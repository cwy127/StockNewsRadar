import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import streamlit as st

st.set_page_config(page_title="StockNewsRadar", page_icon="📡", layout="centered", initial_sidebar_state="collapsed")

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
div[data-testid="stSegmentedControl"] button{border-radius:12px!important}
@media(max-width:600px){.block-container{padding-top:5rem}.hero-title{font-size:1.72rem}.metrics{grid-template-columns:repeat(2,1fr)}}
</style>
""", unsafe_allow_html=True)

KST = ZoneInfo("Asia/Seoul")
LIVE_FILE = Path("data/live_kr.json")

def direction_text(v):
    return {"positive":"▲ 상승 촉매","negative":"▼ 위험·악재","neutral":"• 추가 확인"}.get(v,"• 추가 확인")

def direction_css(v):
    return {"positive":"pos","negative":"neg","neutral":"neutral"}.get(v,"neutral")

def fmt_pct(v):
    if v is None: return "—"
    return f"{v:+.1f}%"

def fmt_ratio(v):
    if v is None: return "—"
    return f"{v:.1f}배"

def final_score(x):
    m = x.get("material_score") or 0
    c = x.get("market_confirmation")
    h = x.get("overheat_risk")
    p = x.get("price") or {}

    c = 40 if c is None else c
    h = 50 if h is None else h
    score = m * 0.55 + c * 0.35 - h * 0.20

    day = p.get("day_change_pct")
    five = p.get("five_day_change_pct")
    vr = p.get("volume_ratio_20d")

    # Prefer fresh catalysts over already-extended moves.
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
    p = x.get("price") or {}
    confirmation = x.get("market_confirmation")
    overheat = x.get("overheat_risk")
    score = final_score(x)

    price_line = ""
    if p:
        price_line = (
            f'<div class="price-line">최근일 {fmt_pct(p.get("day_change_pct"))} · '
            f'5일 {fmt_pct(p.get("five_day_change_pct"))} · '
            f'거래량 {fmt_ratio(p.get("volume_ratio_20d"))} · '
            f'20일 고점 대비 {fmt_pct(p.get("distance_20d_high_pct"))}</div>'
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
      <div class="metrics">
        <div class="metric"><div class="n">{score}</div><div class="l">최종점수</div></div>
        <div class="metric"><div class="n">{x.get("material_score","—")}</div><div class="l">공시 중요도</div></div>
        <div class="metric"><div class="n">{confirmation if confirmation is not None else "—"}</div><div class="l">시장확인</div></div>
        <div class="metric"><div class="n">{overheat if overheat is not None else "—"}</div><div class="l">과열위험</div></div>
      </div>
      {price_line}
      <div class="reason">왜 보는가 · {values["reason"]}</div>
      <div class="meta">OpenDART · {values["published_at"]}</div>
      <a class="source-link" href="{values["url"]}" target="_blank">DART 원문 보기 ↗</a>
    </div>
    """, unsafe_allow_html=True)

now = datetime.now(KST)
st.markdown(f'<div class="hero"><div class="hero-title">StockNewsRadar <span class="live-badge">KR LIVE</span></div><div class="hero-sub">다음 거래일 관찰 후보 · {now.strftime("%Y-%m-%d %H:%M")} KST</div></div>', unsafe_allow_html=True)

market = st.segmented_control("시장",["한국","미국"],default="한국",label_visibility="collapsed")

if market == "한국":
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
else:
    st.markdown('<div class="section-title">미국 시장</div>', unsafe_allow_html=True)
    st.markdown('<div class="notice">미국 자동수집은 다음 단계에서 연결합니다.</div>', unsafe_allow_html=True)

st.markdown('<div class="notice">자동매매가 아니라 다음 거래일에 먼저 조사할 종목을 좁히는 리서치 도구입니다.</div>', unsafe_allow_html=True)
