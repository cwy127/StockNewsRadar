import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://opendart.fss.or.kr/api/list.json"
KEY = os.environ["OPENDART_API_KEY"].strip()
KST = ZoneInfo("Asia/Seoul")
OUT = Path("data/live_kr.json")

# B 주요사항 / C 발행 / D 지분 / I 거래소 공시
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
                    "User-Agent": "Mozilla/5.0 StockNewsRadar-Collector/1.0",
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
    return output[:120]

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
    payload = {
        "version": "kr-live-v1",
        "generated_at": now.isoformat(timespec="seconds"),
        "window": {"start": start, "end": end},
        "raw_count": len(rows),
        "candidate_count": len(candidates),
        "source_status": source_status,
        "candidates": candidates,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)

    # Avoid repository commits when the actual candidate data did not change.
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
    print(f"Wrote {OUT}: raw={len(rows)}, candidates={len(candidates)}")

if __name__ == "__main__":
    main()
