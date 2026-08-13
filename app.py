import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

st.set_page_config(
    page_title="StockNewsRadar",
    page_icon="📡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
:root{--bg:#0b0d10;--card:#15181d;--card2:#1b1f25;--text:#f4f6f8;--muted:#9ca3af;--line:#272c34;--green:#39d98a;--red:#ff6b6b;--yellow:#f5c451;--blue:#6ea8fe}
html,body,[class*="css"]{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Apple SD Gothic Neo",sans-serif}
.stApp{background:var(--bg);color:var(--text)}
.block-container{max-width:760px;padding-top:5rem;padding-left:.85rem;padding-right:.85rem;padding-bottom:5rem}
.hero{margin:.2rem 0 1rem}.hero-title{font-size:1.9rem;font-weight:780;line-height:1.05}.hero-sub{color:var(--muted);font-size:.86rem;margin-top:.35rem}
.live-badge{display:inline-block;padding:.19rem .48rem;border-radius:999px;background:rgba(57,217,138,.13);color:var(--green);font-size:.67rem;font-weight:800;margin-left:.35rem;vertical-align:middle}
.market-strip{display:grid;grid-template-columns:repeat(2,1fr);gap:.5rem;margin-bottom:1rem}.market-chip{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:.75rem .8rem}.market-chip .k{color:var(--muted);font-size:.72rem}.market-chip .v{font-size:.92rem;font-weight:700;margin-top:.08rem}
.pos{color:var(--green)}.neg{color:var(--red)}.warn{color:var(--yellow)}.neutral{color:var(--text)}
.stock-card{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:18px;padding:.95rem 1rem;margin:.7rem 0}.card-top{display:flex;justify-content:space-between;gap:.7rem;align-items:flex-start}.stock-name{font-size:1.05rem;font-weight:750}.symbol{color:var(--muted);font-size:.78rem;margin-top:.08rem}.grade{border-radius:999px;padding:.25rem .55rem;font-size:.74rem;font-weight:800}.grade-a{background:rgba(57,217,138,.14);color:var(--green)}.grade-b{background:rgba(245,196,81,.14);color:var(--yellow)}
.event{margin-top:.72rem;font-weight:700;font-size:.94rem}.summary{color:#c7ccd4;font-size:.83rem;line-height:1.45;margin-top:.28rem}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem;margin-top:.8rem}.metric{background:#101318;border-radius:11px;padding:.55rem .45rem;text-align:center}.metric .n{font-size:1rem;font-weight:800}.metric .l{color:var(--muted);font-size:.65rem;margin-top:.05rem}.reason{border-top:1px solid var(--line);margin-top:.75rem;padding-top:.65rem;font-size:.78rem;color:#cbd1d8}.meta{color:#7f8792;font-size:.68rem;margin-top:.45rem}.source-link{display:inline-block;margin-top:.55rem;color:#8ab4ff!important;text-decoration:none;font-size:.76rem;font-weight:700}
.section-title{font-size:1.05rem;font-weight:800;margin-top:1.15rem;margin-bottom:.4rem}.notice{background:#11151a;border:1px solid var(--line);border-radius:14px;padding:.8rem;color:#aeb5bf;font-size:.76rem;line-height:1.45;margin-top:1rem}.empty{background:#11151a;border:1px solid var(--line);border-radius:14px;padding:1rem;color:#aeb5bf;font-size:.82rem;line-height:1.5}
div[data-testid="stSegmentedControl"] button{border-radius:12px!important}
@media(max-width:600px){.block-container{padding-top:5rem}.hero-title{font-size:1.72rem}}
</style>
""", unsafe_allow_html=True)

KST = ZoneInfo("Asia/Seoul")
LIVE_FILE = Path("data/live_kr.json")

def direction_text(value):
    return {
        "positive": "▲ 긍정 가능",
        "negative": "▼ 부정 가능",
        "neutral": "• 방향 확인",
    }.get(value, "• 방향 확인")

def direction_css(value):
    return {
        "positive": "pos",
        "negative": "neg",
        "neutral": "neutral",
    }.get(value, "neutral")

def render_card(x):
    dc = direction_css(x.get("direction"))
    grade = x.get("grade", "B")
    gc = "grade-a" if grade == "A" else "grade-b"

    values = {
        k: html.escape(str(x.get(k, "")), quote=True)
        for k in ("name", "symbol", "market", "event", "report_name", "reason", "published_at", "url")
    }

    st.markdown(
        f"""
        <div class="stock-card">
          <div class="card-top">
            <div>
              <div class="stock-name">{values["name"]}</div>
              <div class="symbol">{values["symbol"]} · {values["market"]} · <span class="{dc}">{direction_text(x.get("direction"))}</span></div>
            </div>
            <div class="grade {gc}">{grade}급</div>
          </div>
          <div class="event">{values["event"]}</div>
          <div class="summary">{values["report_name"]}</div>
          <div class="metrics">
            <div class="metric"><div class="n">{x.get("material_score","—")}</div><div class="l">공시 중요도</div></div>
            <div class="metric"><div class="n">—</div><div class="l">시장확인</div></div>
            <div class="metric"><div class="n">—</div><div class="l">과열위험</div></div>
          </div>
          <div class="reason">왜 보는가 · {values["reason"]}</div>
          <div class="meta">OpenDART · {values["published_at"]}</div>
          <a class="source-link" href="{values["url"]}" target="_blank">DART 원문 보기 ↗</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

now = datetime.now(KST)
st.markdown(
    f'<div class="hero"><div class="hero-title">StockNewsRadar <span class="live-badge">KR LIVE</span></div><div class="hero-sub">다음 거래일 관찰 후보 · {now.strftime("%Y-%m-%d %H:%M")} KST</div></div>',
    unsafe_allow_html=True,
)

market = st.segmented_control("시장", ["한국", "미국"], default="한국", label_visibility="collapsed")

if market == "한국":
    if not LIVE_FILE.exists():
        st.warning("아직 자동 수집 데이터가 없습니다. GitHub Actions의 `Collect Korean stock disclosures`를 한 번 수동 실행하세요.")
        st.stop()

    data = json.loads(LIVE_FILE.read_text(encoding="utf-8"))
    candidates = data.get("candidates", [])
    generated = data.get("generated_at", "")
    window = data.get("window", {})

    st.markdown(
        f"""
        <div class="market-strip">
          <div class="market-chip"><div class="k">최근 수집</div><div class="v pos">{generated[5:16].replace("T"," ") if generated else "—"}</div></div>
          <div class="market-chip"><div class="k">검색 기간</div><div class="v">{window.get("start","—")} ~ {window.get("end","—")}</div></div>
          <div class="market-chip"><div class="k">확인한 공시</div><div class="v">{data.get("raw_count",0):,}건</div></div>
          <div class="market-chip"><div class="k">중요 후보</div><div class="v pos">{data.get("candidate_count",0):,}건</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    a_list = [x for x in candidates if x.get("grade") == "A"]
    b_list = [x for x in candidates if x.get("grade") == "B"]

    st.markdown('<div class="section-title">A급 · 우선 확인</div>', unsafe_allow_html=True)
    if a_list:
        for item in a_list[:20]:
            render_card(item)
    else:
        st.markdown('<div class="empty">A급 중요 공시가 없습니다.</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">B급 · 추가 확인</div>', unsafe_allow_html=True)
    if b_list:
        for item in b_list[:30]:
            render_card(item)
    else:
        st.markdown('<div class="empty">B급 후보가 없습니다.</div>', unsafe_allow_html=True)

    with st.expander("현재 단계에서 알아둘 점"):
        st.markdown("""
- 지금은 **OpenDART 공시 중요도**만 자동화했습니다.
- A/B는 매수등급이 아니라 **조사 우선순위**입니다.
- 아직 주가·거래량을 연결하지 않아 `시장확인`, `과열위험`은 비어 있습니다.
- 실적·합병·무상증자처럼 제목만으로 방향을 판단하기 어려운 공시는 `방향 확인`으로 표시합니다.
        """)
else:
    st.markdown('<div class="section-title">미국 시장</div>', unsafe_allow_html=True)
    st.markdown('<div class="notice">미국 자동수집은 다음 단계에서 SEC EDGAR + 미국 뉴스로 연결합니다.</div>', unsafe_allow_html=True)

st.markdown('<div class="notice">자동매매가 아니라 다음 거래일에 먼저 조사할 종목을 좁히는 리서치 도구입니다.</div>', unsafe_allow_html=True)
