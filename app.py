import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import streamlit as st

st.set_page_config(page_title="StockNewsRadar", page_icon="📡", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
:root{--bg:#0b0d10;--card:#15181d;--card2:#1b1f25;--text:#f4f6f8;--muted:#9ca3af;--line:#272c34;--green:#39d98a;--red:#ff5d67;--yellow:#f5c451;--blue:#4f8cff}
html,body,[class*="css"]{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Apple SD Gothic Neo",sans-serif}
.stApp{background:var(--bg);color:var(--text)}
.block-container{max-width:760px;padding-top:5rem;padding-left:.85rem;padding-right:.85rem;padding-bottom:5rem}
.hero{margin:.2rem 0 1rem}.hero-title{font-size:1.9rem;font-weight:780;line-height:1.05}.hero-sub{color:var(--muted);font-size:.86rem;margin-top:.35rem}
.live-badge{display:inline-block;padding:.19rem .48rem;border-radius:999px;background:rgba(57,217,138,.13);color:var(--green);font-size:.67rem;font-weight:800;margin-left:.35rem;vertical-align:middle}
.market-strip{display:grid;grid-template-columns:repeat(2,1fr);gap:.5rem;margin-bottom:1rem}.market-chip{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:.75rem .8rem}.market-chip .k{color:var(--muted);font-size:.72rem}.market-chip .v{font-size:.92rem;font-weight:700;margin-top:.08rem}
.pos{color:var(--green)}.neg{color:var(--red)}.warn{color:var(--yellow)}.neutral{color:var(--text)}
.top-card{background:linear-gradient(180deg,#18221d,#141917);border:1px solid rgba(57,217,138,.25);border-radius:20px;padding:1rem 1rem;margin:.7rem 0}
.top-rank{display:inline-block;min-width:2rem;text-align:center;background:rgba(57,217,138,.15);color:var(--green);border-radius:999px;padding:.2rem .45rem;font-size:.74rem;font-weight:900;margin-right:.45rem}
.stock-card{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:18px;padding:.95rem 1rem;margin:.7rem 0}
.card-top{display:flex;justify-content:space-between;gap:.7rem;align-items:flex-start}.stock-name{font-size:1.05rem;font-weight:750}.symbol{color:var(--muted);font-size:.78rem;margin-top:.08rem}
.grade{border-radius:999px;padding:.25rem .55rem;font-size:.74rem;font-weight:800}.grade-a{background:rgba(57,217,138,.14);color:var(--green)}.grade-b{background:rgba(245,196,81,.14);color:var(--yellow)}
.event{margin-top:.72rem;font-weight:700;font-size:.94rem}.summary{color:#c7ccd4;font-size:.83rem;line-height:1.45;margin-top:.28rem}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:.4rem;margin-top:.8rem}.metric{background:#101318;border-radius:11px;padding:.55rem .35rem;text-align:center}.metric .n{font-size:.95rem;font-weight:800}.metric .l{color:var(--muted);font-size:.61rem;margin-top:.05rem}
.price-line{margin-top:.6rem;font-size:.76rem;color:#aeb5bf;line-height:1.45}.reason{border-top:1px solid var(--line);margin-top:.75rem;padding-top:.65rem;font-size:.78rem;color:#cbd1d8}.meta{color:#7f8792;font-size:.68rem;margin-top:.45rem}
.source-link{display:inline-block;margin-top:.55rem;color:#8ab4ff!important;text-decoration:none;font-size:.76rem;font-weight:700}
.section-title{font-size:1.05rem;font-weight:800;margin-top:1.15rem;margin-bottom:.4rem}.notice{background:#11151a;border:1px solid var(--line);border-radius:14px;padding:.8rem;color:#aeb5bf;font-size:.76rem;line-height:1.45;margin-top:1rem}.empty{background:#11151a;border:1px solid var(--line);border-radius:14px;padding:1rem;color:#aeb5bf;font-size:.82rem;line-height:1.5}
.bucket-positive{border-left:3px solid var(--green);padding-left:.65rem}.bucket-neutral{border-left:3px solid var(--yellow);padding-left:.65rem}.bucket-negative{border-left:3px solid var(--red);padding-left:.65rem}

.price-up{color:var(--red);font-weight:800}
.price-down{color:var(--blue);font-weight:800}
.price-flat{color:#d5dae1;font-weight:700}
div[data-testid="stExpander"]{
  background:#11151a!important;
  border:1px solid var(--line)!important;
  border-radius:14px!important;
  overflow:hidden!important;
}
div[data-testid="stExpander"] details,
div[data-testid="stExpander"] summary{
  background:#11151a!important;
  color:var(--text)!important;
}
div[data-testid="stExpander"] summary:hover{
  background:#171c22!important;
}
div[data-testid="stExpander"] summary *{
  color:var(--text)!important;
}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"]{
  background:#0f1317!important;
  color:var(--text)!important;
  border-top:1px solid var(--line)!important;
}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] *{
  color:inherit;
}


.perf-tabs{margin-top:.65rem}
.perf-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:.5rem;margin:.8rem 0 1rem}
.perf-box{background:#14181d;border:1px solid var(--line);border-radius:14px;padding:.8rem}
.perf-box .k{color:var(--muted);font-size:.7rem}
.perf-box .v{font-size:1.08rem;font-weight:850;margin-top:.15rem}
.perf-row{background:#14181d;border:1px solid var(--line);border-radius:14px;padding:.8rem;margin:.55rem 0}
.perf-row-top{display:flex;justify-content:space-between;gap:.6rem;align-items:center}
.perf-rank{font-weight:850}
.perf-name{font-weight:750}
.perf-small{color:var(--muted);font-size:.72rem;margin-top:.18rem}
.perf-returns{display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem;margin-top:.55rem}
.perf-return{background:#101318;border-radius:10px;padding:.5rem .35rem;text-align:center}
.perf-return .k{font-size:.62rem;color:var(--muted)}
.perf-return .v{font-weight:850;font-size:.86rem;margin-top:.08rem}


/* Compact segmented controls: preserve native layout, force dark unselected state */
div[data-testid="stSegmentedControl"]{
  width:fit-content!important;
  max-width:100%!important;
}
div[data-testid="stSegmentedControl"] > div{
  width:fit-content!important;
  max-width:100%!important;
}

/* all segments = unselected appearance */
div[data-testid="stSegmentedControl"] button,
div[data-testid="stSegmentedControl"] [role="radio"],
div[data-testid="stSegmentedControl"] [role="button"]{
  background:#0b0d10!important;
  background-color:#0b0d10!important;
  color:#f4f6f8!important;
  -webkit-text-fill-color:#f4f6f8!important;
  border-color:#f4f6f8!important;
  box-shadow:none!important;
}
div[data-testid="stSegmentedControl"] button *,
div[data-testid="stSegmentedControl"] [role="radio"] *,
div[data-testid="stSegmentedControl"] [role="button"] *{
  color:#f4f6f8!important;
  -webkit-text-fill-color:#f4f6f8!important;
  background:transparent!important;
}

/* selected segment: cover Streamlit/BaseWeb state variants */
div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
div[data-testid="stSegmentedControl"] button[aria-checked="true"],
div[data-testid="stSegmentedControl"] button[aria-selected="true"],
div[data-testid="stSegmentedControl"] button[data-selected="true"],
div[data-testid="stSegmentedControl"] button[data-active="true"],
div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"],
div[data-testid="stSegmentedControl"] [role="radio"][aria-selected="true"],
div[data-testid="stSegmentedControl"] [role="button"][aria-pressed="true"],
div[data-testid="stSegmentedControl"] [role="button"][aria-selected="true"]{
  background:#241012!important;
  background-color:#241012!important;
  color:var(--red)!important;
  -webkit-text-fill-color:var(--red)!important;
  border-color:var(--red)!important;
}
div[data-testid="stSegmentedControl"] button[aria-pressed="true"] *,
div[data-testid="stSegmentedControl"] button[aria-checked="true"] *,
div[data-testid="stSegmentedControl"] button[aria-selected="true"] *,
div[data-testid="stSegmentedControl"] button[data-selected="true"] *,
div[data-testid="stSegmentedControl"] button[data-active="true"] *,
div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"] *,
div[data-testid="stSegmentedControl"] [role="radio"][aria-selected="true"] *,
div[data-testid="stSegmentedControl"] [role="button"][aria-pressed="true"] *,
div[data-testid="stSegmentedControl"] [role="button"][aria-selected="true"] *{
  color:var(--red)!important;
  -webkit-text-fill-color:var(--red)!important;
}

/* keep compact size close to original */
div[data-testid="stSegmentedControl"] button,
div[data-testid="stSegmentedControl"] [role="radio"],
div[data-testid="stSegmentedControl"] [role="button"]{
  min-height:0!important;
  padding-top:.36rem!important;
  padding-bottom:.36rem!important;
}





.brief-wrap{margin:.7rem 0 1rem}
.brief-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:.5rem}
.brief-card{background:#14181d;border:1px solid var(--line);border-radius:14px;padding:.75rem}
.brief-k{font-size:.66rem;color:var(--muted)}
.brief-v{font-size:.95rem;font-weight:850;margin-top:.1rem}
.brief-list{margin-top:.5rem}
.brief-item{background:#11151a;border:1px solid var(--line);border-radius:11px;padding:.6rem .7rem;margin:.35rem 0}
.brief-item-top{display:flex;justify-content:space-between;gap:.5rem}
.brief-name{font-size:.78rem;font-weight:800}
.brief-meta{font-size:.64rem;color:var(--muted);margin-top:.15rem}

.analysis-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:.5rem;margin:.7rem 0}
.analysis-card{background:#14181d;border:1px solid var(--line);border-radius:14px;padding:.75rem}
.analysis-card .k{font-size:.67rem;color:var(--muted)}
.analysis-card .v{font-size:.95rem;font-weight:850;margin-top:.12rem}
.analysis-row{background:#11151a;border:1px solid var(--line);border-radius:12px;padding:.65rem .7rem;margin:.42rem 0}
.analysis-row-top{display:flex;justify-content:space-between;gap:.5rem}
.analysis-label{font-size:.78rem;font-weight:800}
.analysis-sample{font-size:.65rem;color:var(--muted)}
.analysis-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:.35rem;margin-top:.42rem}
.analysis-metric{background:#0d1115;border-radius:9px;padding:.4rem;text-align:center}
.analysis-metric .k{font-size:.58rem;color:var(--muted)}
.analysis-metric .v{font-size:.76rem;font-weight:800;margin-top:.05rem}

.health-wrap{margin:.7rem 0 .9rem}
.health-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:.42rem}
.health-item{background:#11151a;border:1px solid var(--line);border-radius:12px;padding:.62rem .7rem}
.health-k{font-size:.66rem;color:var(--muted)}
.health-v{font-size:.78rem;font-weight:800;margin-top:.12rem}
.health-ok{color:var(--green)}
.health-warn{color:var(--yellow)}
.health-bad{color:var(--red)}
.health-wait{color:#aeb5bf}

.news-box{border-top:1px solid var(--line);margin-top:.7rem;padding-top:.65rem}
.news-head{display:flex;justify-content:space-between;gap:.5rem;align-items:center;margin-bottom:.35rem}
.news-title{font-size:.76rem;font-weight:800;color:#d9dee5}
.news-score{font-size:.72rem;font-weight:850}
.news-item{display:block;color:#aeb7c4!important;text-decoration:none;font-size:.72rem;line-height:1.35;margin:.28rem 0}
.news-item:hover{color:#ffffff!important}
.news-meta{color:#737d89;font-size:.64rem}
.metrics.us-five{grid-template-columns:repeat(5,1fr)}
@media(max-width:600px){.metrics.us-five{grid-template-columns:repeat(2,1fr)}}

@media(max-width:600px){.block-container{padding-top:5rem}.hero-title{font-size:1.72rem}.metrics{grid-template-columns:repeat(2,1fr)}}
</style>
""", unsafe_allow_html=True)

KST = ZoneInfo("Asia/Seoul")
LIVE_FILE = Path("data/live_kr.json")
VALIDATION_FILE = Path("data/validation/results.json")
US_VALIDATION_FILE = Path("data/validation/results_us.json")
US_LIVE_FILE = Path("data/live_us.json")
US_NEWS_FILE = Path("data/news_us.json")
ANALYSIS_FILE = Path("data/analysis/performance_report.json")
DAILY_BRIEF_FILE = Path("data/brief/daily_brief.json")


def load_us_news_map():
    if not US_NEWS_FILE.exists():
        return {}
    try:
        payload = json.loads(US_NEWS_FILE.read_text(encoding="utf-8"))
        return {
            str(item.get("symbol", "")).upper(): item
            for item in payload.get("items", [])
            if item.get("symbol")
        }
    except Exception:
        return {}

US_NEWS_BY_SYMBOL = load_us_news_map()

def direction_text(v):
    return {"positive":"▲ 상승 촉매","negative":"▼ 위험·악재","neutral":"• 추가 확인"}.get(v,"• 추가 확인")

def direction_css(v):
    return {"positive":"pos","negative":"neg","neutral":"neutral"}.get(v,"neutral")

def fmt_pct(v):
    if v is None:
        return '<span class="price-flat">—</span>'
    cls = "price-up" if v > 0 else "price-down" if v < 0 else "price-flat"
    return f'<span class="{cls}">{v:+.1f}%</span>'

def fmt_ratio(v):
    if v is None:
        return '<span class="price-flat">—</span>'
    # Volume ratio is not inherently positive/negative; use red only when above average,
    # blue when below average, neutral at exactly 1.0x for quick visual scanning.
    cls = "price-up" if v > 1 else "price-down" if v < 1 else "price-flat"
    return f'<span class="{cls}">{v:.1f}배</span>'

def final_score(x):
    m = x.get("material_score") or 0
    c = x.get("market_confirmation")
    h = x.get("overheat_risk")
    p = x.get("price") or {}

    c = 40 if c is None else c
    h = 50 if h is None else h

    is_us = x.get("market") == "US"
    if is_us:
        news = US_NEWS_BY_SYMBOL.get(str(x.get("symbol", "")).upper(), {})
        n = news.get("news_score")
        n = 50 if n is None else n

        # US V2: SEC remains primary; news is a confirmation layer.
        score = m * 0.45 + c * 0.30 + n * 0.25 - h * 0.15

        sec_dir = x.get("direction")
        news_dir = news.get("news_sentiment")
        if sec_dir == "positive" and news_dir == "positive":
            score += 5
        elif sec_dir == "negative" and news_dir == "negative":
            score -= 4
        elif sec_dir in {"positive", "negative"} and news_dir in {"positive", "negative"} and sec_dir != news_dir:
            score -= 7
    else:
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

def render_card(x, top_rank=None):
    dc = direction_css(x.get("direction"))
    grade = x.get("grade","B")
    gc = "grade-a" if grade == "A" else "grade-b"
    values = {k: html.escape(str(x.get(k,"")), quote=True) for k in ("name","symbol","market","event","report_name","reason","published_at","url")}
    is_us = x.get("market") == "US"
    source_name = "SEC EDGAR" if is_us else "OpenDART"
    source_link_text = "SEC 원문 보기 ↗" if is_us else "DART 원문 보기 ↗"
    p = x.get("price") or {}
    confirmation = x.get("market_confirmation")
    overheat = x.get("overheat_risk")
    score = final_score(x)
    news = US_NEWS_BY_SYMBOL.get(str(x.get("symbol", "")).upper(), {}) if is_us else {}
    news_score = news.get("news_score")
    news_sentiment = news.get("news_sentiment", "neutral")
    news_metric_html = (
        f'<div class="metric"><div class="n">{news_score if news_score is not None else "—"}</div><div class="l">뉴스확인</div></div>'
        if is_us else ""
    )

    price_line = ""
    if p:
        price_line = (
            f'<div class="price-line">최근일 {fmt_pct(p.get("day_change_pct"))} · '
            f'5일 {fmt_pct(p.get("five_day_change_pct"))} · '
            f'거래량 {fmt_ratio(p.get("volume_ratio_20d"))} · '
            f'20일 고점 대비 {fmt_pct(p.get("distance_20d_high_pct"))}</div>'
        )

    news_html = ""
    if is_us and news:
        sentiment_label = {
            "positive": "긍정",
            "negative": "부정",
            "neutral": "중립",
        }.get(news_sentiment, "중립")
        sentiment_class = {
            "positive": "pos",
            "negative": "neg",
            "neutral": "neutral",
        }.get(news_sentiment, "neutral")

        links = []
        for article in (news.get("articles") or [])[:3]:
            title = html.escape(str(article.get("title", "")), quote=True)
            url = html.escape(str(article.get("url", "")), quote=True)
            source = html.escape(str(article.get("source", "")), quote=True)
            if not title:
                continue
            source_html = f' <span class="news-meta">· {source}</span>' if source else ""
            if url:
                links.append(f'<a class="news-item" href="{url}" target="_blank">• {title}{source_html}</a>')
            else:
                links.append(f'<div class="news-item">• {title}{source_html}</div>')

        articles_html = "".join(links) if links else '<div class="news-meta">최근 연결된 뉴스 제목이 없습니다.</div>'
        score_text = news_score if news_score is not None else "—"
        news_html = (
            f'<div class="news-box">'
            f'<div class="news-head"><div class="news-title">관련 뉴스</div>'
            f'<div class="news-score {sentiment_class}">뉴스확인 {score_text} · {sentiment_label}</div></div>'
            f'{articles_html}</div>'
        )

    rank_html = f'<span class="top-rank">#{top_rank}</span>' if top_rank else ""
    card_class = "top-card" if top_rank else "stock-card"

    st.markdown(f"""
    <div class="{card_class}">
      <div class="card-top"><div>
        <div class="stock-name">{rank_html}{values["name"]}</div>
        <div class="symbol">{values["symbol"]} · {values["market"]} · <span class="{dc}">{direction_text(x.get("direction"))}</span></div>
      </div><div class="grade {gc}">{grade}급</div></div>
      <div class="event">{values["event"]}</div><div class="summary">{values["report_name"]}</div>
      <div class="metrics{" us-five" if is_us else ""}"><div class="metric"><div class="n">{score}</div><div class="l">최종점수</div></div><div class="metric"><div class="n">{x.get("material_score","—")}</div><div class="l">{"SEC 중요도" if is_us else "공시 중요도"}</div></div><div class="metric"><div class="n">{confirmation if confirmation is not None else "—"}</div><div class="l">시장확인</div></div>{news_metric_html}<div class="metric"><div class="n">{overheat if overheat is not None else "—"}</div><div class="l">과열위험</div></div></div>
      {price_line}
      {news_html}
      <div class="reason">왜 보는가 · {values["reason"]}</div>
      <div class="meta">{source_name} · {values["published_at"]}</div>
      <a class="source-link" href="{values["url"]}" target="_blank">{source_link_text}</a>
    </div>
    """, unsafe_allow_html=True)


ET = ZoneInfo("America/New_York")

def parse_iso_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None

def file_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def age_hours(dt, now_dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=now_dt.tzinfo)
    try:
        return (now_dt.astimezone(dt.tzinfo) - dt).total_seconds() / 3600
    except Exception:
        return None

def status_item(label, dt, now_dt, ok_hours, warn_hours, wait_text=None):
    if dt is None:
        return label, "데이터 없음", "health-bad"

    age = age_hours(dt, now_dt)
    if age is None:
        return label, "시간 확인 불가", "health-warn"

    local = dt.astimezone(KST)
    shown = local.strftime("%m-%d %H:%M")

    if wait_text:
        return label, f"{shown} · {wait_text}", "health-wait"
    if age <= ok_hours:
        return label, f"{shown} · 정상", "health-ok"
    if age <= warn_hours:
        return label, f"{shown} · 지연", "health-warn"
    return label, f"{shown} · 오래됨", "health-bad"

def render_health_monitor():
    now_kst = datetime.now(KST)
    now_et = datetime.now(ET)

    kr = file_json(LIVE_FILE)
    us = file_json(US_LIVE_FILE)
    news = file_json(US_NEWS_FILE)
    kr_val = file_json(VALIDATION_FILE)
    us_val = file_json(US_VALIDATION_FILE)

    kr_dt = parse_iso_dt(kr.get("generated_at"))
    us_dt = parse_iso_dt(us.get("generated_at"))
    news_dt = parse_iso_dt(news.get("generated_at"))
    kr_eval_dt = parse_iso_dt(kr_val.get("updated_at"))
    us_eval_dt = parse_iso_dt(us_val.get("updated_at"))

    weekday_et = now_et.weekday() < 5
    us_session_openish = weekday_et and 7 <= now_et.hour <= 18

    items = [
        status_item("한국 공시·가격", kr_dt, now_kst, 8, 20),
        status_item(
            "미국 SEC",
            us_dt,
            now_kst,
            8 if us_session_openish else 24,
            18 if us_session_openish else 48,
        ),
        status_item(
            "미국 뉴스",
            news_dt,
            now_kst,
            8 if us_session_openish else 24,
            18 if us_session_openish else 48,
        ),
    ]

    kr_eval_count = (kr_val.get("summary") or {}).get("evaluated_count", 0)
    us_eval_count = (us_val.get("summary") or {}).get("evaluated_count", 0)

    if kr_eval_dt:
        label, value, cls = status_item("한국 성과", kr_eval_dt, now_kst, 36, 72)
        value += f" · {kr_eval_count}건"
    else:
        label, value, cls = "한국 성과", f"평가 대기 · {kr_eval_count}건", "health-wait"
    items.append((label, value, cls))

    if us_eval_dt:
        # 0 evaluated on the first snapshot is normal.
        label, value, cls = status_item("미국 성과", us_eval_dt, now_kst, 36, 72)
        if us_eval_count == 0:
            value += " · 다음 거래일 대기"
            cls = "health-wait"
        else:
            value += f" · {us_eval_count}건"
    else:
        label, value, cls = "미국 성과", "평가 대기", "health-wait"
    items.append((label, value, cls))

    cards = "".join(
        f'<div class="health-item"><div class="health-k">{html.escape(label)}</div>'
        f'<div class="health-v {cls}">{html.escape(value)}</div></div>'
        for label, value, cls in items
    )

    st.markdown(
        f'<div class="health-wrap"><div class="health-grid">{cards}</div></div>',
        unsafe_allow_html=True,
    )


def render_analysis_group(title, groups):
    st.markdown(f'<div class="section-title">{html.escape(title)}</div>', unsafe_allow_html=True)

    if not groups:
        st.markdown('<div class="empty">아직 이 구간을 분석할 평가 데이터가 없습니다.</div>', unsafe_allow_html=True)
        return

    for g in groups:
        label = html.escape(str(g.get("label", "—")))
        count = g.get("count", 0)
        sample = html.escape(str(g.get("sample_status", "표본 부족")))
        win = g.get("close_win_rate_pct")
        avg_close = g.get("avg_close_return_pct")
        hit3 = g.get("high_hit_3pct_rate_pct")

        def pct_text(v, signed=False):
            if v is None:
                return "—"
            return f"{v:+.2f}%" if signed else f"{v:.1f}%"

        avg_class = "price-flat"
        if avg_close is not None:
            avg_class = "price-up" if avg_close > 0 else "price-down" if avg_close < 0 else "price-flat"

        st.markdown(f"""
        <div class="analysis-row">
          <div class="analysis-row-top">
            <div class="analysis-label">{label}</div>
            <div class="analysis-sample">{sample} · {count}건</div>
          </div>
          <div class="analysis-metrics">
            <div class="analysis-metric"><div class="k">종가 승률</div><div class="v">{pct_text(win)}</div></div>
            <div class="analysis-metric"><div class="k">평균 종가</div><div class="v {avg_class}">{pct_text(avg_close, True)}</div></div>
            <div class="analysis-metric"><div class="k">장중 +3%</div><div class="v">{pct_text(hit3)}</div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

def render_analysis_market(market_key):
    report = file_json(ANALYSIS_FILE)
    market_data = report.get(market_key, {})
    overall = market_data.get("overall", {})

    if not report or not market_data:
        st.markdown('<div class="empty">아직 성과 분석 리포트가 없습니다. Build performance analysis를 실행하세요.</div>', unsafe_allow_html=True)
        return

    count = overall.get("count", 0)
    sample_status = overall.get("sample_status", "표본 부족")
    win = overall.get("close_win_rate_pct")
    avg_close = overall.get("avg_close_return_pct")
    med_close = overall.get("median_close_return_pct")

    def p(v, signed=False):
        if v is None:
            return "—"
        return f"{v:+.2f}%" if signed else f"{v:.1f}%"

    st.markdown(f"""
    <div class="analysis-grid">
      <div class="analysis-card"><div class="k">평가 표본</div><div class="v">{count:,}건</div></div>
      <div class="analysis-card"><div class="k">분석 상태</div><div class="v">{html.escape(str(sample_status))}</div></div>
      <div class="analysis-card"><div class="k">전체 종가 승률</div><div class="v">{p(win)}</div></div>
      <div class="analysis-card"><div class="k">평균 / 중앙값 종가</div><div class="v">{p(avg_close, True)} / {p(med_close, True)}</div></div>
    </div>
    """, unsafe_allow_html=True)

    highlights = market_data.get("highlights", {})
    if highlights:
        st.markdown('<div class="section-title">현재 우수 구간</div>', unsafe_allow_html=True)
        rows = []
        for key, item in highlights.items():
            name_map = {
                "by_rank": "TOP 순위",
                "by_market_confirmation": "시장확인",
                "by_overheat_risk": "과열위험",
                "by_final_score": "최종점수",
                "by_sec_score": "SEC 중요도",
                "by_news_score": "뉴스확인",
                "by_news_sentiment": "뉴스 방향",
            }
            rows.append(
                f'<div class="analysis-card"><div class="k">{name_map.get(key,key)}</div>'
                f'<div class="v">{html.escape(str(item.get("label","—")))} · '
                f'{item.get("avg_close_return_pct","—")}%</div></div>'
            )
        st.markdown(f'<div class="analysis-grid">{"".join(rows)}</div>', unsafe_allow_html=True)

    render_analysis_group("TOP 순위별", market_data.get("by_rank", []))
    render_analysis_group("시장확인 구간별", market_data.get("by_market_confirmation", []))
    render_analysis_group("과열위험 구간별", market_data.get("by_overheat_risk", []))
    render_analysis_group("최종점수 구간별", market_data.get("by_final_score", []))

    if market_key == "us":
        render_analysis_group("SEC 중요도 구간별", market_data.get("by_sec_score", []))
        render_analysis_group("뉴스확인 점수별", market_data.get("by_news_score", []))
        render_analysis_group("뉴스 방향별", market_data.get("by_news_sentiment", []))


def render_daily_brief_market(market_key, title):
    brief = file_json(DAILY_BRIEF_FILE)
    data = brief.get(market_key, {})

    if not data or data.get("status") != "ok":
        st.markdown('<div class="empty">아직 Daily Brief 데이터가 없습니다.</div>', unsafe_allow_html=True)
        return

    strongest = data.get("strongest") or {}
    strongest_name = html.escape(str(strongest.get("name", "—")))
    strongest_score = strongest.get("final_score", "—")

    st.markdown(f"""
    <div class="brief-wrap">
      <div class="section-title">{html.escape(title)}</div>
      <div class="brief-grid">
        <div class="brief-card"><div class="brief-k">새 후보</div><div class="brief-v">{data.get("new_count",0)}개</div></div>
        <div class="brief-card"><div class="brief-k">유지</div><div class="brief-v">{data.get("retained_count",0)}개</div></div>
        <div class="brief-card"><div class="brief-k">탈락</div><div class="brief-v">{data.get("dropped_count",0)}개</div></div>
        <div class="brief-card"><div class="brief-k">TOP #1</div><div class="brief-v">{strongest_name} · {strongest_score}</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if data.get("new"):
        st.markdown('<div class="section-title">오늘 새 후보</div>', unsafe_allow_html=True)
        for item in data.get("new", [])[:5]:
            name = html.escape(str(item.get("name", "")))
            symbol = html.escape(str(item.get("symbol", "")))
            score = item.get("final_score", "—")
            rank = item.get("rank", "—")
            event = html.escape(str(item.get("event", "")))
            st.markdown(f"""
            <div class="brief-item">
              <div class="brief-item-top">
                <div class="brief-name">#{rank} {name}</div>
                <div class="brief-name">{score}</div>
              </div>
              <div class="brief-meta">{symbol} · {event}</div>
            </div>
            """, unsafe_allow_html=True)

    if data.get("retained"):
        st.markdown('<div class="section-title">계속 유지 중</div>', unsafe_allow_html=True)
        for item in data.get("retained", [])[:5]:
            name = html.escape(str(item.get("name", "")))
            symbol = html.escape(str(item.get("symbol", "")))
            rank = item.get("rank", "—")
            prev_rank = item.get("previous_rank", "—")
            score_change = item.get("score_change")
            rank_change = item.get("rank_change")

            rank_txt = ""
            if rank_change is not None:
                rank_txt = f"순위 {'+' if rank_change > 0 else ''}{rank_change}"
            score_txt = ""
            if score_change is not None:
                score_txt = f"점수 {'+' if score_change > 0 else ''}{score_change}"

            extra = " · ".join([x for x in [rank_txt, score_txt] if x]) or "변화 없음"

            st.markdown(f"""
            <div class="brief-item">
              <div class="brief-item-top">
                <div class="brief-name">#{rank} {name}</div>
                <div class="brief-name">전일 #{prev_rank}</div>
              </div>
              <div class="brief-meta">{symbol} · {extra}</div>
            </div>
            """, unsafe_allow_html=True)

    if data.get("dropped"):
        with st.expander(f"오늘 탈락 {data.get('dropped_count',0)}개"):
            for item in data.get("dropped", [])[:10]:
                name = html.escape(str(item.get("name", "")))
                symbol = html.escape(str(item.get("symbol", "")))
                rank = item.get("rank", "—")
                score = item.get("final_score", "—")
                st.markdown(f"**#{rank} {name}** · {symbol} · 이전 점수 {score}")

def render_daily_brief():
    st.markdown('<div class="section-title">Daily Brief</div>', unsafe_allow_html=True)
    st.caption("전날 TOP 스냅샷과 비교한 오늘의 변화입니다.")
    brief_market = st.segmented_control(
        "브리프 시장",
        ["한국", "미국"],
        default="한국",
        label_visibility="collapsed",
    )
    render_daily_brief_market("kr" if brief_market == "한국" else "us", f"{brief_market} 오늘 변화")

now = datetime.now(KST)
st.markdown(f'<div class="hero"><div class="hero-title">StockNewsRadar <span class="live-badge">KR LIVE</span></div><div class="hero-sub">다음 거래일 관찰 후보 · {now.strftime("%Y-%m-%d %H:%M")} KST</div></div>', unsafe_allow_html=True)

view = st.segmented_control("보기", ["레이더", "성과"], default="레이더", label_visibility="collapsed", width="content")

with st.expander("수집 상태"):
    render_health_monitor()

if view == "레이더":
    render_daily_brief()
    market = st.segmented_control("시장",["한국","미국"],default="한국",label_visibility="collapsed", width="content")

if view == "레이더" and market == "한국":
    if not LIVE_FILE.exists():
        st.warning("아직 자동 수집 데이터가 없습니다.")
        st.stop()

    data = json.loads(LIVE_FILE.read_text(encoding="utf-8"))
    candidates = data.get("candidates",[])
    generated = data.get("generated_at","")

    positive = [x for x in candidates if x.get("direction")=="positive"]
    neutral = [x for x in candidates if x.get("direction")=="neutral"]
    negative = [x for x in candidates if x.get("direction")=="negative"]

    positive.sort(key=lambda x:(final_score(x), x.get("published_at","")), reverse=True)
    neutral.sort(key=lambda x:(final_score(x), x.get("published_at","")), reverse=True)
    negative.sort(key=lambda x:(x.get("material_score",0),x.get("published_at","")), reverse=True)

    top_candidates = [
        x for x in positive
        if (x.get("overheat_risk") is None or x.get("overheat_risk") <= 65)
        and (x.get("market_confirmation") is None or x.get("market_confirmation") >= 35)
    ][:7]

    st.markdown(f"""
    <div class="market-strip">
      <div class="market-chip"><div class="k">최근 수집</div><div class="v pos">{generated[5:16].replace("T"," ") if generated else "—"}</div></div>
      <div class="market-chip"><div class="k">가격 확인</div><div class="v">{data.get("price_enriched_count",0):,}건</div></div>
      <div class="market-chip"><div class="k">상승 촉매</div><div class="v pos">{len(positive):,}건</div></div>
      <div class="market-chip"><div class="k">TOP 후보</div><div class="v pos">{len(top_candidates):,}개</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title bucket-positive">내일 우선 관찰 TOP</div>', unsafe_allow_html=True)
    st.caption("공시 중요도 + 시장확인 + 과열위험을 합친 V1 우선순위입니다.")
    if top_candidates:
        for i, item in enumerate(top_candidates, 1):
            render_card(item, top_rank=i)
    else:
        st.markdown('<div class="empty">현재 조건을 통과한 TOP 후보가 없습니다.</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title bucket-positive">상승 촉매 전체</div>', unsafe_allow_html=True)
    if positive:
        for item in positive[:20]:
            render_card(item)
    else:
        st.markdown('<div class="empty">현재 명확한 상승 촉매 후보가 없습니다.</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title bucket-neutral">추가 확인 후보</div>', unsafe_allow_html=True)
    if neutral:
        for item in neutral[:20]:
            render_card(item)

    with st.expander(f"위험·악재 후보 {len(negative)}건 보기"):
        if negative:
            for item in negative[:30]:
                render_card(item)

    with st.expander("TOP 점수 기준"):
        st.markdown("""
- **최종점수 = 공시 중요도 55% + 시장확인 35% - 과열위험 20%**
- 최근 하루 +12% 초과 또는 최근 5일 +20% 초과 시 추가 감점
- 거래량이 20일 평균의 1.2~4배면 소폭 가점
- 과열위험 65 초과 종목은 TOP 후보에서 제외
- 시장확인 35 미만 종목도 TOP 후보에서 제외
- 아직 백테스트 전의 **V1 휴리스틱**이므로 매수 신호가 아니라 조사 우선순위입니다.
        """)
elif view == "레이더" and market == "미국":
    if not US_LIVE_FILE.exists():
        st.markdown('<div class="section-title">미국 시장</div>', unsafe_allow_html=True)
        st.markdown('<div class="empty">아직 미국 SEC 수집 데이터가 없습니다. GitHub Actions의 Collect US SEC radar를 실행하세요.</div>', unsafe_allow_html=True)
    else:
        us_data = json.loads(US_LIVE_FILE.read_text(encoding="utf-8"))
        us_candidates = us_data.get("candidates", [])
        us_generated = us_data.get("generated_at", "")

        us_positive = [x for x in us_candidates if x.get("direction") == "positive"]
        us_neutral = [x for x in us_candidates if x.get("direction") == "neutral"]
        us_negative = [x for x in us_candidates if x.get("direction") == "negative"]

        us_positive.sort(key=lambda x:(final_score(x), x.get("published_at","")), reverse=True)
        us_neutral.sort(key=lambda x:(final_score(x), x.get("published_at","")), reverse=True)
        us_negative.sort(key=lambda x:(x.get("material_score",0), x.get("published_at","")), reverse=True)

        us_top = [
            x for x in us_positive
            if x.get("price")
            and (x.get("overheat_risk") is None or x.get("overheat_risk") <= 65)
            and (x.get("market_confirmation") is None or x.get("market_confirmation") >= 35)
        ][:7]

        st.markdown(f"""
        <div class="market-strip">
          <div class="market-chip"><div class="k">SEC 후보</div><div class="v">{us_data.get("candidate_count",0):,}건</div></div>
          <div class="market-chip"><div class="k">가격 확인</div><div class="v">{us_data.get("price_enriched_count",0):,}건</div></div>
          <div class="market-chip"><div class="k">상승 촉매</div><div class="v pos">{len(us_positive):,}건</div></div>
          <div class="market-chip"><div class="k">TOP 후보</div><div class="v pos">{len(us_top):,}개</div></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="section-title bucket-positive">미국 우선 관찰 TOP</div>', unsafe_allow_html=True)
        st.caption("SEC 공시 + 가격·거래량 + 뉴스확인 + 과열위험을 합친 미국 V2 우선순위입니다.")
        if us_top:
            for i, item in enumerate(us_top, 1):
                render_card(item, top_rank=i)
        else:
            st.markdown('<div class="empty">현재 조건을 통과한 미국 상승 촉매 TOP 후보가 없습니다.</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-title bucket-positive">상승 촉매 전체</div>', unsafe_allow_html=True)
        if us_positive:
            for item in us_positive[:20]:
                render_card(item)
        else:
            st.markdown('<div class="empty">현재 명확한 미국 상승 촉매 후보가 없습니다.</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-title bucket-neutral">추가 확인 후보</div>', unsafe_allow_html=True)
        st.caption("10-Q, 10-K, 13D/13G 등은 수치와 세부 내용을 추가 확인해야 방향을 판단할 수 있습니다.")
        if us_neutral:
            for item in us_neutral[:20]:
                render_card(item)
        else:
            st.markdown('<div class="empty">추가 확인 후보가 없습니다.</div>', unsafe_allow_html=True)

        with st.expander(f"위험·희석 후보 {len(us_negative)}건 보기"):
            if us_negative:
                for item in us_negative[:30]:
                    render_card(item)
            else:
                st.markdown('<div class="empty">현재 위험·희석 후보가 없습니다.</div>', unsafe_allow_html=True)

        with st.expander("미국 레이더 V1 기준"):
            st.markdown("""
- **8-K / 6-K**: 실적·계약·자사주·배당·승인 등 키워드가 확인되면 상승 촉매 후보로 분류합니다.
- **S-3 / S-3ASR / 424B5**: 증권 발행 및 희석 가능성 때문에 위험 후보로 우선 분류합니다.
- **10-Q / 10-K / 13D / 13G**: 세부 내용에 따라 방향이 달라질 수 있어 추가 확인 후보입니다.
- **미국 V2 최종점수**는 SEC 중요도 45% + 시장확인 30% + 뉴스확인 25% - 과열위험 15%를 기본으로 사용합니다.\n- SEC 방향과 뉴스 방향이 모두 긍정이면 추가 가점, 서로 충돌하면 감점합니다.\n- `시장확인`과 `과열위험`은 한국 레이더와 같은 가격·거래량 휴리스틱을 사용합니다.
- SEC 키워드 분류는 아직 문서 의미를 완전히 이해하는 AI 분석이 아니므로 **원문 확인이 필요합니다.**
            """)

elif view == "성과":
    st.markdown('<div class="section-title">TOP 후보 검증 성과</div>', unsafe_allow_html=True)
    st.caption("매일 저장된 TOP 후보를 다음 거래일 실제 시가·고가·저가·종가와 비교한 누적 검증 결과입니다.")

    perf_market = st.segmented_control(
        "성과 시장",
        ["한국", "미국"],
        default="한국",
        label_visibility="collapsed",
    )

    perf_view = st.segmented_control(
        "성과 보기",
        ["요약", "분석"],
        default="요약",
        label_visibility="collapsed",
    )

    if perf_view == "분석":
        render_analysis_market("kr" if perf_market == "한국" else "us")
    elif perf_market == "한국":
        if not VALIDATION_FILE.exists():
            st.markdown('<div class="empty">아직 한국 검증 결과 파일이 없습니다.</div>', unsafe_allow_html=True)
        else:
            validation = json.loads(VALIDATION_FILE.read_text(encoding="utf-8"))
            records = validation.get("records", [])
            summary = validation.get("summary", {})
            evaluated = [r for r in records if r.get("status") == "evaluated"]

            def perf_pct(v):
                if v is None:
                    return '<span class="price-flat">—</span>'
                cls = "price-up" if v > 0 else "price-down" if v < 0 else "price-flat"
                return f'<span class="{cls}">{v:+.2f}%</span>'

            st.markdown(f"""
            <div class="perf-grid">
              <div class="perf-box"><div class="k">평가 완료</div><div class="v">{summary.get("evaluated_count",0):,}건</div></div>
              <div class="perf-box"><div class="k">종가 승률</div><div class="v">{summary.get("close_win_rate_pct") if summary.get("close_win_rate_pct") is not None else "—"}{"" if summary.get("close_win_rate_pct") is None else "%"}</div></div>
              <div class="perf-box"><div class="k">장중 +3% 도달률</div><div class="v">{summary.get("high_hit_3pct_rate_pct") if summary.get("high_hit_3pct_rate_pct") is not None else "—"}{"" if summary.get("high_hit_3pct_rate_pct") is None else "%"}</div></div>
              <div class="perf-box"><div class="k">평균 종가 수익률</div><div class="v">{perf_pct(summary.get("avg_close_return_pct"))}</div></div>
            </div>
            """, unsafe_allow_html=True)

            if not evaluated:
                st.markdown('<div class="empty">아직 다음 거래일 평가가 완료된 한국 후보가 없습니다.</div>', unsafe_allow_html=True)
            else:
                top1 = [r for r in evaluated if r.get("rank") == 1]
                if top1:
                    top1_win = [r for r in top1 if (r.get("next_close_pct") or 0) > 0]
                    top1_avg = sum(r.get("next_close_pct") or 0 for r in top1) / len(top1)
                    st.markdown(f"""
                    <div class="perf-grid">
                      <div class="perf-box"><div class="k">TOP #1 종가 승률</div><div class="v">{len(top1_win)/len(top1)*100:.1f}%</div></div>
                      <div class="perf-box"><div class="k">TOP #1 평균 종가</div><div class="v">{perf_pct(top1_avg)}</div></div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown('<div class="section-title">최근 한국 평가 결과</div>', unsafe_allow_html=True)
                for r in evaluated[:30]:
                    rank = r.get("rank","—")
                    name = html.escape(str(r.get("name","")), quote=True)
                    symbol = html.escape(str(r.get("symbol","")), quote=True)
                    signal_date = html.escape(str(r.get("signal_date","")), quote=True)
                    next_date = html.escape(str(r.get("next_trade_date","")), quote=True)
                    score = r.get("final_score","—")
                    st.markdown(f"""
                    <div class="perf-row">
                      <div class="perf-row-top">
                        <div><span class="perf-rank">#{rank}</span> <span class="perf-name">{name}</span></div>
                        <div class="perf-small">점수 {score}</div>
                      </div>
                      <div class="perf-small">{symbol} · 신호 {signal_date} → 평가 {next_date}</div>
                      <div class="perf-returns">
                        <div class="perf-return"><div class="k">시가 갭</div><div class="v">{perf_pct(r.get("gap_open_pct"))}</div></div>
                        <div class="perf-return"><div class="k">장중 고가</div><div class="v">{perf_pct(r.get("next_high_pct"))}</div></div>
                        <div class="perf-return"><div class="k">종가</div><div class="v">{perf_pct(r.get("next_close_pct"))}</div></div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

    else:
        if not US_VALIDATION_FILE.exists():
            st.markdown('<div class="empty">아직 미국 검증 결과 파일이 없습니다.</div>', unsafe_allow_html=True)
        else:
            validation = json.loads(US_VALIDATION_FILE.read_text(encoding="utf-8"))
            records = validation.get("records", [])
            summary = validation.get("summary", {})
            evaluated = [r for r in records if r.get("status") == "evaluated"]

            def us_perf_pct(v):
                if v is None:
                    return '<span class="price-flat">—</span>'
                cls = "price-up" if v > 0 else "price-down" if v < 0 else "price-flat"
                return f'<span class="{cls}">{v:+.2f}%</span>'

            st.markdown(f"""
            <div class="perf-grid">
              <div class="perf-box"><div class="k">평가 완료</div><div class="v">{summary.get("evaluated_count",0):,}건</div></div>
              <div class="perf-box"><div class="k">종가 승률</div><div class="v">{summary.get("close_win_rate_pct") if summary.get("close_win_rate_pct") is not None else "—"}{"" if summary.get("close_win_rate_pct") is None else "%"}</div></div>
              <div class="perf-box"><div class="k">장중 +3% 도달률</div><div class="v">{summary.get("high_hit_3pct_rate_pct") if summary.get("high_hit_3pct_rate_pct") is not None else "—"}{"" if summary.get("high_hit_3pct_rate_pct") is None else "%"}</div></div>
              <div class="perf-box"><div class="k">장중 +5% 도달률</div><div class="v">{summary.get("high_hit_5pct_rate_pct") if summary.get("high_hit_5pct_rate_pct") is not None else "—"}{"" if summary.get("high_hit_5pct_rate_pct") is None else "%"}</div></div>
              <div class="perf-box"><div class="k">평균 시가 갭</div><div class="v">{us_perf_pct(summary.get("avg_gap_open_pct"))}</div></div>
              <div class="perf-box"><div class="k">평균 종가 수익률</div><div class="v">{us_perf_pct(summary.get("avg_close_return_pct"))}</div></div>
              <div class="perf-box"><div class="k">TOP #1 종가 승률</div><div class="v">{summary.get("top1_close_win_rate_pct") if summary.get("top1_close_win_rate_pct") is not None else "—"}{"" if summary.get("top1_close_win_rate_pct") is None else "%"}</div></div>
              <div class="perf-box"><div class="k">TOP #1 평균 종가</div><div class="v">{us_perf_pct(summary.get("top1_avg_close_return_pct"))}</div></div>
            </div>
            """, unsafe_allow_html=True)

            if not evaluated:
                st.markdown('<div class="empty">아직 다음 거래일 평가가 완료된 미국 후보가 없습니다. 첫 스냅샷의 다음 미국 거래일 장 종료 후 수치가 채워집니다.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="section-title">최근 미국 평가 결과</div>', unsafe_allow_html=True)
                for r in evaluated[:30]:
                    rank = r.get("rank","—")
                    name = html.escape(str(r.get("name","")), quote=True)
                    symbol = html.escape(str(r.get("symbol","")), quote=True)
                    signal_date = html.escape(str(r.get("signal_date","")), quote=True)
                    next_date = html.escape(str(r.get("next_trade_date","")), quote=True)
                    score = r.get("final_score","—")
                    sec_score = r.get("material_score","—")
                    market_score = r.get("market_confirmation","—")
                    news_score = r.get("news_score","—")
                    heat = r.get("overheat_risk","—")

                    st.markdown(f"""
                    <div class="perf-row">
                      <div class="perf-row-top">
                        <div><span class="perf-rank">#{rank}</span> <span class="perf-name">{name}</span></div>
                        <div class="perf-small">V2 점수 {score}</div>
                      </div>
                      <div class="perf-small">{symbol} · SEC {sec_score} · 시장 {market_score} · 뉴스 {news_score} · 과열 {heat}</div>
                      <div class="perf-small">신호 {signal_date} → 평가 {next_date}</div>
                      <div class="perf-returns">
                        <div class="perf-return"><div class="k">시가 갭</div><div class="v">{us_perf_pct(r.get("gap_open_pct"))}</div></div>
                        <div class="perf-return"><div class="k">장중 고가</div><div class="v">{us_perf_pct(r.get("next_high_pct"))}</div></div>
                        <div class="perf-return"><div class="k">종가</div><div class="v">{us_perf_pct(r.get("next_close_pct"))}</div></div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

    with st.expander("성과 해석 기준"):
        st.markdown("""
- **종가 승률**: 다음 거래일 종가가 스냅샷 기준 종가보다 높은 비율입니다.
- **장중 +3% / +5% 도달률**: 다음 거래일 고가가 기준 종가 대비 해당 수익률 이상 도달한 비율입니다.
- **평균 시가 갭**: 다음 거래일 시가가 스냅샷 기준 종가에서 얼마나 벌어져 시작했는지의 평균입니다.
- **TOP #1 성적**: 매일 최종점수가 가장 높았던 한 종목만 따로 집계합니다.
- 미국 성과는 현재 **SEC + 시장확인 + 뉴스확인 + 과열위험**을 결합한 V2 점수를 검증합니다.
- 데이터가 적을 때는 통계적 의미가 약하므로 수십 건 이상 쌓인 뒤 점수 가중치를 조정하는 게 좋습니다.
        """)

st.markdown('<div class="notice">자동매매가 아니라 다음 거래일에 먼저 조사할 종목을 좁히는 리서치 도구입니다.</div>', unsafe_allow_html=True)
