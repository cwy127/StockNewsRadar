import json
import html
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

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
.stock-card{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:18px;padding:.95rem 1rem;margin:.7rem 0}.card-top{display:flex;justify-content:space-between;gap:.7rem;align-items:flex-start}.stock-name{font-size:1.05rem;font-weight:750}.symbol{color:var(--muted);font-size:.78rem;margin-top:.08rem}.grade{border-radius:999px;padding:.25rem .55rem;font-size:.74rem;font-weight:800}.grade-a{background:rgba(57,217,138,.14);color:var(--green)}.grade-b{background:rgba(245,196,81,.14);color:var(--yellow)}.grade-watch{background:rgba(110,168,254,.13);color:var(--blue)}
.event{margin-top:.72rem;font-weight:700;font-size:.94rem}.summary{color:#c7ccd4;font-size:.83rem;line-height:1.45;margin-top:.28rem}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem;margin-top:.8rem}.metric{background:#101318;border-radius:11px;padding:.55rem .45rem;text-align:center}.metric .n{font-size:1rem;font-weight:800}.metric .l{color:var(--muted);font-size:.65rem;margin-top:.05rem}.reason{border-top:1px solid var(--line);margin-top:.75rem;padding-top:.65rem;font-size:.78rem;color:#cbd1d8}.meta{color:#7f8792;font-size:.68rem;margin-top:.45rem}.source-link{display:inline-block;margin-top:.55rem;color:#8ab4ff!important;text-decoration:none;font-size:.76rem;font-weight:700}
.section-title{font-size:1.05rem;font-weight:800;margin-top:1.15rem;margin-bottom:.4rem}.notice{background:#11151a;border:1px solid var(--line);border-radius:14px;padding:.8rem;color:#aeb5bf;font-size:.76rem;line-height:1.45;margin-top:1rem}.empty{background:#11151a;border:1px solid var(--line);border-radius:14px;padding:1rem;color:#aeb5bf;font-size:.82rem;line-height:1.5}
.status-row{display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem;margin:.65rem 0 1rem}.status-chip{background:#11151a;border:1px solid var(--line);border-radius:12px;padding:.6rem;text-align:center}.status-chip .name{font-size:.69rem;color:var(--muted)}.status-chip .state{font-size:.78rem;font-weight:800;margin-top:.12rem}
div[data-testid="stSegmentedControl"] button{border-radius:12px!important}
@media(max-width:600px){.block-container{padding-top:5rem}.hero-title{font-size:1.72rem}}
</style>
""", unsafe_allow_html=True)

KST = ZoneInfo("Asia/Seoul")
DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
MARKETS = {"Y": "KOSPI", "K": "KOSDAQ", "N": "KONEX"}

EVENT_RULES = [
    ("상장폐지", 98, "negative", "상장폐지 관련", "기업 존속·거래 가능성에 직접 영향을 줄 수 있는 공시"),
    ("횡령", 96, "negative", "횡령·배임", "재무·지배구조 위험이 큰 사건"),
    ("배임", 96, "negative", "횡령·배임", "재무·지배구조 위험이 큰 사건"),
    ("영업정지", 94, "negative", "영업정지", "본업의 매출·현금흐름에 직접 영향을 줄 수 있는 사건"),
    ("유상증자결정", 90, "negative", "유상증자", "기존 주주 지분 희석 가능성이 있는 자금조달"),
    ("전환사채권발행결정", 88, "negative", "전환사채 발행", "향후 주식 전환에 따른 희석 가능성이 있는 자금조달"),
    ("신주인수권부사채권발행결정", 88, "negative", "BW 발행", "향후 신주 발행에 따른 희석 가능성이 있는 자금조달"),
    ("합병결정", 90, "neutral", "합병 결정", "기업가치·지배구조에 큰 변화를 줄 수 있어 세부 조건 확인 필요"),
    ("분할결정", 86, "neutral", "분할 결정", "사업·지배구조 변경이 큰 사건이라 세부 조건 확인 필요"),
    ("타법인주식및출자증권양수결정", 84, "neutral", "대규모 투자·인수", "자산 및 사업구조 변화 가능성이 있는 사건"),
    ("단일판매ㆍ공급계약체결", 86, "positive", "공급계약 체결", "매출로 연결될 수 있는 직접적인 수주·계약 공시"),
    ("단일판매·공급계약체결", 86, "positive", "공급계약 체결", "매출로 연결될 수 있는 직접적인 수주·계약 공시"),
    ("자기주식소각결정", 86, "positive", "자사주 소각", "유통주식수 감소에 직접 영향을 주는 주주환원"),
    ("자기주식취득결정", 82, "positive", "자사주 취득", "회사가 직접 주식을 매입하는 주주환원"),
    ("무상증자결정", 78, "neutral", "무상증자", "주식 수 변화가 큰 사건이지만 경제적 가치 증가와 동일하지 않아 세부 확인 필요"),
    ("최대주주변경", 82, "neutral", "최대주주 변경", "지배구조 변화가 발생한 사건"),
    ("영업(잠정)실적", 76, "neutral", "잠정 실적", "실적 수치와 시장 예상치를 비교해야 방향을 판단할 수 있음"),
    ("매출액또는손익구조30", 76, "neutral", "실적 변동", "실제 증가·감소 폭을 원문에서 확인해야 함"),
    ("주요사항보고서", 68, "neutral", "주요사항보고", "중요 공시 유형이지만 세부 내용 확인 필요"),
]

def compact(text):
    return "".join((text or "").split())

def classify_disclosure(report_name):
    cleaned = compact(report_name)
    for keyword, score, direction, label, reason in EVENT_RULES:
        if compact(keyword) in cleaned:
            return {"score": score, "direction": direction, "label": label, "reason": reason}
    return {"score": 42, "direction": "neutral", "label": "일반 공시", "reason": "현재 규칙상 우선순위가 높은 사건으로 분류되지 않음"}

def grade_from_score(score):
    if score >= 82:
        return "A"
    if score >= 68:
        return "B"
    return "관찰"

def direction_text(direction):
    return {"positive": "▲ 긍정 가능", "negative": "▼ 부정 가능", "neutral": "• 방향 확인"}.get(direction, "• 방향 확인")

def direction_css(direction):
    return {"positive": "pos", "negative": "neg", "neutral": "neutral"}.get(direction, "neutral")

def _request_json(url, timeout=8):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 StockNewsRadar/1.2",
            "Accept": "application/json",
            "Connection": "close",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

@st.cache_data(ttl=600, show_spinner=False)
def fetch_dart_market(api_key, corp_cls, start_yyyymmdd, end_yyyymmdd):
    results = []
    max_pages = 3  # 최대 300건/시장. 최신 공시 우선.
    for page_no in range(1, max_pages + 1):
        params = {
            "crtfc_key": api_key,
            "bgn_de": start_yyyymmdd,
            "end_de": end_yyyymmdd,
            "corp_cls": corp_cls,
            "sort": "date",
            "sort_mth": "desc",
            "page_no": str(page_no),
            "page_count": "100",
        }
        url = DART_LIST_URL + "?" + urllib.parse.urlencode(params)

        last_error = None
        payload = None
        for attempt in range(3):
            try:
                payload = _request_json(url, timeout=8)
                break
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.7 * (attempt + 1))

        if payload is None:
            raise RuntimeError(f"{MARKETS[corp_cls]} 요청 실패: {last_error}")

        status = payload.get("status")
        if status == "013":
            break
        if status != "000":
            raise RuntimeError(
                f"{MARKETS[corp_cls]} OpenDART {status}: {payload.get('message', '알 수 없는 오류')}"
            )

        batch = payload.get("list", [])
        results.extend(batch)

        total_page = int(payload.get("total_page") or 1)
        if page_no >= total_page or len(batch) < 100:
            break

    return results

def fetch_all_markets(api_key, start_date, end_date):
    rows = []
    states = {}
    errors = {}

    with ThreadPoolExecutor(max_workers=3) as pool:
        future_map = {
            pool.submit(fetch_dart_market, api_key, cls, start_date, end_date): cls
            for cls in MARKETS
        }
        for future in as_completed(future_map):
            cls = future_map[future]
            name = MARKETS[cls]
            try:
                data = future.result()
                rows.extend(data)
                states[name] = len(data)
            except Exception as exc:
                states[name] = None
                errors[name] = str(exc)

    return rows, states, errors

def build_live_candidates(raw_rows):
    seen = set()
    candidates = []

    for row in raw_rows:
        stock_code = (row.get("stock_code") or "").strip()
        report_nm = row.get("report_nm") or ""
        rcept_no = row.get("rcept_no") or ""
        corp_name = row.get("corp_name") or ""

        if not stock_code or not rcept_no:
            continue

        key = (stock_code, report_nm, rcept_no)
        if key in seen:
            continue
        seen.add(key)

        info = classify_disclosure(report_nm)
        if info["score"] < 68:
            continue

        candidates.append({
            "market": "KR",
            "grade": grade_from_score(info["score"]),
            "symbol": stock_code,
            "name": corp_name,
            "direction": info["direction"],
            "material_score": info["score"],
            "confirmation_score": None,
            "overheat_risk": None,
            "event": info["label"],
            "summary": report_nm,
            "reason": info["reason"],
            "source": f"OpenDART · {MARKETS.get(row.get('corp_cls'), '')}",
            "published_at": row.get("rcept_dt") or "",
            "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}",
        })

    candidates.sort(
        key=lambda x: (x["material_score"], x["published_at"]),
        reverse=True,
    )
    return candidates

def render_card(x):
    dc = direction_css(x["direction"])
    direction = direction_text(x["direction"])
    grade = x["grade"]
    grade_cls = "grade-a" if grade == "A" else "grade-b" if grade == "B" else "grade-watch"

    confirmation = str(x["confirmation_score"]) if x.get("confirmation_score") is not None else "—"
    overheat = str(x["overheat_risk"]) if x.get("overheat_risk") is not None else "—"

    safe_name = html.escape(str(x["name"]))
    safe_symbol = html.escape(str(x["symbol"]))
    safe_event = html.escape(str(x["event"]))
    safe_summary = html.escape(str(x["summary"]))
    safe_reason = html.escape(str(x["reason"]))
    safe_source = html.escape(str(x["source"]))
    safe_time = html.escape(str(x["published_at"]))
    safe_url = html.escape(str(x.get("url", "")), quote=True)

    link_html = (
        f'<a class="source-link" href="{safe_url}" target="_blank">DART 원문 보기 ↗</a>'
        if safe_url else ""
    )

    st.markdown(
        f"""
        <div class="stock-card">
          <div class="card-top">
            <div>
              <div class="stock-name">{safe_name}</div>
              <div class="symbol">{safe_symbol} · <span class="{dc}">{direction}</span></div>
            </div>
            <div class="grade {grade_cls}">{grade}급</div>
          </div>
          <div class="event">{safe_event}</div>
          <div class="summary">{safe_summary}</div>
          <div class="metrics">
            <div class="metric"><div class="n">{x["material_score"]}</div><div class="l">공시 중요도</div></div>
            <div class="metric"><div class="n">{confirmation}</div><div class="l">시장확인</div></div>
            <div class="metric"><div class="n">{overheat}</div><div class="l">과열위험</div></div>
          </div>
          <div class="reason">왜 보는가 · {safe_reason}</div>
          <div class="meta">{safe_source} · {safe_time}</div>
          {link_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_market_states(states):
    parts = ['<div class="status-row">']
    for name in ("KOSPI", "KOSDAQ", "KONEX"):
        value = states.get(name)
        if value is None:
            cls, label = "neg", "실패"
        else:
            cls, label = "pos", f"{value:,}건"
        parts.append(
            f'<div class="status-chip"><div class="name">{name}</div>'
            f'<div class="state {cls}">{label}</div></div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)

now_kst = datetime.now(KST)
st.markdown(
    f"""
    <div class="hero">
      <div class="hero-title">StockNewsRadar <span class="live-badge">LIVE V1.2</span></div>
      <div class="hero-sub">다음 거래일 관찰 후보 · {now_kst.strftime('%Y-%m-%d %H:%M')} KST</div>
    </div>
    """,
    unsafe_allow_html=True,
)

market_label = st.segmented_control(
    "시장",
    options=["한국", "미국"],
    default="한국",
    label_visibility="collapsed",
)

if market_label == "한국":
    st.markdown('<div class="section-title">실시간 공시 스캔</div>', unsafe_allow_html=True)

    try:
        api_key = st.secrets["OPENDART_API_KEY"]
    except Exception:
        api_key = None

    if not api_key:
        st.error("OpenDART 인증키가 없습니다. Streamlit App settings → Secrets에 OPENDART_API_KEY를 저장하세요.")
        st.stop()

    lookback_days = st.segmented_control(
        "검색 기간",
        options=["오늘", "최근 2일", "최근 3일"],
        default="최근 2일",
        label_visibility="collapsed",
    )
    days = {"오늘": 0, "최근 2일": 1, "최근 3일": 2}[lookback_days]
    start_date = (now_kst.date() - timedelta(days=days)).strftime("%Y%m%d")
    end_date = now_kst.date().strftime("%Y%m%d")

    if st.button("공시 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("OpenDART 공시를 확인하고 있습니다..."):
        raw, states, errors = fetch_all_markets(api_key, start_date, end_date)

    render_market_states(states)

    if errors:
        failed = ", ".join(errors.keys())
        st.warning(
            f"{failed} 조회가 일시적으로 실패했습니다. "
            "성공한 시장 데이터는 아래에 계속 표시합니다."
        )

    if not raw:
        st.error("현재 OpenDART에서 가져온 공시가 없습니다.")
        if errors:
            with st.expander("연결 오류 상세"):
                for name, msg in errors.items():
                    st.code(f"{name}: {msg}")
        st.stop()

    candidates = build_live_candidates(raw)

    st.markdown(
        f"""
        <div class="market-strip">
          <div class="market-chip"><div class="k">검색 기간</div><div class="v">{start_date} ~ {end_date}</div></div>
          <div class="market-chip"><div class="k">확인한 공시</div><div class="v">{len(raw):,}건</div></div>
          <div class="market-chip"><div class="k">우선 확인 후보</div><div class="v pos">{len(candidates):,}건</div></div>
          <div class="market-chip"><div class="k">캐시</div><div class="v">10분</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    a_list = [x for x in candidates if x["grade"] == "A"][:15]
    b_list = [x for x in candidates if x["grade"] == "B"][:20]

    st.markdown('<div class="section-title">A급 · 우선 확인</div>', unsafe_allow_html=True)
    if a_list:
        for x in a_list:
            render_card(x)
    else:
        st.markdown('<div class="empty">현재 검색 기간에는 A급으로 분류된 중요 공시가 없습니다.</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">B급 · 추가 확인</div>', unsafe_allow_html=True)
    if b_list:
        for x in b_list:
            render_card(x)
    else:
        st.markdown('<div class="empty">현재 검색 기간에는 B급 후보가 없습니다.</div>', unsafe_allow_html=True)

    if errors:
        with st.expander("실패한 시장 상세"):
            for name, msg in errors.items():
                st.code(f"{name}: {msg}")

    with st.expander("V1.2 판단 기준"):
        st.markdown("""
- **공시 중요도**: 공시 제목과 사건 종류를 기준으로 한 1차 규칙 점수입니다.
- **A급**: 중요도 82점 이상으로, 먼저 원문을 확인할 공시입니다.
- **B급**: 중요도 68~81점으로, 세부 내용을 추가 확인할 공시입니다.
- **시장확인 / 과열위험**: 아직 가격·거래량 데이터가 연결되지 않아 `—`로 표시합니다.
- 각 시장은 **최신 최대 300건**만 먼저 조회합니다.
- OpenDART 연결 실패 시 **최대 3회 재시도**합니다.
- 한 시장이 실패해도 성공한 다른 시장의 결과는 계속 표시합니다.
- 결과는 **10분 캐시**되며 `공시 새로고침` 버튼으로 강제 갱신할 수 있습니다.
        """)

else:
    demo_path = Path("data/demo.json")
    if demo_path.exists():
        demo = json.loads(demo_path.read_text(encoding="utf-8"))
        us = [x for x in demo.get("candidates", []) if x.get("market") == "US"]
        st.markdown('<div class="section-title">미국 시장</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="notice">미국 탭은 아직 데모입니다. 다음 단계에서 SEC EDGAR와 미국 뉴스 소스를 연결합니다.</div>',
            unsafe_allow_html=True,
        )
        for x in us:
            x = dict(x)
            x["url"] = ""
            render_card(x)
    else:
        st.info("미국 데이터는 다음 단계에서 연결합니다.")

st.markdown(
    '<div class="notice">StockNewsRadar는 자동매매 시스템이 아닙니다. 공시의 중요도를 빠르게 분류해 다음 거래일의 조사 우선순위를 정하는 리서치 도구입니다.</div>',
    unsafe_allow_html=True,
)
