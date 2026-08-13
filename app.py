import time
import urllib.request
import urllib.error
import streamlit as st

st.set_page_config(page_title="StockNewsRadar Diagnostics", page_icon="🧪", layout="centered")

st.markdown("""
<style>
.stApp { background:#0b0d10; color:#f4f6f8; }
.block-container { max-width:760px; padding-top:4.5rem; padding-left:1rem; padding-right:1rem; }
.card { background:#15181d; border:1px solid #272c34; border-radius:16px; padding:1rem; margin:.7rem 0; }
.ok { color:#39d98a; font-weight:800; }
.bad { color:#ff6b6b; font-weight:800; }
.warn { color:#f5c451; font-weight:800; }
.muted { color:#9ca3af; font-size:.82rem; }
code { white-space:pre-wrap !important; }
</style>
""", unsafe_allow_html=True)

TARGETS = [
    ("OpenDART homepage", "https://opendart.fss.or.kr/"),
    ("OpenDART API no-key probe", "https://opendart.fss.or.kr/api/list.json"),
    ("GitHub", "https://github.com/"),
    ("Google", "https://www.google.com/"),
]

def probe(name, url, timeout=8):
    started = time.perf_counter()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 StockNewsRadar-Diagnostics/1.3",
            "Accept": "*/*",
            "Connection": "close",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            elapsed = time.perf_counter() - started
            body = response.read(300).decode("utf-8", errors="ignore")
            return {
                "name": name,
                "url": url,
                "ok": True,
                "status": getattr(response, "status", None),
                "elapsed": elapsed,
                "detail": body[:300],
            }
    except urllib.error.HTTPError as exc:
        elapsed = time.perf_counter() - started
        try:
            body = exc.read(300).decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        # HTTP error still proves network connectivity to the host.
        return {
            "name": name,
            "url": url,
            "ok": True,
            "status": exc.code,
            "elapsed": elapsed,
            "detail": f"HTTPError {exc.code}: {body[:240]}",
        }
    except Exception as exc:
        elapsed = time.perf_counter() - started
        return {
            "name": name,
            "url": url,
            "ok": False,
            "status": None,
            "elapsed": elapsed,
            "detail": repr(exc),
        }

st.title("StockNewsRadar 연결 진단")
st.caption("Streamlit Cloud → 외부 사이트 연결 상태 확인")

if st.button("진단 실행", use_container_width=True):
    results = []
    with st.spinner("외부 연결을 확인하고 있습니다..."):
        for name, url in TARGETS:
            results.append(probe(name, url))

    for r in results:
        cls = "ok" if r["ok"] else "bad"
        state = "연결됨" if r["ok"] else "실패"
        st.markdown(
            f"""
            <div class="card">
              <div><b>{r["name"]}</b></div>
              <div class="{cls}">{state}</div>
              <div class="muted">응답시간 {r["elapsed"]:.2f}s · HTTP {r["status"] if r["status"] is not None else "—"}</div>
              <div class="muted">{r["url"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander(f"{r['name']} 상세"):
            st.code(r["detail"] or "(본문 없음)")

    dart_home = next(x for x in results if x["name"] == "OpenDART homepage")
    dart_api = next(x for x in results if x["name"] == "OpenDART API no-key probe")
    github = next(x for x in results if x["name"] == "GitHub")
    google = next(x for x in results if x["name"] == "Google")

    st.subheader("판정")

    if not github["ok"] and not google["ok"]:
        st.error("Streamlit Cloud의 외부 인터넷 연결 전반에 문제가 있는 것으로 보입니다.")
    elif github["ok"] and google["ok"] and not dart_home["ok"] and not dart_api["ok"]:
        st.error(
            "Streamlit Cloud에서는 일반 인터넷 연결은 되지만 OpenDART 도메인 연결만 실패합니다. "
            "OpenDART 수집기를 Streamlit 밖으로 분리하는 편이 적절합니다."
        )
    elif dart_home["ok"] and not dart_api["ok"]:
        st.warning(
            "OpenDART 홈페이지는 연결되지만 API 엔드포인트만 실패합니다. "
            "API 접근 경로 또는 서버 정책을 추가 확인해야 합니다."
        )
    elif dart_home["ok"] and dart_api["ok"]:
        st.success(
            "OpenDART 도메인과 API 엔드포인트 모두 네트워크 연결은 됩니다. "
            "이 경우 인증키/IP/API 요청 조건을 다시 확인해야 합니다."
        )
    else:
        st.warning("결과가 혼합되어 있습니다. 각 항목의 상세 오류를 확인하세요.")

st.info(
    "이 페이지는 진단 전용입니다. 인증키를 사용하지 않으며 실제 공시 데이터를 저장하지 않습니다."
)
