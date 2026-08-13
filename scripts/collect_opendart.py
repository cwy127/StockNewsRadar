import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

API = "https://opendart.fss.or.kr/api/list.json"
KEY = os.environ["OPENDART_API_KEY"].strip()
KST = ZoneInfo("Asia/Seoul")
OUT = Path("data/live_kr.json")

DISCLOSURE_TYPES = ("B", "C", "D", "I")
LISTED_CLASSES = {"Y": "KOSPI", "K": "KOSDAQ", "N": "KONEX"}

RULES = [
    ("상장폐지", 99, "negative", "상장폐지 관련", "거래 가능성과 기업 존속에 직접 영향을 줄 수 있는 공시"),
    ("회생절차", 98, "negative", "회생절차", "재무 건전성과 기업 존속에 큰 영향을 줄 수 있는 사건"),
    ("횡령", 97, "negative", "횡령·배임", "재무·지배구조 위험이 큰 사건"),
    ("배임", 97, "negative", "횡령·배임", "재무·지배구조 위험이 큰 사건"),
    ("영업정지", 95, "negative", "영업정지", "본업의 매출과 현금흐름에 직접 영향을 줄 수 있는 사건"),
    ("감자결정", 93, "negative", "감자 결정", "자본구조에 큰 변화를 주는 사건"),
    ("유상증자결정", 91, "negative", "유상증자", "기존 주주 지분 희석 가능성이 있는 자금조달"),
    ("전환사채권발행결정", 89, "negative", "전환사채 발행", "향후 주식 전환에 따른 희석 가능성이 있는 자금조달"),
    ("신주인수권부사채권발행결정", 89, "negative", "BW 발행", "향후 신주 발행에 따른 희석 가능성이 있는 자금조달"),
    ("소송등의제기", 88, "negative", "중요 소송 제기", "재무·사업에 영향을 줄 수 있는 법적 분쟁"),
    ("합병결정", 90, "neutral", "합병 결정", "기업가치·지배구조 변화가 커 세부 조건 확인 필요"),
    ("분할결정", 87, "neutral", "분할 결정", "사업·지배구조 변화가 커 세부 조건 확인 필요"),
    ("타법인주식및출자증권양수결정", 85, "neutral", "대규모 투자·인수", "자산 및 사업구조 변화 가능성이 있는 사건"),
    ("단일판매ㆍ공급계약체결", 87, "positive", "공급계약 체결", "매출로 연결될 수 있는 직접적인 수주·계약 공시"),
    ("단일판매·공급계약체결", 87, "positive", "공급계약 체결", "매출로 연결될 수 있는 직접적인 수주·계약 공시"),
    ("자기주식소각결정", 87, "positive", "자사주 소각", "유통주식수 감소에 직접 영향을 주는 주주환원"),
    ("자기주식취득결정", 83, "positive", "자사주 취득", "회사가 직접 주식을 매입하는 주주환원"),
    ("공개매수", 90, "neutral", "공개매수", "주가와 지배구조에 직접 영향을 줄 수 있어 조건 확인 필요"),
    ("최대주주변경", 83, "neutral", "최대주주 변경", "지배구조 변화가 발생한 사건"),
    ("소송등의판결", 82, "neutral", "중요 소송 판결", "판결 내용에 따라 영향 방향이 달라 원문 확인 필요"),
    ("무상증자결정", 79, "neutral", "무상증자", "주식 수 변화가 크지만 기업가치 증가와 동일하지 않아 확인 필요"),
    ("영업(잠정)실적", 77, "neutral", "잠정 실적", "실적 수치와 시장 예상치를 비교해야 방향 판단 가능"),
    ("매출액또는손익구조", 77, "neutral", "실적 변동", "실제 증가·감소 폭을 원문에서 확인해야 함"),
    ("투자판단관련주요경영사항", 75, "neutral", "주요 경영사항", "회사 가치에 영향을 줄 수 있어 원문 확인 필요"),
    ("주요사항보고서", 68, "neutral", "주요사항보고", "중요 공시 유형이지만 세부 내용 확인 필요"),
]

def compact(value):
    return "".join((value or "").split())

def classify(name):
    name_c = compact(name)
    for keyword, score, direction, label, reason in RULES:
        if compact(keyword) in name_c:
            return score, direction, label, reason
    return 42, "neutral", "일반 공시", "우선순위 규칙에 해당하지 않는 공시"

