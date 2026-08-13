import json
import os
import socket
import sys
import time
import urllib.parse
import urllib.request

HOST = "opendart.fss.or.kr"
HOME = "https://opendart.fss.or.kr/"
API = "https://opendart.fss.or.kr/api/list.json"
KEY = os.getenv("OPENDART_API_KEY", "").strip()


def probe(label, url, timeout=12):
    print(f"\\n=== {label} ===")
    started = time.perf_counter()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 StockNewsRadar-GitHubActions-Test/1.0",
            "Accept": "*/*",
            "Connection": "close",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            elapsed = time.perf_counter() - started
            body = response.read(500).decode("utf-8", errors="ignore")
            print(f"SUCCESS HTTP={getattr(response, 'status', None)} elapsed={elapsed:.2f}s")
            print(body[:500])
            return True
    except Exception as exc:
        elapsed = time.perf_counter() - started
        print(f"FAILED elapsed={elapsed:.2f}s error={repr(exc)}")
        return False


print("=== DNS ===")
try:
    infos = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
    addresses = sorted({item[4][0] for item in infos})
    print("DNS SUCCESS:", addresses)
except Exception as exc:
    print("DNS FAILED:", repr(exc))

home_ok = probe("OpenDART homepage", HOME)
api_no_key_ok = probe("OpenDART API no-key", API)

api_key_ok = None
if KEY:
    params = {
        "crtfc_key": KEY,
        "bgn_de": "20260813",
        "end_de": "20260813",
        "page_no": "1",
        "page_count": "1",
    }
    api_key_url = API + "?" + urllib.parse.urlencode(params)
    api_key_ok = probe("OpenDART API with repository secret", api_key_url)
else:
    print("\\n=== OpenDART API with repository secret ===")
    print("SKIPPED: OPENDART_API_KEY repository secret is not configured.")

print("\\n=== SUMMARY ===")
print(json.dumps({
    "homepage_network_ok": home_ok,
    "api_network_ok": api_no_key_ok,
    "api_with_key_network_ok": api_key_ok,
    "secret_present": bool(KEY),
}, ensure_ascii=False))

# Fail the workflow only if the OpenDART host itself cannot be reached.
if not home_ok and not api_no_key_ok:
    sys.exit(2)
