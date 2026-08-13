import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

KR_SNAPSHOT_DIR = Path("data/history/top")
US_SNAPSHOT_DIR = Path("data/history/top_us")
KR_RESULTS = Path("data/validation/results.json")
US_RESULTS = Path("data/validation/results_us.json")
OUT = Path("data/analysis/persistence_performance.json")

MIN_SAMPLE = 10
GOOD_SAMPLE = 30

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None

def median(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    n = len(values)
    m = n // 2
    if n % 2:
        return round(values[m], 2)
    return round((values[m - 1] + values[m]) / 2, 2)

def sample_status(n):
    if n < MIN_SAMPLE:
        return "표본 부족"
    if n < GOOD_SAMPLE:
        return "초기 참고"
    return "분석 가능"

def load_snapshots(folder):
    snapshots = []
    for path in sorted(folder.glob("*.json")):
        payload = load_json(path)
        date = payload.get("signal_date")
        if not date:
            continue
        symbols = {}
        for item in payload.get("candidates", []):
            symbol = str(item.get("symbol", "")).upper()
            if not symbol:
                continue
            symbols[symbol] = {
                "rank": item.get("rank"),
                "final_score": item.get("final_score"),
            }
        snapshots.append({"date": date, "symbols": symbols})
    snapshots.sort(key=lambda x: x["date"])
    return snapshots

def build_signal_metadata(snapshots):
    # Metadata for each (signal_date, symbol), calculated only with information
    # available up to that signal date.
    meta = {}
    seen_dates = defaultdict(list)

    for idx, snap in enumerate(snapshots):
        date = snap["date"]
        current_symbols = set(snap["symbols"].keys())

        for symbol in current_symbols:
            previous_dates = seen_dates[symbol]
            total_before = len(previous_dates)

            # Consecutive snapshot streak ending today.
            streak = 1
            j = idx - 1
            while j >= 0:
                if symbol in snapshots[j]["symbols"]:
                    streak += 1
                    j -= 1
                else:
                    break

            is_first = total_before == 0
            was_in_previous_snapshot = (
                idx > 0 and symbol in snapshots[idx - 1]["symbols"]
            )
            is_reentry = (not is_first) and (not was_in_previous_snapshot)

            if is_first:
                stage = "첫 등장"
            elif is_reentry:
                stage = "재등장"
            elif streak == 2:
                stage = "2회 연속"
            else:
                stage = "3회 이상 연속"

            recent_start = max(0, idx - 9)
            recent_count = 0
            for prior_idx in range(recent_start, idx + 1):
                if symbol in snapshots[prior_idx]["symbols"]:
                    recent_count += 1

            meta[(date, symbol)] = {
                "stage": stage,
                "streak_at_signal": streak,
                "appearance_number": total_before + 1,
                "recent_10_appearances_at_signal": recent_count,
                "is_first": is_first,
                "is_reentry": is_reentry,
            }

            seen_dates[symbol].append(date)

    return meta

def summarize(rows):
    close = [r.get("next_close_pct") for r in rows if r.get("next_close_pct") is not None]
    high = [r.get("next_high_pct") for r in rows if r.get("next_high_pct") is not None]
    low = [r.get("next_low_pct") for r in rows if r.get("next_low_pct") is not None]
    gap = [r.get("gap_open_pct") for r in rows if r.get("gap_open_pct") is not None]

    wins = [v for v in close if v > 0]
    hit3 = [v for v in high if v >= 3]
    hit5 = [v for v in high if v >= 5]

    return {
        "count": len(rows),
        "sample_status": sample_status(len(rows)),
        "close_win_rate_pct": round(len(wins) / len(close) * 100, 1) if close else None,
        "high_hit_3pct_rate_pct": round(len(hit3) / len(high) * 100, 1) if high else None,
        "high_hit_5pct_rate_pct": round(len(hit5) / len(high) * 100, 1) if high else None,
        "avg_close_return_pct": avg(close),
        "median_close_return_pct": median(close),
        "avg_high_return_pct": avg(high),
        "avg_low_return_pct": avg(low),
        "avg_gap_open_pct": avg(gap),
    }

def group_by(rows, key, ordered_labels=None):
    buckets = defaultdict(list)
    for row in rows:
        buckets[row.get(key, "기타")].append(row)

    labels = ordered_labels or sorted(buckets.keys(), key=str)
    out = []
    for label in labels:
        bucket = buckets.get(label, [])
        if not bucket:
            continue
        out.append({
            "label": str(label),
            **summarize(bucket),
        })
    return out

def recent_frequency_bucket(v):
    if v is None:
        return "기타"
    if v <= 1:
        return "최근10회 중 1회"
    if v <= 3:
        return "최근10회 중 2–3회"
    if v <= 5:
        return "최근10회 중 4–5회"
    return "최근10회 중 6회 이상"

def analyze_market(snapshot_dir, results_file, market):
    snapshots = load_snapshots(snapshot_dir)
    meta = build_signal_metadata(snapshots)

    results = load_json(results_file)
    evaluated = [
        r for r in results.get("records", [])
        if r.get("status") == "evaluated"
    ]

    enriched = []
    unmatched = 0

    for r in evaluated:
        signal_date = r.get("signal_date")
        symbol = str(r.get("symbol", "")).upper()
        m = meta.get((signal_date, symbol))

        if not m:
            unmatched += 1
            continue

        row = dict(r)
        row.update(m)
        row["recent_frequency_bucket"] = recent_frequency_bucket(
            m.get("recent_10_appearances_at_signal")
        )
        enriched.append(row)

    by_stage = group_by(
        enriched,
        "stage",
        ["첫 등장", "2회 연속", "3회 이상 연속", "재등장"],
    )

    by_recent_frequency = group_by(
        enriched,
        "recent_frequency_bucket",
        [
            "최근10회 중 1회",
            "최근10회 중 2–3회",
            "최근10회 중 4–5회",
            "최근10회 중 6회 이상",
        ],
    )

    # Appearance number buckets: 1st, 2nd, 3-5th, 6th+
    numbered = []
    for row in enriched:
        n = row.get("appearance_number")
        copy = dict(row)
        if n == 1:
            label = "1번째 등장"
        elif n == 2:
            label = "2번째 등장"
        elif n is not None and n <= 5:
            label = "3–5번째 등장"
        else:
            label = "6번째 이상"
        copy["appearance_bucket"] = label
        numbered.append(copy)

    by_appearance_number = group_by(
        numbered,
        "appearance_bucket",
        ["1번째 등장", "2번째 등장", "3–5번째 등장", "6번째 이상"],
    )

    best_stage = None
    eligible = [
        g for g in by_stage
        if g.get("count", 0) >= MIN_SAMPLE
        and g.get("avg_close_return_pct") is not None
    ]
    if eligible:
        best = max(eligible, key=lambda g: g["avg_close_return_pct"])
        best_stage = {
            "label": best["label"],
            "count": best["count"],
            "avg_close_return_pct": best["avg_close_return_pct"],
            "close_win_rate_pct": best["close_win_rate_pct"],
        }

    return {
        "market": market,
        "snapshot_count": len(snapshots),
        "evaluated_matched_count": len(enriched),
        "unmatched_result_count": unmatched,
        "overall": summarize(enriched),
        "by_persistence_stage": by_stage,
        "by_recent_10_frequency": by_recent_frequency,
        "by_appearance_number": by_appearance_number,
        "best_persistence_stage": best_stage,
    }

def main():
    kr = analyze_market(KR_SNAPSHOT_DIR, KR_RESULTS, "KR")
    us = analyze_market(US_SNAPSHOT_DIR, US_RESULTS, "US")

    payload = {
        "version": "persistence-performance-v1",
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "sample_rules": {
            "minimum_for_best_stage": MIN_SAMPLE,
            "recommended_for_analysis": GOOD_SAMPLE,
        },
        "definition": {
            "first_seen": "해당 시장 TOP 스냅샷에 처음 등장한 신호",
            "second_consecutive": "직전 스냅샷에도 있었고 현재 연속 2회째인 신호",
            "third_plus_consecutive": "현재 연속 3회 이상 TOP에 남은 신호",
            "reentry": "과거 등장한 적은 있으나 직전 스냅샷에는 없다가 다시 등장한 신호",
        },
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
        f"KR matched={kr['evaluated_matched_count']} | "
        f"US matched={us['evaluated_matched_count']}"
    )

if __name__ == "__main__":
    main()