def grade(score):
    if score >= 82:
        return "A"
    if score >= 68:
        return "B"
    return "관찰"

def request_json(params, retries=3):
    url = API + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 StockNewsRadar-Collector/1.1",
                    "Accept": "application/json",
                    "Connection": "close",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(1.0 + attempt)
    raise RuntimeError(str(last))

def fetch_type(kind, start_date, end_date):
    rows = []
    page = 1
    while page <= 30:
        payload = request_json({
            "crtfc_key": KEY,
            "bgn_de": start_date,
            "end_de": end_date,
            "pblntf_ty": kind,
            "sort": "date",
            "sort_mth": "desc",
            "page_no": page,
            "page_count": 100,
        })
        status = payload.get("status")
        if status == "013":
            break
        if status != "000":
            raise RuntimeError(f"type={kind} status={status} message={payload.get('message')}")
        batch = payload.get("list", [])
        rows.extend(batch)
        total_page = int(payload.get("total_page") or 1)
        if page >= total_page or len(batch) < 100:
            break
        page += 1
    return rows

def yahoo_ticker(stock_code, market):
    if market == "KOSPI":
        return f"{stock_code}.KS"
    if market == "KOSDAQ":
        return f"{stock_code}.KQ"
    return None

def score_market_confirmation(day_change, five_day, volume_ratio):
    score = 40.0
    if day_change is not None:
        if 0 < day_change <= 5:
            score += 15
        elif 5 < day_change <= 10:
            score += 10
        elif day_change > 10:
            score += 3
        elif -3 <= day_change < 0:
            score += 4
        elif day_change < -3:
            score -= 8

    if volume_ratio is not None:
        if 1.2 <= volume_ratio < 2.5:
            score += 20
        elif 2.5 <= volume_ratio < 5:
            score += 15
        elif volume_ratio >= 5:
            score += 8
        elif volume_ratio < 0.8:
            score -= 7

    if five_day is not None:
        if -2 <= five_day <= 8:
            score += 10
        elif 8 < five_day <= 15:
            score += 4
        elif five_day > 15:
            score -= 6

    return int(max(0, min(100, round(score))))

def score_overheat(day_change, five_day, volume_ratio, distance_20d_high):
    risk = 10.0
    if day_change is not None:
        if day_change >= 20:
            risk += 40
        elif day_change >= 12:
            risk += 30
        elif day_change >= 7:
            risk += 18
        elif day_change >= 4:
            risk += 8

    if five_day is not None:
        if five_day >= 30:
            risk += 35
        elif five_day >= 20:
            risk += 25
        elif five_day >= 12:
            risk += 12

    if volume_ratio is not None:
        if volume_ratio >= 8:
            risk += 15
        elif volume_ratio >= 5:
            risk += 10

    if distance_20d_high is not None and distance_20d_high >= -1.5:
        risk += 8

    return int(max(0, min(100, round(risk))))

def parse_price_frame(frame):
    if frame is None or frame.empty:
        return None

    frame = frame.dropna(subset=["Close"]).copy()
    if len(frame) < 6:
        return None

    close = frame["Close"].astype(float)
    volume = frame["Volume"].astype(float).fillna(0)

    latest = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    day_change = ((latest / prev) - 1) * 100 if prev else None

    five_base = float(close.iloc[-6])
    five_day = ((latest / five_base) - 1) * 100 if five_base else None

    vol_window = volume.iloc[-21:-1]
    vol_avg20 = float(vol_window.mean()) if len(vol_window) else 0
    latest_vol = float(volume.iloc[-1])
    volume_ratio = (latest_vol / vol_avg20) if vol_avg20 > 0 else None

    high20 = float(frame["High"].astype(float).iloc[-20:].max())
    distance_high = ((latest / high20) - 1) * 100 if high20 else None

    confirmation = score_market_confirmation(day_change, five_day, volume_ratio)
    overheat = score_overheat(day_change, five_day, volume_ratio, distance_high)

    return {
        "latest_close": round(latest, 2),
        "day_change_pct": round(day_change, 2) if day_change is not None else None,
        "five_day_change_pct": round(five_day, 2) if five_day is not None else None,
        "volume_ratio_20d": round(volume_ratio, 2) if volume_ratio is not None else None,
        "distance_20d_high_pct": round(distance_high, 2) if distance_high is not None else None,
        "market_confirmation": confirmation,
        "overheat_risk": overheat,
    }

