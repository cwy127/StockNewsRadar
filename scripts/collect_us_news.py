import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

LIVE = Path("data/live_us.json")
OUT = Path("data/news_us.json")

POSITIVE = {
    "fda approval": 20, "approval": 10, "approved": 10,
    "contract": 12, "award": 10, "partnership": 10, "strategic partnership": 14,
    "acquisition": 10, "merger": 8, "beats estimates": 15, "beats expectations": 15,
    "raises guidance": 18, "guidance raised": 18, "buyback": 14, "share repurchase": 14,
    "dividend increase": 12, "record revenue": 10, "record sales": 10,
}
NEGATIVE = {
    "offering": 15, "public offering": 20, "bankruptcy": 25, "chapter 11": 25,
    "investigation": 15, "subpoena": 15, "recall": 15, "delisting": 20,
    "cuts guidance": 18, "guidance cut": 18, "misses estimates": 15,
    "layoffs": 8, "lawsuit": 10, "data breach": 12,
}

def fetch(url, timeout=12):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 StockNewsRadar/1.0",
            "Accept": "application/rss+xml,application/xml,text/xml,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def clean(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def parse_google_news_rss(data):
    root = ET.fromstring(data)
    items = []
    for node in root.findall(".//item"):
        title = clean(node.findtext("title", ""))
        link = clean(node.findtext("link", ""))
        pub = clean(node.findtext("pubDate", ""))
        source_el = node.find("source")
        source = clean(source_el.text if source_el is not None else "")
        try:
            dt = parsedate_to_datetime(pub).astimezone(timezone.utc)
            published_at = dt.isoformat(timespec="seconds")
        except Exception:
            published_at = pub
        items.append({
            "title": title,
            "url": link,
            "source": source,
            "published_at": published_at,
        })
    return items

def headline_score(title):
    low = title.lower()
    pos = sum(weight for key, weight in POSITIVE.items() if key in low)
    neg = sum(weight for key, weight in NEGATIVE.items() if key in low)
    return pos, neg

def query_news(symbol, company):
    # Company name + ticker reduces false positives for short/ambiguous symbols.
    short_company = re.sub(r"\b(inc|corp|corporation|ltd|plc|co|company)\b\.?", "", company, flags=re.I)
    short_company = re.sub(r"\s+", " ", short_company).strip()
    query = f'"{symbol}" "{short_company}" stock when:1d'
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    })
    data = fetch(url)
    return parse_google_news_rss(data)[:10]

def main():
    if not LIVE.exists():
        raise SystemExit("data/live_us.json not found")

    live = json.loads(LIVE.read_text(encoding="utf-8"))
    candidates = live.get("candidates", [])

    # Prioritize candidates that already have SEC relevance and price data.
    candidates = sorted(
        candidates,
        key=lambda x: (
            x.get("direction") == "positive",
            x.get("material_score") or 0,
            x.get("market_confirmation") or 0,
        ),
        reverse=True,
    )[:35]

    rows = []
    for idx, item in enumerate(candidates, 1):
        symbol = item.get("symbol", "")
        name = item.get("name", "")
        try:
            news = query_news(symbol, name)
        except Exception as exc:
            print(f"{symbol}: news fetch failed: {exc}")
            news = []

        pos_total = 0
        neg_total = 0
        scored = []
        seen_titles = set()

        for article in news:
            title = article["title"]
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            pos, neg = headline_score(title)
            pos_total += pos
            neg_total += neg
            article["positive_points"] = pos
            article["negative_points"] = neg
            scored.append(article)

        # Breadth is a confirmation signal, but cap it so duplicated coverage cannot dominate.
        breadth_bonus = min(len(scored), 5) * 2
        news_score = 50 + breadth_bonus + min(pos_total, 30) - min(neg_total, 30)
        news_score = int(max(0, min(100, news_score)))

        if neg_total > pos_total and neg_total >= 10:
            sentiment = "negative"
        elif pos_total > neg_total and pos_total >= 10:
            sentiment = "positive"
        else:
            sentiment = "neutral"

        rows.append({
            "symbol": symbol,
            "name": name,
            "news_score": news_score,
            "news_sentiment": sentiment,
            "article_count": len(scored),
            "positive_points": pos_total,
            "negative_points": neg_total,
            "articles": scored[:5],
        })
        print(f"{idx}/{len(candidates)} {symbol}: articles={len(scored)} score={news_score}")
        time.sleep(0.25)

    payload = {
        "version": "us-news-layer-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_count": len(rows),
        "items": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")

if __name__ == "__main__":
    main()
