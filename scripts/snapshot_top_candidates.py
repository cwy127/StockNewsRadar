import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
LIVE = Path("data/live_kr.json")
HISTORY_DIR = Path("data/history/top")

def final_score(x):
    m = x.get("material_score") or 0
    c = x.get("market_confirmation")
    h = x.get("overheat_risk")
    p = x.get("price") or {}

    c = 40 if c is None else c
    h = 50 if h is None else h
    score = m * 0.55 + c * 0.35 - h * 0.20

    day = p.get("day_change_pct")
    five = p.get("five_day_change_pct")
    vr = p.get("volume_ratio_20d")

    if day is not None and day > 12:
        score -= 8
    if five is not None and five > 20:
        score -= 8
    if vr is not None and 1.2 <= vr <= 4:
        score += 4

    return round(max(0, min(100, score)), 1)

def main():
    if not LIVE.exists():
        raise SystemExit("data/live_kr.json not found")

    data = json.loads(LIVE.read_text(encoding="utf-8"))
    candidates = data.get("candidates", [])

    positive = [x for x in candidates if x.get("direction") == "positive"]
    positive.sort(
        key=lambda x: (final_score(x), x.get("published_at", "")),
        reverse=True,
    )

    top_candidates = [
        x for x in positive
        if (x.get("overheat_risk") is None or x.get("overheat_risk") <= 65)
        and (x.get("market_confirmation") is None or x.get("market_confirmation") >= 35)
    ][:7]

    now = datetime.now(KST)
    trade_date = now.strftime("%Y-%m-%d")

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    out = HISTORY_DIR / f"{trade_date}.json"

    rows = []
    for rank, item in enumerate(top_candidates, 1):
        price = item.get("price") or {}
        rows.append({
            "rank": rank,
            "symbol": item.get("symbol"),
            "name": item.get("name"),
            "market": item.get("market"),
            "event": item.get("event"),
            "report_name": item.get("report_name"),
            "published_at": item.get("published_at"),
            "receipt_no": item.get("receipt_no"),
            "material_score": item.get("material_score"),
            "market_confirmation": item.get("market_confirmation"),
            "overheat_risk": item.get("overheat_risk"),
            "final_score": final_score(item),
            "baseline_close": price.get("latest_close"),
            "day_change_pct": price.get("day_change_pct"),
            "five_day_change_pct": price.get("five_day_change_pct"),
            "volume_ratio_20d": price.get("volume_ratio_20d"),
            "distance_20d_high_pct": price.get("distance_20d_high_pct"),
        })

    payload = {
        "version": "top-validation-snapshot-v1",
        "snapshot_at": now.isoformat(timespec="seconds"),
        "signal_date": trade_date,
        "source_generated_at": data.get("generated_at"),
        "count": len(rows),
        "candidates": rows,
    }

    # Same-day reruns overwrite the snapshot with the latest final version.
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {out} with {len(rows)} candidates")

if __name__ == "__main__":
    main()