def fetch_price_data(candidates):
    mapping = {}
    for item in candidates:
        ticker = yahoo_ticker(item["symbol"], item["market"])
        if ticker:
            mapping[ticker] = item["symbol"]

    tickers = list(mapping)
    results = {}

    for i in range(0, len(tickers), 25):
        chunk = tickers[i:i+25]
        try:
            data = yf.download(
                tickers=chunk,
                period="3mo",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                timeout=15,
                group_by="ticker",
            )
        except Exception as exc:
            print(f"yfinance chunk failed: {exc}")
            continue

        if data is None or data.empty:
            continue

        for ticker in chunk:
            try:
                if len(chunk) == 1:
                    frame = data.copy()
                else:
                    frame = data[ticker].copy()
                parsed = parse_price_frame(frame)
                if parsed:
                    results[mapping[ticker]] = parsed
            except Exception as exc:
                print(f"price parse failed {ticker}: {exc}")

    return results

def build_candidates(rows):
    seen = set()
    output = []
    for row in rows:
        corp_cls = (row.get("corp_cls") or "").strip()
        stock_code = (row.get("stock_code") or "").strip()
        receipt = (row.get("rcept_no") or "").strip()
        report = (row.get("report_nm") or "").strip()

        if corp_cls not in LISTED_CLASSES or not stock_code or not receipt:
            continue

        key = (receipt, stock_code, report)
        if key in seen:
            continue
        seen.add(key)

        score, direction, label, reason = classify(report)
        if score < 68:
            continue

        output.append({
            "grade": grade(score),
            "symbol": stock_code,
            "name": (row.get("corp_name") or "").strip(),
            "market": LISTED_CLASSES[corp_cls],
            "direction": direction,
            "material_score": score,
            "event": label,
            "report_name": report,
            "reason": reason,
            "published_at": row.get("rcept_dt") or "",
            "receipt_no": receipt,
            "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}",
        })

    output.sort(
        key=lambda x: (x["material_score"], x["published_at"], x["receipt_no"]),
        reverse=True,
    )
    output = output[:120]

    price_data = fetch_price_data(output)

    for item in output:
        px = price_data.get(item["symbol"])
        if px:
            item["price"] = px
            item["market_confirmation"] = px["market_confirmation"]
            item["overheat_risk"] = px["overheat_risk"]
        else:
            item["price"] = None
            item["market_confirmation"] = None
            item["overheat_risk"] = None

    return output

def substantive(payload):
    return {
        "window": payload.get("window"),
        "raw_count": payload.get("raw_count"),
        "candidate_count": payload.get("candidate_count"),
        "candidates": payload.get("candidates"),
    }

def main():
    now = datetime.now(KST)
    start = (now.date() - timedelta(days=2)).strftime("%Y%m%d")
    end = now.date().strftime("%Y%m%d")

    rows = []
    source_status = {}
    for kind in DISCLOSURE_TYPES:
        try:
            batch = fetch_type(kind, start, end)
            rows.extend(batch)
            source_status[kind] = {"ok": True, "count": len(batch)}
        except Exception as exc:
            source_status[kind] = {"ok": False, "count": 0, "error": str(exc)}

    if not rows:
        raise SystemExit("No OpenDART data fetched; keeping the previous live_kr.json.")

    candidates = build_candidates(rows)
    price_count = sum(1 for x in candidates if x.get("price"))

    payload = {
        "version": "kr-live-price-v1",
        "generated_at": now.isoformat(timespec="seconds"),
        "window": {"start": start, "end": end},
        "raw_count": len(rows),
        "candidate_count": len(candidates),
        "price_enriched_count": price_count,
        "source_status": source_status,
        "candidates": candidates,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)

    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
            if substantive(old) == substantive(payload):
                print("No substantive changes. live_kr.json remains unchanged.")
                return
        except Exception:
            pass

    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"Wrote {OUT}: raw={len(rows)}, candidates={len(candidates)}, "
        f"price_enriched={price_count}"
    )

if __name__ == "__main__":
    main()
