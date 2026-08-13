import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

KR_DIR = Path("data/history/top")
US_DIR = Path("data/history/top_us")
OUT = Path("data/brief/daily_brief.json")

def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def latest_two(folder):
    files = sorted(folder.glob("*.json"))
    if not files:
        return None, None
    latest = files[-1]
    prev = files[-2] if len(files) >= 2 else None
    return latest, prev

def normalize_candidates(payload):
    rows = []
    for item in payload.get("candidates", []):
        rows.append({
            "rank": item.get("rank"),
            "symbol": item.get("symbol"),
            "name": item.get("name"),
            "final_score": item.get("final_score"),
            "market_confirmation": item.get("market_confirmation"),
            "overheat_risk": item.get("overheat_risk"),
            "news_score": item.get("news_score"),
            "event": item.get("event"),
            "baseline_close": item.get("baseline_close"),
        })
    return rows

def build_market(folder, market):
    latest_path, prev_path = latest_two(folder)

    if not latest_path:
        return {
            "market": market,
            "status": "no_snapshot",
            "latest_date": None,
            "previous_date": None,
            "latest": [],
            "new": [],
            "retained": [],
            "dropped": [],
        }

    latest_payload = load(latest_path)
    prev_payload = load(prev_path) if prev_path else {}

    latest = normalize_candidates(latest_payload)
    prev = normalize_candidates(prev_payload)

    latest_map = {str(x.get("symbol")): x for x in latest if x.get("symbol")}
    prev_map = {str(x.get("symbol")): x for x in prev if x.get("symbol")}

    new_symbols = [s for s in latest_map if s not in prev_map]
    retained_symbols = [s for s in latest_map if s in prev_map]
    dropped_symbols = [s for s in prev_map if s not in latest_map]

    new_rows = [latest_map[s] for s in new_symbols]
    retained_rows = []
    for s in retained_symbols:
        cur = latest_map[s]
        old = prev_map[s]
        retained_rows.append({
            **cur,
            "previous_rank": old.get("rank"),
            "rank_change": (
                (old.get("rank") - cur.get("rank"))
                if old.get("rank") is not None and cur.get("rank") is not None
                else None
            ),
            "previous_score": old.get("final_score"),
            "score_change": (
                round(cur.get("final_score") - old.get("final_score"), 1)
                if cur.get("final_score") is not None and old.get("final_score") is not None
                else None
            ),
        })

    dropped_rows = [prev_map[s] for s in dropped_symbols]

    new_rows.sort(key=lambda x: x.get("rank") or 999)
    retained_rows.sort(key=lambda x: x.get("rank") or 999)
    dropped_rows.sort(key=lambda x: x.get("rank") or 999)

    strongest = latest[0] if latest else None

    return {
        "market": market,
        "status": "ok",
        "latest_date": latest_payload.get("signal_date"),
        "previous_date": prev_payload.get("signal_date") if prev_payload else None,
        "latest_count": len(latest),
        "new_count": len(new_rows),
        "retained_count": len(retained_rows),
        "dropped_count": len(dropped_rows),
        "strongest": strongest,
        "latest": latest,
        "new": new_rows,
        "retained": retained_rows,
        "dropped": dropped_rows,
    }

def main():
    kr = build_market(KR_DIR, "KR")
    us = build_market(US_DIR, "US")

    payload = {
        "version": "daily-brief-v1",
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "kr": kr,
        "us": us,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"Wrote {OUT} | "
        f"KR new={kr.get('new_count',0)} retained={kr.get('retained_count',0)} | "
        f"US new={us.get('new_count',0)} retained={us.get('retained_count',0)}"
    )

if __name__ == "__main__":
    main()
