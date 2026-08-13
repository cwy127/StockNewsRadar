import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

ET = ZoneInfo("America/New_York")
HISTORY_DIR = Path("data/history/top_us")
RESULTS = Path("data/validation/results_us.json")

def pct(a, b):
    if a is None or b in (None, 0):
        return None
    return round(((a / b) - 1) * 100, 2)

def next_trade_bar(symbol, signal_date):
    start = datetime.strptime(signal_date, "%Y-%m-%d").date() + timedelta(days=1)
    end = start + timedelta(days=10)

    try:
        frame = yf.download(
            symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
            timeout=15,
        )
    except Exception as exc:
        print(f"{symbol} download failed: {exc}")
        return None

    if frame is None or frame.empty:
        return None

    if getattr(frame.columns, "nlevels", 1) > 1:
        try:
            frame.columns = frame.columns.get_level_values(0)
        except Exception:
            pass

    frame = frame.dropna(subset=["Close"])
    if frame.empty:
        return None

    row = frame.iloc[0]
    idx = frame.index[0]
    trade_date = idx.date().isoformat() if hasattr(idx, "date") else str(idx)[:10]

    def val(col):
        try:
            return float(row[col])
        except Exception:
            return None

    return {
        "trade_date": trade_date,
        "open": val("Open"),
        "high": val("High"),
        "low": val("Low"),
        "close": val("Close"),
        "volume": val("Volume"),
    }

def load_results():
    if RESULTS.exists():
        try:
            return json.loads(RESULTS.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "version": "us-top-validation-results-v1",
        "updated_at": None,
        "records": [],
        "summary": {},
    }

def avg(values):
    return round(sum(values) / len(values), 2) if values else None

def summarize(records):
    complete = [r for r in records if r.get("status") == "evaluated"]

    if not complete:
        return {
            "evaluated_count": 0,
            "close_win_rate_pct": None,
            "high_hit_3pct_rate_pct": None,
            "high_hit_5pct_rate_pct": None,
            "avg_gap_open_pct": None,
            "avg_close_return_pct": None,
            "avg_high_return_pct": None,
            "avg_low_return_pct": None,
            "top1_count": 0,
            "top1_close_win_rate_pct": None,
            "top1_avg_close_return_pct": None,
        }

    close_returns = [
        r["next_close_pct"] for r in complete
        if r.get("next_close_pct") is not None
    ]
    high_returns = [
        r["next_high_pct"] for r in complete
        if r.get("next_high_pct") is not None
    ]
    low_returns = [
        r["next_low_pct"] for r in complete
        if r.get("next_low_pct") is not None
    ]
    gap_returns = [
        r["gap_open_pct"] for r in complete
        if r.get("gap_open_pct") is not None
    ]

    wins = [x for x in close_returns if x > 0]
    high3 = [x for x in high_returns if x >= 3]
    high5 = [x for x in high_returns if x >= 5]

    top1 = [r for r in complete if r.get("rank") == 1]
    top1_close = [
        r["next_close_pct"] for r in top1
        if r.get("next_close_pct") is not None
    ]
    top1_wins = [x for x in top1_close if x > 0]

    return {
        "evaluated_count": len(complete),
        "close_win_rate_pct": (
            round(len(wins) / len(close_returns) * 100, 1)
            if close_returns else None
        ),
        "high_hit_3pct_rate_pct": (
            round(len(high3) / len(high_returns) * 100, 1)
            if high_returns else None
        ),
        "high_hit_5pct_rate_pct": (
            round(len(high5) / len(high_returns) * 100, 1)
            if high_returns else None
        ),
        "avg_gap_open_pct": avg(gap_returns),
        "avg_close_return_pct": avg(close_returns),
        "avg_high_return_pct": avg(high_returns),
        "avg_low_return_pct": avg(low_returns),
        "top1_count": len(top1),
        "top1_close_win_rate_pct": (
            round(len(top1_wins) / len(top1_close) * 100, 1)
            if top1_close else None
        ),
        "top1_avg_close_return_pct": avg(top1_close),
    }

def main():
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)

    result_data = load_results()
    records = list(result_data.get("records", []))

    evaluated_keys = {
        (r.get("signal_date"), r.get("symbol"), r.get("rank"))
        for r in records
        if r.get("status") == "evaluated"
    }

    today_et = datetime.now(ET).date().isoformat()

    for path in sorted(HISTORY_DIR.glob("*.json")):
        snap = json.loads(path.read_text(encoding="utf-8"))
        signal_date = snap.get("signal_date")

        if not signal_date or signal_date >= today_et:
            continue

        for item in snap.get("candidates", []):
            key = (
                signal_date,
                item.get("symbol"),
                item.get("rank"),
            )

            if key in evaluated_keys:
                continue

            baseline = item.get("baseline_close")
            bar = next_trade_bar(item.get("symbol"), signal_date)

            record = {
                "signal_date": signal_date,
                "rank": item.get("rank"),
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "market": "US",
                "form": item.get("form"),
                "event": item.get("event"),
                "final_score": item.get("final_score"),
                "material_score": item.get("material_score"),
                "market_confirmation": item.get("market_confirmation"),
                "news_score": item.get("news_score"),
                "news_sentiment": item.get("news_sentiment"),
                "overheat_risk": item.get("overheat_risk"),
                "baseline_close": baseline,
            }

            if not bar or baseline in (None, 0):
                record["status"] = "pending"
                records.append(record)
                continue

            record.update({
                "status": "evaluated",
                "next_trade_date": bar["trade_date"],
                "next_open": bar["open"],
                "next_high": bar["high"],
                "next_low": bar["low"],
                "next_close": bar["close"],
                "next_volume": bar["volume"],
                "gap_open_pct": pct(bar["open"], baseline),
                "next_high_pct": pct(bar["high"], baseline),
                "next_low_pct": pct(bar["low"], baseline),
                "next_close_pct": pct(bar["close"], baseline),
            })

            records.append(record)
            evaluated_keys.add(key)

    # Remove duplicate pending rows after a later successful evaluation.
    evaluated_keys = {
        (r.get("signal_date"), r.get("symbol"), r.get("rank"))
        for r in records
        if r.get("status") == "evaluated"
    }

    deduped = []
    pending_seen = set()

    for r in records:
        key = (
            r.get("signal_date"),
            r.get("symbol"),
            r.get("rank"),
        )

        if r.get("status") == "pending":
            if key in evaluated_keys or key in pending_seen:
                continue
            pending_seen.add(key)

        deduped.append(r)

    deduped.sort(
        key=lambda r: (
            r.get("signal_date") or "",
            -(r.get("rank") or 999),
        ),
        reverse=True,
    )

    payload = {
        "version": "us-top-validation-results-v1",
        "updated_at": datetime.now(ET).isoformat(timespec="seconds"),
        "score_model": "US_V2_SEC45_MARKET30_NEWS25_HEAT15",
        "records": deduped,
        "summary": summarize(deduped),
    }

    RESULTS.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"Wrote {RESULTS}: records={len(deduped)}, "
        f"evaluated={payload['summary']['evaluated_count']}"
    )

if __name__ == "__main__":
    main()
