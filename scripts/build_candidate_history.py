import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

KR_DIR = Path("data/history/top")
US_DIR = Path("data/history/top_us")
OUT = Path("data/history/candidate_history.json")

RECENT_WINDOW = 10

def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def load_snapshots(folder):
    snapshots = []

    for path in sorted(folder.glob("*.json")):
        payload = load_json(path)
        signal_date = payload.get("signal_date")
        if not signal_date:
            continue

        candidates = []
        for item in payload.get("candidates", []):
            symbol = item.get("symbol")
            if not symbol:
                continue

            candidates.append({
                "symbol": str(symbol),
                "name": item.get("name"),
                "rank": item.get("rank"),
                "final_score": item.get("final_score"),
                "market_confirmation": item.get("market_confirmation"),
                "overheat_risk": item.get("overheat_risk"),
                "news_score": item.get("news_score"),
                "event": item.get("event"),
            })

        snapshots.append({
            "date": signal_date,
            "candidates": candidates,
        })

    snapshots.sort(key=lambda x: x["date"])
    return snapshots

def consecutive_streak(snapshot_dates, presence_dates):
    if not snapshot_dates or not presence_dates:
        return 0

    presence = set(presence_dates)

    streak = 0
    for date in reversed(snapshot_dates):
        if date in presence:
            streak += 1
        else:
            break

    return streak

def build_market(folder, market):
    snapshots = load_snapshots(folder)
    snapshot_dates = [s["date"] for s in snapshots]

    history = {}

    for snap in snapshots:
        date = snap["date"]

        for item in snap["candidates"]:
            symbol = item["symbol"]

            entry = history.setdefault(symbol, {
                "symbol": symbol,
                "name": item.get("name"),
                "market": market,
                "appearances": [],
            })

            if item.get("name"):
                entry["name"] = item.get("name")

            entry["appearances"].append({
                "date": date,
                "rank": item.get("rank"),
                "final_score": item.get("final_score"),
                "market_confirmation": item.get("market_confirmation"),
                "overheat_risk": item.get("overheat_risk"),
                "news_score": item.get("news_score"),
                "event": item.get("event"),
            })

    recent_dates = set(snapshot_dates[-RECENT_WINDOW:])

    items = []

    for symbol, entry in history.items():
        apps = sorted(entry["appearances"], key=lambda x: x["date"])

        dates = [a["date"] for a in apps]

        ranks = [
            a["rank"] for a in apps
            if isinstance(a.get("rank"), (int, float))
        ]

        scores = [
            a["final_score"] for a in apps
            if isinstance(a.get("final_score"), (int, float))
        ]

        latest = apps[-1]

        recent_apps = [
            a for a in apps
            if a["date"] in recent_dates
        ]

        previous = apps[-2] if len(apps) >= 2 else None

        rank_change = None
        score_change = None

        if previous:
            if (
                isinstance(previous.get("rank"), (int, float))
                and isinstance(latest.get("rank"), (int, float))
            ):
                rank_change = previous["rank"] - latest["rank"]

            if (
                isinstance(previous.get("final_score"), (int, float))
                and isinstance(latest.get("final_score"), (int, float))
            ):
                score_change = round(
                    latest["final_score"] - previous["final_score"],
                    1,
                )

        item = {
            "symbol": symbol,
            "name": entry.get("name"),
            "market": market,

            "first_seen": dates[0],
            "last_seen": dates[-1],

            "consecutive_days": consecutive_streak(
                snapshot_dates,
                dates,
            ),

            "recent_10_appearances": len(recent_apps),
            "total_appearances": len(apps),

            "best_rank": min(ranks) if ranks else None,
            "best_score": round(max(scores), 1) if scores else None,

            "latest_rank": latest.get("rank"),
            "latest_score": latest.get("final_score"),

            "rank_change_from_previous_appearance": rank_change,
            "score_change_from_previous_appearance": score_change,

            "latest_event": latest.get("event"),
            "latest_market_confirmation": latest.get("market_confirmation"),
            "latest_overheat_risk": latest.get("overheat_risk"),
            "latest_news_score": latest.get("news_score"),

            "appearance_dates": dates,
        }

        items.append(item)

    items.sort(
        key=lambda x: (
            x.get("last_seen") or "",
            x.get("consecutive_days") or 0,
            x.get("recent_10_appearances") or 0,
            -(x.get("latest_rank") or 999),
        ),
        reverse=True,
    )

    current_date = snapshot_dates[-1] if snapshot_dates else None

    current = [
        item for item in items
        if item.get("last_seen") == current_date
    ]

    return {
        "market": market,
        "snapshot_count": len(snapshots),
        "latest_snapshot_date": current_date,
        "recent_window": RECENT_WINDOW,
        "current_count": len(current),
        "current": current,
        "all": items,
    }

def main():
    kr = build_market(KR_DIR, "KR")
    us = build_market(US_DIR, "US")

    payload = {
        "version": "candidate-history-v1",
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "recent_window": RECENT_WINDOW,
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
        f"KR snapshots={kr['snapshot_count']} current={kr['current_count']} | "
        f"US snapshots={us['snapshot_count']} current={us['current_count']}"
    )

if __name__ == "__main__":
    main()
