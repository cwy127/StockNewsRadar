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
.stApp{background:var(--bg);color:var(--text)}.block-container{max-width:760px;padding-top:5rem;padding-left:.85rem;padding-right:.85rem;padding-bottom:5rem}
.hero{margin:.2rem 0 1rem}.hero-title{font-size:1.9rem;font-weight:780;line-height:1.05}.hero-sub{color:var(--muted);font-size:.86rem;margin-top:.35rem}
.live-badge{display:inline-block;padding:.19rem .48rem;border-radius:999px;background:rgba(57,217,138,.13);color:var(--green);font-size:.67rem;font-weight:800;margin-left:.35rem;vertical-align:middle}
.market-strip{display:grid;grid-template-columns:repeat(2,1fr);gap:.5rem;margin-bottom:1rem}.market-chip{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:.75rem .8rem}.market-chip .k{color:var(--muted);font-size:.72rem}.market-chip .v{font-size:.92rem;font-weight:700;margin-top:.08rem}
.pos{color:var(--green)}.neg{color:var(--red)}.warn{color:var(--yellow)}.neutral{color:var(--text)}
.stock-card{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:18px;padding:.95rem 1rem;margin:.7rem 0}.card-top{display:flex;justify-content:space-between;gap:.7rem;align-items:flex-start}.stock-name{font-size:1.05rem;font-weight:750}.symbol{color:var(--muted);font-size:.78rem;margin-top:.08rem}.grade{border-radius:999px;padding:.25rem .55rem;font-size:.74rem;font-weight:800}.grade-a{background:rgba(57,217,138,.14);color:var(--green)}.grade-b{background:rgba(245,196,81,.14);color:var(--yellow)}
.event{margin-top:.72rem;font-weight:700;font-size:.94rem}.summary{color:#c7ccd4;font-size:.83rem;line-height:1.45;margin-top:.28rem}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem;margin-top:.8rem}.metric{background:#101318;border-radius:11px;padding:.55rem .45rem;text-align:center}.metric .n{font-size:1rem;font-weight:800}.metric .l{color:var(--muted);font-size:.65rem;margin-top:.05rem}
.price-line{margin-top:.6rem;font-size:.76rem;color:#aeb5bf;line-height:1.45}.reason{border-top:1px solid var(--line);margin-top:.75rem;padding-top:.65rem;font-size:.78rem;color:#cbd1d8}.meta{color:#7f8792;font-size:.68rem;margin-top:.45rem}.source-link{display:inline-block;margin-top:.55rem;color:#8ab4ff!important;text-decoration:none;font-size:.76rem;font-weight:700}
.section-title{font-size:1.05rem;font-weight:800;margin-top:1.15rem;margin-bottom:.4rem}.notice{background:#11151a;border:1px solid var(--line);border-radius:14px;padding:.8rem;color:#aeb5bf;font-size:.76rem;line-height:1.45;margin-top:1rem}.empty{background:#11151a;border:1px solid var(--line);border-radius:14px;padding:1rem;color:#aeb5bf;font-size:.82rem;line-height:1.5}
.bucket-positive{border-left:3px solid var(--green);padding-left:.65rem}.bucket-neutral{border-left:3px solid var(--yellow);padding-left:.65rem}.bucket-negative{border-left:3px solid var(--red);padding-left:.65rem}
div[data-testid="stSegmentedControl"] button{border-radius:12px!important}@media(max-width:600px){.block-container{padding-top:5rem}.hero-title{font-size:1.72rem}}
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

def render_card(x):
    dc = direction_css(x.get("direction"))
    grade = x.get("grade","B")
    gc = "grade-a" if grade == "A" else "grade-b"
    values = {k: html.escape(str(x.get(k,"")), quote=True) for k in ("name","symbol","market","event","report_name","reason","published_at","url")}
    p = x.get("price") or {}
    confirmation = x.get("market_confirmation")
    overheat = x.get("overheat_risk")
    conf_text = str(confirmation) if confirmation is not None else "—"
    heat_text = str(overheat) if overheat is not None else "—"

    price_line = ""
    if p:
        price_line = (
            f'<div class="price-line">최근일 {fmt_pct(p.get("day_change_pct"))} · '
            f'5일 {fmt_pct(p.get("five_day_change_pct"))} · '
            f'거래량 {fmt_ratio(p.get("volume_ratio_20d"))} · '
            f'20일 고점 대비 {fmt_pct(p.get("distance_20d_high_pct"))}</div>'
        )

    st.markdown(f"""
    <div class="stock-card">
      <div class="card-top"><div><div class="stock-name">{values["name"]}</div>
      <div class="symbol">{values["symbol"]} · {values["market"]} · <span class="{dc}">{direction_text(x.get("direction"))}</span></div></div>
      <div class="grade {gc}">{grade}급</div></div>
      <div class="event">{values["event"]}</div><div class="summary">{values["report_name"]}</div>
      <div class="metrics">
        <div class="metric"><div class="n">{x.get("material_score","—")}</div><div class="l">공시 중요도</div></div>
        <div class="metric"><div class="n">{conf_text}</div><div class="l">시장확인</div></div>
        <div class="metric"><div class="n">{heat_text}</div><div class="l">과열위험</div></div>
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

    # Within each bucket, prefer strong material + confirmation and low overheat.
    def rank(x):
        m = x.get("material_score") or 0
        c = x.get("market_confirmation")
        h = x.get("overheat_risk")
        c = c if c is not None else 40
        h = h if h is not None else 50
        return (m * .55 + c * .35 - h * .20, x.get("published_at",""))

    positive.sort(key=rank, reverse=True)
    neutral.sort(key=rank, reverse=True)
    negative.sort(key=lambda x:(x.get("material_score",0),x.get("published_at","")), reverse=True)

    st.markdown(f"""
    <div class="market-strip">
      <div class="market-chip"><div class="k">최근 수집</div><div class="v pos">{generated[5:16].replace("T"," ") if generated else "—"}</div></div>
      <div class="market-chip"><div class="k">가격 확인</div><div class="v">{data.get("price_enriched_count",0):,}건</div></div>
      <div class="market-chip"><div class="k">상승 촉매</div><div class="v pos">{len(positive):,}건</div></div>
      <div class="market-chip"><div class="k">위험·악재</div><div class="v neg">{len(negative):,}건</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title bucket-positive">상승 촉매 후보</div>', unsafe_allow_html=True)
    st.caption("공시 중요도 + 가격·거래량 확인 + 과열위험을 함께 보고 정렬합니다.")
    if positive:
        for item in positive[:20]: render_card(item)
    else:
        st.markdown('<div class="empty">현재 명확한 상승 촉매 후보가 없습니다.</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title bucket-neutral">추가 확인 후보</div>', unsafe_allow_html=True)
    if neutral:
        for item in neutral[:20]: render_card(item)
    else:
        st.markdown('<div class="empty">추가 확인 후보가 없습니다.</div>', unsafe_allow_html=True)

    with st.expander(f"위험·악재 후보 {len(negative)}건 보기"):
        if negative:
            for item in negative[:30]: render_card(item)
        else:
            st.markdown('<div class="empty">위험·악재 후보가 없습니다.</div>', unsafe_allow_html=True)

    with st.expander("시장확인 / 과열위험 기준"):
        st.markdown("""
- **시장확인**: 최근 일봉 수익률, 5일 수익률, 20일 평균 대비 거래량을 조합한 초기 휴리스틱 점수입니다.
- **과열위험**: 최근 1일·5일 급등, 극단적인 거래량, 20일 고점 접근도를 조합합니다.
- 이 점수는 아직 **백테스트로 검증되지 않은 V1 가설**입니다.
- Yahoo Finance 한국 KOSPI/KOSDAQ 데이터는 지연 데이터이므로 초단타용 실시간 지표가 아니라 **다음 거래일 후보 선별용**입니다.
        """)
else:
    st.markdown('<div class="section-title">미국 시장</div>', unsafe_allow_html=True)
    st.markdown('<div class="notice">미국 자동수집은 다음 단계에서 연결합니다.</div>', unsafe_allow_html=True)

st.markdown('<div class="notice">자동매매가 아니라 다음 거래일에 먼저 조사할 종목을 좁히는 리서치 도구입니다.</div>', unsafe_allow_html=True)
