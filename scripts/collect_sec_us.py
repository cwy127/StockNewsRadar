import gzip
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

OUT = Path("data/live_us.json")
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "").strip()

if not SEC_USER_AGENT:
    raise SystemExit(
        "SEC_USER_AGENT is required. Example: StockNewsRadar contact@example.com"
    )

HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json, application/atom+xml, text/html;q=0.9,*/*;q=0.8",
}

FORMS = ["8-K", "10-Q", "10-K", "6-K", "S-3", "S-3ASR", "424B5", "SC 13D", "SC 13G"]

FORM_RULES = {
    "424B5": (90, "negative", "증권 발행/희석 가능성", "추가 증권 발행에 따른 희석 가능성을 우선 확인"),
    "S-3": (84, "negative", "증권 등록", "향후 자금조달 및 희석 가능성 확인 필요"),
    "S-3ASR": (84, "negative", "증권 등록", "향후 자금조달 및 희석 가능성 확인 필요"),
    "SC 13D": (82, "neutral", "대량보유 공시", "5% 이상 보유 및 적극적 지분 목적 여부 확인 필요"),
    "SC 13G": (72, "neutral", "대량보유 공시", "기관·대주주 지분 변화 확인 필요"),
    "10-Q": (78, "neutral", "분기 실적", "실적과 가이던스가 시장 예상 대비 어떤지 확인 필요"),
    "10-K": (76, "neutral", "연간 실적", "연간 실적과 향후 전망 확인 필요"),
    "6-K": (76, "neutral", "외국기업 주요 공시", "미국 상장 외국기업의 주요 이벤트 확인 필요"),
    "8-K": (80, "neutral", "주요 경영 이벤트", "8-K 항목과 첨부자료를 확인해 방향 판단 필요"),
}

POSITIVE_KEYWORDS = [
    "results of operations", "financial condition", "material definitive agreement",
    "acquisition", "strategic agreement", "share repurchase", "repurchase program",
    "dividend", "guidance", "earnings", "contract", "award", "approval",
]
NEGATIVE_KEYWORDS = [
    "bankruptcy", "delisting", "impairment", "restatement", "default",
    "termination", "resignation", "investigation", "subpoena", "material weakness",
    "going concern", "offering", "securities purchase agreement",
]

def sec_get(url, timeout=20, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                content_encoding = (r.headers.get("Content-Encoding") or "").lower()
                if content_encoding == "gzip" or data[:2] == b"\x1f\x8b":
                    data = gzip.decompress(data)
                return data, r.headers.get("Content-Type", "")
        except Exception as exc:
            last = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"SEC request failed: {url}: {last}")

def load_cik_ticker_map():
    data, _ = sec_get("https://www.sec.gov/files/company_tickers.json")
    raw = json.loads(data.decode("utf-8"))
    mapping = {}
    for item in raw.values():
        cik = str(item["cik_str"]).zfill(10)
        mapping[cik] = {
            "ticker": item.get("ticker", ""),
            "title": item.get("title", ""),
        }
    return mapping

def parse_atom(form, count=100):
    query = urllib.parse.urlencode({
        "action": "getcurrent",
        "type": form,
        "company": "",
        "dateb": "",
        "owner": "exclude",
        "start": 0,
        "count": count,
        "output": "atom",
    })
    url = f"https://www.sec.gov/cgi-bin/browse-edgar?{query}"
    data, _ = sec_get(url)
    root = ET.fromstring(data)
    ns = {"a": "http://www.w3.org/2005/Atom"}

    rows = []
    for entry in root.findall("a:entry", ns):
        title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        summary = (entry.findtext("a:summary", default="", namespaces=ns) or "").strip()
        updated = (entry.findtext("a:updated", default="", namespaces=ns) or "").strip()
        link_el = entry.find("a:link", ns)
        href = link_el.attrib.get("href", "") if link_el is not None else ""

        cik_match = re.search(r"CIK=(\d+)", href)
        if not cik_match:
            cik_match = re.search(r"\((\d{6,10})\)", title)
        cik = cik_match.group(1).zfill(10) if cik_match else ""

        acc_match = re.search(r"AccNo:\s*([0-9-]+)", summary)
        accession = acc_match.group(1) if acc_match else ""

        company = title
        if " - " in title:
            company = title.split(" - ", 1)[-1]
        company = re.sub(r"\s*\(\d+\)\s*$", "", company).strip()

        rows.append({
            "form": form,
            "title": title,
            "summary": summary,
            "updated": updated,
            "href": href,
            "cik": cik,
            "accession": accession,
            "company": company,
        })
    return rows

def fetch_filing_text(cik, accession):
    if not cik or not accession:
        return ""
    cik_int = str(int(cik))
    accession_nodash = accession.replace("-", "")
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
        f"{accession_nodash}/{accession}-index.html"
    )
    try:
        data, _ = sec_get(index_url, timeout=15, retries=2)
        text = re.sub(r"<[^>]+>", " ", data.decode("utf-8", errors="ignore"))
        text = re.sub(r"\s+", " ", text)
        return text[:30000]
    except Exception:
        return ""

def classify(row, filing_text):
    form = row["form"]
    score, direction, event, reason = FORM_RULES.get(
        form, (60, "neutral", "SEC 공시", "원문 확인 필요")
    )

    hay = f'{row.get("summary","")} {filing_text}'.lower()
    if form in {"8-K", "6-K"}:
        pos_hits = sum(1 for k in POSITIVE_KEYWORDS if k in hay)
        neg_hits = sum(1 for k in NEGATIVE_KEYWORDS if k in hay)

        if neg_hits > pos_hits and neg_hits > 0:
            direction = "negative"
            score = max(score, 86)
            event = "주의 이벤트"
            reason = "공시 내 위험·희석·조사·재무경고 관련 키워드가 확인됨"
        elif pos_hits > neg_hits and pos_hits > 0:
            direction = "positive"
            score = max(score, 84)
            event = "상승 촉매 가능"
            reason = "실적·계약·자사주·배당·승인 등 긍정 촉매 키워드가 확인됨"

    return score, direction, event, reason

def likely_warrant_or_unit(ticker):
    # Recent SEC ticker map frequently includes warrants such as BFRIW/CINGW/BNZIW.
    # For this stock radar, omit obvious warrant/unit tickers rather than treating
    # them as common-stock candidates.
    t = (ticker or "").upper().strip()
    if len(t) >= 4 and t.endswith("W"):
        return True
    if len(t) >= 5 and t.endswith("U"):
        return True
    return False

def yahoo_symbol(ticker):
    return ticker.replace(".", "-")

def parse_price_frame(df):
    if df is None or df.empty:
        return None

    if getattr(df.columns, "nlevels", 1) > 1:
        try:
            df.columns = df.columns.get_level_values(0)
        except Exception:
            pass

    df = df.dropna(subset=["Close"]).copy()
    if len(df) < 21:
        return None

    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float).fillna(0)
    latest = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    five_base = float(close.iloc[-6])

    day = ((latest / prev) - 1) * 100 if prev else None
    five = ((latest / five_base) - 1) * 100 if five_base else None
    avg20 = float(volume.iloc[-21:-1].mean())
    vr = float(volume.iloc[-1]) / avg20 if avg20 > 0 else None
    high20 = float(df["High"].astype(float).iloc[-20:].max())
    dist_high = ((latest / high20) - 1) * 100 if high20 else None

    confirmation = 40
    if day is not None:
        if 0 < day <= 5:
            confirmation += 15
        elif 5 < day <= 10:
            confirmation += 10
        elif day > 10:
            confirmation += 2
        elif day < -3:
            confirmation -= 8
    if vr is not None:
        if 1.2 <= vr < 2.5:
            confirmation += 20
        elif 2.5 <= vr < 5:
            confirmation += 15
        elif vr >= 5:
            confirmation += 7
        elif vr < .8:
            confirmation -= 7
    if five is not None:
        if -2 <= five <= 8:
            confirmation += 10
        elif five > 15:
            confirmation -= 6

    heat = 10
    if day is not None:
        if day >= 20:
            heat += 40
        elif day >= 12:
            heat += 30
        elif day >= 7:
            heat += 18
    if five is not None:
        if five >= 30:
            heat += 35
        elif five >= 20:
            heat += 25
        elif five >= 12:
            heat += 12
    if vr is not None and vr >= 5:
        heat += 10
    if dist_high is not None and dist_high >= -1.5:
        heat += 8

    return {
        "latest_close": round(latest, 2),
        "day_change_pct": round(day, 2) if day is not None else None,
        "five_day_change_pct": round(five, 2) if five is not None else None,
        "volume_ratio_20d": round(vr, 2) if vr is not None else None,
        "distance_20d_high_pct": round(dist_high, 2) if dist_high is not None else None,
        "market_confirmation": int(max(0, min(100, confirmation))),
        "overheat_risk": int(max(0, min(100, heat))),
    }

def fetch_prices(candidates):
    symbol_map = {}
    for item in candidates:
        ys = yahoo_symbol(item["symbol"])
        symbol_map[ys] = item["symbol"]

    y_symbols = list(symbol_map)
    results = {}

    for i in range(0, len(y_symbols), 25):
        chunk = y_symbols[i:i + 25]
        try:
            data = yf.download(
                tickers=chunk,
                period="3mo",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                timeout=20,
                group_by="ticker",
            )
        except Exception as exc:
            print(f"US price batch failed: {exc}")
            continue

        if data is None or data.empty:
            continue

        for ys in chunk:
            try:
                frame = data.copy() if len(chunk) == 1 else data[ys].copy()
                parsed = parse_price_frame(frame)
                if parsed:
                    results[symbol_map[ys]] = parsed
            except Exception as exc:
                print(f"US price parse failed {ys}: {exc}")

    # Targeted retry for positive candidates that a batch request missed.
    for item in candidates:
        ticker = item["symbol"]
        if ticker in results or item.get("direction") != "positive":
            continue
        ys = yahoo_symbol(ticker)
        try:
            df = yf.download(
                ys,
                period="3mo",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
                timeout=15,
            )
            parsed = parse_price_frame(df)
            if parsed:
                results[ticker] = parsed
        except Exception as exc:
            print(f"US price retry failed {ys}: {exc}")

    return results

def main():
    cik_map = load_cik_ticker_map()

    filings = []
    for form in FORMS:
        try:
            batch = parse_atom(form, 100)
            filings.extend(batch)
            print(f"{form}: {len(batch)}")
        except Exception as exc:
            print(f"{form} feed failed: {exc}")
        time.sleep(0.15)

    seen = set()
    candidates = []
    excluded_special = 0

    for row in filings:
        cik = row["cik"]
        ticker_info = cik_map.get(cik)
        if not ticker_info:
            continue

        ticker = (ticker_info.get("ticker") or "").strip().upper()
        if not ticker or ticker in seen:
            continue

        if likely_warrant_or_unit(ticker):
            excluded_special += 1
            seen.add(ticker)
            continue

        seen.add(ticker)

        filing_text = ""
        if row["form"] in {"8-K", "6-K"}:
            filing_text = fetch_filing_text(cik, row.get("accession"))
            time.sleep(0.12)

        score, direction, event, reason = classify(row, filing_text)

        candidates.append({
            "symbol": ticker,
            "name": ticker_info.get("title") or row.get("company") or ticker,
            "market": "US",
            "form": row["form"],
            "direction": direction,
            "material_score": score,
            "grade": "A" if score >= 84 else "B" if score >= 72 else "관찰",
            "event": event,
            "report_name": row.get("title", ""),
            "reason": reason,
            "published_at": row.get("updated", ""),
            "cik": cik,
            "accession": row.get("accession", ""),
            "url": row.get("href", ""),
        })

        if len(candidates) >= 80:
            break

    # Price-enrich ALL candidates in batches, instead of only the first 60.
    prices = fetch_prices(candidates)
    enriched = 0

    for item in candidates:
        px = prices.get(item["symbol"])
        if px:
            item["price"] = px
            item["market_confirmation"] = px["market_confirmation"]
            item["overheat_risk"] = px["overheat_risk"]
            item["price_status"] = "ok"
            enriched += 1
        else:
            item["price"] = None
            item["market_confirmation"] = None
            item["overheat_risk"] = None
            item["price_status"] = "unavailable"

    candidates.sort(
        key=lambda x: (
            x.get("material_score") or 0,
            x.get("published_at") or "",
        ),
        reverse=True,
    )

    now = datetime.now(timezone.utc)
    payload = {
        "version": "us-sec-live-v2-price-cleanup",
        "generated_at": now.isoformat(timespec="seconds"),
        "candidate_count": len(candidates),
        "price_enriched_count": enriched,
        "excluded_special_ticker_count": excluded_special,
        "forms": FORMS,
        "candidates": candidates,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"Wrote {OUT}: candidates={len(candidates)}, "
        f"price_enriched={enriched}, excluded_special={excluded_special}"
    )

if __name__ == "__main__":
    main()
