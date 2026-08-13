import json
from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="StockNewsRadar",
    page_icon="📡",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ---------- Mobile-first CSS ----------
st.markdown("""
<style>
:root {
    --bg:#0b0d10;
    --card:#15181d;
    --card2:#1b1f25;
    --text:#f4f6f8;
    --muted:#9ca3af;
    --line:#272c34;
    --green:#39d98a;
    --red:#ff6b6b;
    --yellow:#f5c451;
    --blue:#6ea8fe;
}
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Apple SD Gothic Neo", sans-serif;
}
.stApp {
    background: var(--bg);
    color: var(--text);
}
.block-container {
    max-width: 760px;
    padding-top: 1.0rem;
    padding-left: 0.85rem;
    padding-right: 0.85rem;
    padding-bottom: 5rem;
}
h1,h2,h3 { letter-spacing:-0.03em; }
.hero {
    margin: 0.2rem 0 1rem 0;
}
.hero-title {
    font-size: 1.9rem;
    font-weight: 780;
    line-height: 1.05;
}
.hero-sub {
    color: var(--muted);
    font-size: 0.86rem;
    margin-top: 0.35rem;
}
.market-strip {
    display:grid;
    grid-template-columns: repeat(2, 1fr);
    gap:0.5rem;
    margin-bottom:1rem;
}
.market-chip {
    background:var(--card);
    border:1px solid var(--line);
    border-radius:14px;
    padding:0.75rem 0.8rem;
}
.market-chip .k {
    color:var(--muted);
    font-size:0.72rem;
}
.market-chip .v {
    font-size:0.92rem;
    font-weight:700;
    margin-top:0.08rem;
}
.pos { color:var(--green); }
.neg { color:var(--red); }
.warn { color:var(--yellow); }
.neutral { color:var(--text); }
.stock-card {
    background:linear-gradient(180deg, var(--card2), var(--card));
    border:1px solid var(--line);
    border-radius:18px;
    padding:0.95rem 1rem;
    margin:0.7rem 0;
}
.card-top {
    display:flex;
    justify-content:space-between;
    gap:0.7rem;
    align-items:flex-start;
}
.stock-name {
    font-size:1.05rem;
    font-weight:750;
}
.symbol {
    color:var(--muted);
    font-size:0.78rem;
    margin-top:0.08rem;
}
.grade {
    border-radius:999px;
    padding:0.25rem 0.55rem;
    font-size:0.74rem;
    font-weight:800;
}
.grade-a { background:rgba(57,217,138,.14); color:var(--green); }
.grade-b { background:rgba(245,196,81,.14); color:var(--yellow); }
.event {
    margin-top:0.72rem;
    font-weight:700;
    font-size:0.94rem;
}
.summary {
    color:#c7ccd4;
    font-size:0.83rem;
    line-height:1.45;
    margin-top:0.28rem;
}
.metrics {
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:0.4rem;
    margin-top:0.8rem;
}
.metric {
    background:#101318;
    border-radius:11px;
    padding:0.55rem 0.45rem;
    text-align:center;
}
.metric .n { font-size:1rem; font-weight:800; }
.metric .l { color:var(--muted); font-size:0.65rem; margin-top:0.05rem; }
.reason {
    border-top:1px solid var(--line);
    margin-top:0.75rem;
    padding-top:0.65rem;
    font-size:0.78rem;
    color:#cbd1d8;
}
.meta {
    color:#7f8792;
    font-size:0.68rem;
    margin-top:0.45rem;
}
.section-title {
    font-size:1.05rem;
    font-weight:800;
    margin-top:1.15rem;
    margin-bottom:0.4rem;
}
.notice {
    background:#11151a;
    border:1px solid var(--line);
    border-radius:14px;
    padding:0.8rem;
    color:#aeb5bf;
    font-size:0.76rem;
    line-height:1.45;
    margin-top:1rem;
}
div[data-testid="stSegmentedControl"] button {
    border-radius:12px !important;
}
</style>
""", unsafe_allow_html=True)

data = json.loads(Path("data/demo.json").read_text(encoding="utf-8"))

