import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

KST = ZoneInfo("Asia/Seoul")
HISTORY_DIR = Path("data/history/top")
RESULTS = Path("data/validation/results.json")

def yahoo_ticker(symbol, market):
    if market == "KOSPI":
        return f"{symbol}.KS"
    if market == "KOSDAQ":
        return f"{symbol}.KQ"
    return None

def pct(a, b):
    if a is None or b in (None, 0):
        return None
    return round(((a / b) - 1) * 100, 2)

def next_trade_bar(symbol, market, signal_date):
    ticker = yahoo_ticker(symbol, market)
    if not ticker:
        return None

    start = datetime.strptime(signal_date, "%Y-%m-%d").date() + timedelta(days=1)
    end = start + timedelta(days=10)

    try:
        frame = yf.download(
            ticker,
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
            timeout=15,
        )
    except Exception as exc:
        print(f"{ticker} download failed: {exc}")
        return None

    if frame is None or frame.empty:
        return None

    # yfinance can return MultiIndex columns even for one ticker.
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
        "version": "top-validation-results-v1",
        "updated_at": None,
        "records": [],
        "summary": {},
    }

def summarize(records):
    complete = [r for r in records if r.get("status") == "evaluated"]
    if not complete:
        return {
            "evaluated_count": 0,
            "close_win_rate_pct": None,
            "high_hit_3pct_rate_pct": None,
            "avg_close_return_pct": None,
            "avg_high_return_pct": None,
            "avg_low_return_pct": None,
        }

    close_returns = [r["next_close_pct"] for r in complete if r.get("next_close_pct") is not None]
    high_returns = [r["next_high_pct"] for r in complete if r.get("next_high_pct") is not None]
    low_returns = [r["next_low_pct"] for r in complete if r.get("next_low_pct") is not None]

    wins = [x for x in close_returns if x > 0]
    high3 = [x for x in high_returns if x >= 3]

    def avg(values):
        return round(sum(values) / len(values), 2) if values else None

    return {
        "evaluated_count": len(complete),
        "close_win_rate_pct": round(len(wins) / len(close_returns) * 100, 1) if close_returns else None,
        "high_hit_3pct_rate_pct": round(len(high3) / len(high_returns) * 100, 1) if high_returns else None,
        "avg_close_return_pct": avg(close_returns),
        "avg_high_return_pct": avg(high_returns),
        "avg_low_return_pct": avg(low_returns),
    }

def main():
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)

    result_data = load_results()
    existing = {
        (r.get("signal_date"), r.get("symbol"), r.get("rank"))
        for r in result_data.get("records", [])
        if r.get("status") == "evaluated"
    }

    records = list(result_data.get("records", []))
    changed = False

    for path in sorted(HISTORY_DIR.glob("*.json")):
        snap = json.loads(path.read_text(encoding="utf-8"))
        signal_date = snap.get("signal_date")
        if not signal_date:
            continue

        # Do not try to evaluate today's snapshot before the next session exists.
        if signal_date >= datetime.now(KST).date().isoformat():
            continue

        for item in snap.get("candidates", []):
            key = (signal_date, item.get("symbol"), item.get("rank"))
            if key in existing:
                continue

            baseline = item.get("baseline_close")
            bar = next_trade_bar(item.get("symbol"), item.get("market"), signal_date)

            base_record = {
                "signal_date": signal_date,
                "rank": item.get("rank"),
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "market": item.get("market"),
                "event": item.get("event"),
                "final_score": item.get("final_score"),
                "material_score": item.get("material_score"),
                "market_confirmation": item.get("market_confirmation"),
                "overheat_risk": item.get("overheat_risk"),
                "baseline_close": baseline,
            }

            if not bar or baseline in (None, 0):
                base_record["status"] = "pending"
                records.append(base_record)
                changed = True
                continue

            base_record.update({
                "status": "evaluated",
                "next_trade_date": bar["trade_date"],
                "next_open": bar["open"],
                "next_high": bar["high"],
                "next_low": bar["low"],
                "next_close": bar["close"],
                "gap_open_pct": pct(bar["open"], baseline),
                "next_high_pct": pct(bar["high"], baseline),
                "next_low_pct": pct(bar["low"], baseline),
                "next_close_pct": pct(bar["close"], baseline),
            })
            records.append(base_record)
            existing.add(key)
            changed = True

    # Deduplicate pending records when later runs successfully evaluate the same key.
    evaluated_keys = {
        (r.get("signal_date"), r.get("symbol"), r.get("rank"))
        for r in records if r.get("status") == "evaluated"
    }
    deduped = []
    seen_pending = set()
    for r in records:
        key = (r.get("signal_date"), r.get("symbol"), r.get("rank"))
        if r.get("status") == "pending":
            if key in evaluated_keys or key in seen_pending:
                continue
            seen_pending.add(key)
        deduped.append(r)

    deduped.sort(
        key=lambda r: (
            r.get("signal_date") or "",
            -(r.get("rank") or 999),
        ),
        reverse=True,
    )

    payload = {
        "version": "top-validation-results-v1",
        "updated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "records": deduped,
        "summary": summarize(deduped),
    }

    RESULTS.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"Wrote {RESULTS}: "
        f"records={len(deduped)}, "
        f"evaluated={payload['summary'].get('evaluated_count')}"
    )

if __name__ == "__main__":
    main()
