import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

KR_RESULTS = Path("data/validation/results.json")
US_RESULTS = Path("data/validation/results_us.json")
OUT = Path("data/analysis/performance_report.json")

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
    mid = n // 2
    if n % 2:
        return round(values[mid], 2)
    return round((values[mid - 1] + values[mid]) / 2, 2)

def sample_label(n):
    if n < MIN_SAMPLE:
        return "표본 부족"
    if n < GOOD_SAMPLE:
        return "초기 참고"
    return "분석 가능"

def summarize_group(rows):
    close = [r.get("next_close_pct") for r in rows if r.get("next_close_pct") is not None]
    high = [r.get("next_high_pct") for r in rows if r.get("next_high_pct") is not None]
    low = [r.get("next_low_pct") for r in rows if r.get("next_low_pct") is not None]
    gap = [r.get("gap_open_pct") for r in rows if r.get("gap_open_pct") is not None]

    wins = [v for v in close if v > 0]
    hit3 = [v for v in high if v >= 3]
    hit5 = [v for v in high if v >= 5]

    return {
        "count": len(rows),
        "sample_status": sample_label(len(rows)),
        "close_win_rate_pct": round(len(wins) / len(close) * 100, 1) if close else None,
        "high_hit_3pct_rate_pct": round(len(hit3) / len(high) * 100, 1) if high else None,
        "high_hit_5pct_rate_pct": round(len(hit5) / len(high) * 100, 1) if high else None,
        "avg_close_return_pct": avg(close),
        "median_close_return_pct": median(close),
        "avg_high_return_pct": avg(high),
        "avg_low_return_pct": avg(low),
        "avg_gap_open_pct": avg(gap),
    }

def group_exact(rows, field, values):
    out = []
    for value in values:
        bucket = [r for r in rows if r.get(field) == value]
        if bucket:
            out.append({
                "label": str(value),
                "field": field,
                "value": value,
                **summarize_group(bucket),
            })
    return out

def group_ranges(rows, field, ranges):
    out = []
    for label, lo, hi in ranges:
        bucket = []
        for r in rows:
            v = r.get(field)
            if v is None:
                continue
            if lo is not None and v < lo:
                continue
            if hi is not None and v >= hi:
                continue
            bucket.append(r)

        if bucket:
            out.append({
                "label": label,
                "field": field,
                "min": lo,
                "max_exclusive": hi,
                **summarize_group(bucket),
            })
    return out

def direction_combo(rows):
    labels = [
        ("SEC+뉴스 긍정", lambda r: r.get("news_sentiment") == "positive"),
        ("뉴스 중립", lambda r: r.get("news_sentiment") in (None, "neutral")),
        ("뉴스 부정", lambda r: r.get("news_sentiment") == "negative"),
    ]
    out = []
    for label, fn in labels:
        bucket = [r for r in rows if fn(r)]
        if bucket:
            out.append({"label": label, **summarize_group(bucket)})
    return out

def best_bucket(groups, metric="avg_close_return_pct"):
    eligible = [
        g for g in groups
        if g.get("count", 0) >= MIN_SAMPLE and g.get(metric) is not None
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda g: g.get(metric))

def analyze_market(payload, market):
    rows = [
        r for r in payload.get("records", [])
        if r.get("status") == "evaluated"
    ]

    common_ranges = {
        "market_confirmation": [
            ("0–39", 0, 40),
            ("40–54", 40, 55),
            ("55–69", 55, 70),
            ("70–84", 70, 85),
            ("85–100", 85, None),
        ],
        "overheat_risk": [
            ("0–19", 0, 20),
            ("20–39", 20, 40),
            ("40–59", 40, 60),
            ("60–79", 60, 80),
            ("80–100", 80, None),
        ],
        "final_score": [
            ("0–49", 0, 50),
            ("50–59", 50, 60),
            ("60–69", 60, 70),
            ("70–79", 70, 80),
            ("80–100", 80, None),
        ],
    }

    result = {
        "market": market,
        "overall": summarize_group(rows),
        "by_rank": group_exact(rows, "rank", list(range(1, 8))),
        "by_market_confirmation": group_ranges(
            rows, "market_confirmation", common_ranges["market_confirmation"]
        ),
        "by_overheat_risk": group_ranges(
            rows, "overheat_risk", common_ranges["overheat_risk"]
        ),
        "by_final_score": group_ranges(
            rows, "final_score", common_ranges["final_score"]
        ),
    }

    if market == "US":
        result["by_sec_score"] = group_ranges(
            rows,
            "material_score",
            [
                ("0–69", 0, 70),
                ("70–79", 70, 80),
                ("80–89", 80, 90),
                ("90–100", 90, None),
            ],
        )
        result["by_news_score"] = group_ranges(
            rows,
            "news_score",
            [
                ("0–44", 0, 45),
                ("45–54", 45, 55),
                ("55–64", 55, 65),
                ("65–74", 65, 75),
                ("75–100", 75, None),
            ],
        )
        result["by_news_sentiment"] = direction_combo(rows)

    # Automatic highlights only when minimum sample is met.
    highlights = {}
    for key in [
        "by_rank",
        "by_market_confirmation",
        "by_overheat_risk",
        "by_final_score",
        "by_sec_score",
        "by_news_score",
        "by_news_sentiment",
    ]:
        if key in result:
            best = best_bucket(result[key])
            if best:
                highlights[key] = {
                    "label": best.get("label"),
                    "count": best.get("count"),
                    "avg_close_return_pct": best.get("avg_close_return_pct"),
                    "close_win_rate_pct": best.get("close_win_rate_pct"),
                }

    result["highlights"] = highlights
    return result

def main():
    kr = load_json(KR_RESULTS)
    us = load_json(US_RESULTS)

    kr_analysis = analyze_market(kr, "KR")
    us_analysis = analyze_market(us, "US")

    payload = {
        "version": "performance-analysis-v1",
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "sample_rules": {
            "minimum_for_highlight": MIN_SAMPLE,
            "recommended_for_analysis": GOOD_SAMPLE,
            "labels": {
                "under_10": "표본 부족",
                "10_to_29": "초기 참고",
                "30_plus": "분석 가능",
            },
        },
        "kr": kr_analysis,
        "us": us_analysis,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"Wrote {OUT} | "
        f"KR={kr_analysis['overall']['count']} evaluated, "
        f"US={us_analysis['overall']['count']} evaluated"
    )

if __name__ == "__main__":
    main()
