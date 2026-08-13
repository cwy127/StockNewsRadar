import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
LIVE = Path("data/live_us.json")
NEWS = Path("data/news_us.json")
HISTORY_DIR = Path("data/history/top_us")

def load_news_map():
    if not NEWS.exists():
        return {}
    try:
        payload = json.loads(NEWS.read_text(encoding="utf-8"))
        return {
            str(item.get("symbol", "")).upper(): item
            for item in payload.get("items", [])
            if item.get("symbol")
        }
    except Exception:
        return {}

NEWS_BY_SYMBOL = load_news_map()

def final_score(x):
    m = x.get("material_score") or 0
    c = x.get("market_confirmation")
    h = x.get("overheat_risk")
    p = x.get("price") or {}
    news = NEWS_BY_SYMBOL.get(str(x.get("symbol", "")).upper(), {})

    c = 40 if c is None else c
    h = 50 if h is None else h
    n = news.get("news_score")
    n = 50 if n is None else n

    score = m * 0.45 + c * 0.30 + n * 0.25 - h * 0.15

    sec_dir = x.get("direction")
    news_dir = news.get("news_sentiment")
    if sec_dir == "positive" and news_dir == "positive":
        score += 5
    elif sec_dir == "negative" and news_dir == "negative":
        score -= 4
    elif (
        sec_dir in {"positive", "negative"}
        and news_dir in {"positive", "negative"}
        and sec_dir != news_dir
    ):
        score -= 7

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
        raise SystemExit("data/live_us.json not found")

    data = json.loads(LIVE.read_text(encoding="utf-8"))
    candidates = data.get("candidates", [])

    positive = [x for x in candidates if x.get("direction") == "positive"]
    positive.sort(
        key=lambda x: (final_score(x), x.get("published_at", "")),
        reverse=True,
    )

    top_candidates = [
        x for x in positive
        if x.get("price")
        and (x.get("overheat_risk") is None or x.get("overheat_risk") <= 65)
        and (x.get("market_confirmation") is None or x.get("market_confirmation") >= 35)
    ][:7]

    now = datetime.now(ET)
    signal_date = now.date().isoformat()

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    out = HISTORY_DIR / f"{signal_date}.json"

    rows = []
    for rank, item in enumerate(top_candidates, 1):
        symbol = str(item.get("symbol", "")).upper()
        price = item.get("price") or {}
        news = NEWS_BY_SYMBOL.get(symbol, {})

        rows.append({
            "rank": rank,
            "symbol": symbol,
            "name": item.get("name"),
            "market": "US",
            "form": item.get("form"),
            "event": item.get("event"),
            "report_name": item.get("report_name"),
            "published_at": item.get("published_at"),
            "accession": item.get("accession"),
            "sec_direction": item.get("direction"),
            "material_score": item.get("material_score"),
            "market_confirmation": item.get("market_confirmation"),
            "news_score": news.get("news_score"),
            "news_sentiment": news.get("news_sentiment"),
            "news_article_count": news.get("article_count"),
            "overheat_risk": item.get("overheat_risk"),
            "final_score": final_score(item),
            "baseline_close": price.get("latest_close"),
            "day_change_pct": price.get("day_change_pct"),
            "five_day_change_pct": price.get("five_day_change_pct"),
            "volume_ratio_20d": price.get("volume_ratio_20d"),
            "distance_20d_high_pct": price.get("distance_20d_high_pct"),
        })

    payload = {
        "version": "us-top-validation-snapshot-v1",
        "snapshot_at": now.isoformat(timespec="seconds"),
        "signal_date": signal_date,
        "source_sec_generated_at": data.get("generated_at"),
        "source_news_generated_at": (
            json.loads(NEWS.read_text(encoding="utf-8")).get("generated_at")
            if NEWS.exists()
            else None
        ),
        "score_model": "US_V2_SEC45_MARKET30_NEWS25_HEAT15",
        "count": len(rows),
        "candidates": rows,
    }

    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {out} with {len(rows)} candidates")

if __name__ == "__main__":
    main()