def tone_class(tone):
    return {
        "positive":"pos",
        "negative":"neg",
        "warning":"warn",
        "neutral":"neutral"
    }.get(tone, "neutral")

def render_market_context(items):
    chunks = ['<div class="market-strip">']
    for x in items:
        chunks.append(
            f'<div class="market-chip">'
            f'<div class="k">{x["label"]}</div>'
            f'<div class="v {tone_class(x["tone"])}">{x["value"]}</div>'
            f'</div>'
        )
    chunks.append("</div>")
    st.markdown("".join(chunks), unsafe_allow_html=True)

def render_card(x):
    direction_cls = "pos" if x["direction"] == "positive" else "neg" if x["direction"] == "negative" else "neutral"
    arrow = "▲" if x["direction"] == "positive" else "▼" if x["direction"] == "negative" else "•"
    grade_cls = "grade-a" if x["grade"] == "A" else "grade-b"

    html = f"""
    <div class="stock-card">
      <div class="card-top">
        <div>
          <div class="stock-name">{x["name"]}</div>
          <div class="symbol">{x["symbol"]} · <span class="{direction_cls}">{arrow} {x["status"]}</span></div>
        </div>
        <div class="grade {grade_cls}">{x["grade"]}급</div>
      </div>

      <div class="event">{x["event"]}</div>
      <div class="summary">{x["summary"]}</div>

      <div class="metrics">
        <div class="metric">
          <div class="n">{x["material_score"]}</div>
          <div class="l">재료</div>
        </div>
        <div class="metric">
          <div class="n">{x["confirmation_score"]}</div>
          <div class="l">시장확인</div>
        </div>
        <div class="metric">
          <div class="n">{x["overheat_risk"]}</div>
          <div class="l">과열위험</div>
        </div>
      </div>

      <div class="reason">왜 보는가 · {x["reason"]}</div>
      <div class="meta">{x["source"]} · {x["published_at"]}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# ---------- Header ----------
st.markdown(
    f"""
    <div class="hero">
      <div class="hero-title">StockNewsRadar</div>
      <div class="hero-sub">다음 거래일 관찰 후보 · 업데이트 {data["updated_at"]}</div>
    </div>
    """,
    unsafe_allow_html=True
)

market_label = st.segmented_control(
    "시장",
    options=["한국", "미국"],
    default="한국",
    label_visibility="collapsed"
)
market = "KR" if market_label == "한국" else "US"

st.markdown('<div class="section-title">오늘의 시장 변수</div>', unsafe_allow_html=True)
render_market_context(data["market_context"][market])

candidates = [x for x in data["candidates"] if x["market"] == market]
a_list = [x for x in candidates if x["grade"] == "A"]
b_list = [x for x in candidates if x["grade"] == "B"]

st.markdown('<div class="section-title">A급 후보</div>', unsafe_allow_html=True)
if not a_list:
    st.info("A급 후보 없음")
else:
    for x in a_list:
        render_card(x)

st.markdown('<div class="section-title">B급 / 주의</div>', unsafe_allow_html=True)
if not b_list:
    st.info("B급 후보 없음")
else:
    for x in b_list:
        render_card(x)

with st.expander("전체 판단 기준"):
    st.markdown("""
- **재료점수**: 뉴스/공시 자체의 중요도
- **시장확인**: 가격·거래량이 실제로 반응하는 정도
- **과열위험**: 이미 많이 오른 정도나 추격 위험
- **A급**: 다음 거래일 우선 확인 후보
- **B급**: 재료는 있으나 추가 확인이 필요한 후보

현재 화면은 UI 검증용 데모 데이터입니다.
    """)

st.markdown(
    """
    <div class="notice">
      이 도구는 종목을 자동 매수하는 시스템이 아니라, 다음 거래일에 무엇을 먼저 확인할지 정리하는 리서치 화면입니다.
      실제 버전에서는 공식 공시·뉴스와 가격/거래량 반응을 함께 확인하도록 연결합니다.
    </div>
    """,
    unsafe_allow_html=True
)
