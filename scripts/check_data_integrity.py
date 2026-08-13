import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
ET = ZoneInfo("America/New_York")

FILES = {
    "kr_live": Path("data/live_kr.json"),
    "us_live": Path("data/live_us.json"),
    "us_news": Path("data/news_us.json"),
    "kr_validation": Path("data/validation/results.json"),
    "us_validation": Path("data/validation/results_us.json"),
    "candidate_history": Path("data/history/candidate_history.json"),
    "performance_analysis": Path("data/analysis/performance_report.json"),
    "persistence_analysis": Path("data/analysis/persistence_performance.json"),
    "daily_brief": Path("data/brief/daily_brief.json"),
}
KR_TOP = Path("data/history/top")
US_TOP = Path("data/history/top_us")
OUT = Path("data/health/integrity_report.json")

def load(path):
    if not path.exists():
        return None, f"missing: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, f"invalid json: {path}: {exc}"

def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None

def add_issue(issues, severity, code, message, **details):
    issues.append({
        "severity": severity,
        "code": code,
        "message": message,
        "details": details,
    })

def latest_snapshot(folder):
    files = sorted(folder.glob("*.json"))
    if not files:
        return None, None
    path = files[-1]
    payload, err = load(path)
    return payload, err

def check_duplicates(items, issues, label):
    seen = set()
    for item in items:
        symbol = str(item.get("symbol", "")).upper()
        if not symbol:
            continue
        if symbol in seen:
            add_issue(issues, "error", "duplicate_symbol",
                      f"{label}: duplicate symbol {symbol}", symbol=symbol)
        seen.add(symbol)

def check_snapshot(payload, issues, label):
    if not payload:
        return
    candidates = payload.get("candidates", [])
    check_duplicates(candidates, issues, label)
    for item in candidates:
        symbol = item.get("symbol")
        if item.get("baseline_close") in (None, 0):
            add_issue(issues, "warning", "missing_baseline_close",
                      f"{label}: {symbol} baseline_close missing", symbol=symbol)
        if item.get("rank") is None:
            add_issue(issues, "warning", "missing_rank",
                      f"{label}: {symbol} rank missing", symbol=symbol)

def check_validation(payload, issues, label):
    if not payload:
        return
    records = payload.get("records", [])
    keys = set()
    for r in records:
        key = (r.get("signal_date"), str(r.get("symbol","")).upper(), r.get("rank"))
        if key in keys and r.get("status") == "evaluated":
            add_issue(issues, "error", "duplicate_evaluation",
                      f"{label}: duplicate evaluated record {key}", key=str(key))
        keys.add(key)
        if r.get("status") == "evaluated":
            for field in ("next_open","next_high","next_low","next_close"):
                if r.get(field) is None:
                    add_issue(issues, "error", "missing_evaluation_price",
                              f"{label}: {key} missing {field}", field=field, key=str(key))
            hi, lo = r.get("next_high"), r.get("next_low")
            op, cl = r.get("next_open"), r.get("next_close")
            if None not in (hi, lo, op, cl):
                if hi < max(op, cl) or lo > min(op, cl) or hi < lo:
                    add_issue(issues, "error", "invalid_ohlc",
                              f"{label}: impossible OHLC {key}", key=str(key))

def main():
    issues = []
    loaded = {}

    for name, path in FILES.items():
        payload, err = load(path)
        loaded[name] = payload
        if err:
            # Analysis files may legitimately not exist early in setup, but report it.
            add_issue(issues, "warning", "file_problem", err, file=name)

    kr_snap, kr_err = latest_snapshot(KR_TOP)
    us_snap, us_err = latest_snapshot(US_TOP)
    if kr_err or kr_snap is None:
        add_issue(issues, "error", "kr_snapshot_missing",
                  kr_err or "No KR TOP snapshot")
    if us_err or us_snap is None:
        add_issue(issues, "error", "us_snapshot_missing",
                  us_err or "No US TOP snapshot")

    check_snapshot(kr_snap, issues, "KR TOP")
    check_snapshot(us_snap, issues, "US TOP")
    check_validation(loaded.get("kr_validation"), issues, "KR validation")
    check_validation(loaded.get("us_validation"), issues, "US validation")

    # Check live candidate duplicates / price presence.
    for key, label in (("kr_live","KR live"), ("us_live","US live")):
        payload = loaded.get(key)
        if not payload:
            continue
        candidates = payload.get("candidates", [])
        check_duplicates(candidates, issues, label)
        positive = [x for x in candidates if x.get("direction") == "positive"]
        missing_price = [x.get("symbol") for x in positive if not x.get("price")]
        if missing_price:
            add_issue(issues, "warning", "positive_candidates_without_price",
                      f"{label}: positive candidates without price",
                      symbols=missing_price[:20], count=len(missing_price))

    # Cross-check latest snapshot against candidate history current list.
    hist = loaded.get("candidate_history") or {}
    for market_key, snap, label in (("kr", kr_snap, "KR"), ("us", us_snap, "US")):
        if not snap or not hist.get(market_key):
            continue
        snap_symbols = {str(x.get("symbol","")).upper() for x in snap.get("candidates", [])}
        hist_symbols = {str(x.get("symbol","")).upper() for x in hist[market_key].get("current", [])}
        if snap_symbols != hist_symbols:
            add_issue(
                issues, "warning", "history_snapshot_mismatch",
                f"{label}: candidate history current set differs from latest snapshot",
                snapshot_only=sorted(snap_symbols-hist_symbols),
                history_only=sorted(hist_symbols-snap_symbols),
            )

    # Freshness: don't declare market-day failures based solely on calendar date;
    # report age so the UI/operator can distinguish weekends/holidays.
    now = datetime.now(KST)
    freshness = {}
    for key in ("kr_live","us_live","us_news","kr_validation","us_validation",
                "candidate_history","performance_analysis","persistence_analysis","daily_brief"):
        payload = loaded.get(key) or {}
        dt = parse_dt(payload.get("generated_at") or payload.get("updated_at"))
        if dt:
            age = (now.astimezone(dt.tzinfo) - dt).total_seconds()/3600
            freshness[key] = round(age, 2)
        else:
            freshness[key] = None

    errors = sum(1 for x in issues if x["severity"] == "error")
    warnings = sum(1 for x in issues if x["severity"] == "warning")
    status = "error" if errors else "warning" if warnings else "ok"

    payload = {
        "version": "data-integrity-v1",
        "generated_at": now.isoformat(timespec="seconds"),
        "status": status,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "issues": len(issues),
            "kr_latest_snapshot": kr_snap.get("signal_date") if kr_snap else None,
            "us_latest_snapshot": us_snap.get("signal_date") if us_snap else None,
        },
        "freshness_hours": freshness,
        "issues": issues,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} status={status} errors={errors} warnings={warnings}")

if __name__ == "__main__":
    main()
