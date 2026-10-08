# StockNewsRadar iPhone V1

아이폰 Safari에서 빠르게 확인하는 모바일 우선 StockNewsRadar 첫 버전입니다.

## 현재 기능
- 한국 / 미국 시장 탭
- A급 / B급 / 관찰 후보
- 핵심 재료, 방향, 점수, 과열위험
- 오늘의 시장 변수
- 종목 상세 카드
- 데모 데이터 내장
- Streamlit Community Cloud 배포 준비 완료

## 로컬 실행

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## 아이폰에서 보는 방법

1. 이 폴더를 GitHub 저장소에 업로드합니다.
2. Streamlit Community Cloud에서 저장소의 `app.py`를 배포합니다.
3. 생성된 주소를 아이폰 Safari에서 엽니다.
4. Safari 공유 버튼 → `홈 화면에 추가`를 누르면 앱처럼 사용할 수 있습니다.

## 다음 단계
V2에서 아래를 실제 데이터에 연결할 예정입니다.

- OpenDART
- NAVER 뉴스 검색
- Alpaca News
- SEC EDGAR
- 가격 / 거래량 반응
- 매일 자동 갱신

## 연구용 예측과 실제 결과 비교

관심 순위의 사후 가격 변화와 명시적 예측 적중률을 구분합니다. 과거 TOP
기록은 예측으로 소급 변환하지 않습니다. 새 스냅샷 실행부터 그날 TOP 후보
전체(기존 선택 모집단)에 대해 `momentum-5-session-deadband-1pct-v1`을 기록합니다.
이 규칙은 검증된 우월성이 없는 재현 가능한 연구 기준 모델입니다.

- 기존 Yahoo Finance 입력에서 완료된 최근 6개 거래 세션의 OHLC를 검증합니다.
  5세션 종가 변화가 +1% 이상이면 상승, -1% 이하면 하락, 그 사이는 판단보류입니다.
  입력 누락·불량 OHLC·분할 발생은 판단보류로 남깁니다. 확률은 생성하지 않습니다.
- 발행 이후 시작하는 온전한 1·5·20거래 세션의 종가를 평가 시점으로 고정합니다.
  기준가격은 발행 시점의 가장 최근 완료 세션 종가입니다. 한국 XKRX,
  미국 주식 정규장 XNYS 달력(미국 시장 공통 세션 기준)을 사용하며, 달력 패키지
  버전과 실제 사용한 날짜·개장·폐장 시각을 함께 보존합니다.
- `data/predictions/issued/{KR,US}/YYYY-MM-DD.json`은 최초 발행 후 덮어쓰지
  않습니다. 발행 시각, 원본 후보/가격 입력, 해시, 규칙 버전, 기준가격과 기간을
  보존합니다. 같은 날 재실행해도 중복 발행하지 않습니다.
- 평가 시점이 지나고 1시간 후부터 기존 성과 일정에서 실제 가격을 조회합니다.
  정해진 날짜의 봉이 없으면 다른 날짜로 옮기지 않습니다. 누락/불량 시도도
  `observations/<prediction-id>/YYYY-MM-DD.json`에 보존하고 이후 재시도합니다.
  최초 유효 관측은 고정합니다. 분할 발생 구간은 평가불가이며 배당 총수익은 계산하지 않습니다.
- `prediction_validation.json`은 기간·시장·종목·발행월·규칙 버전별 표본수와
  방향 적중률, 동일 표본의 단순 상승 기준선 적중률을 기록합니다. 완료·미도래·
  누락·잘못된 가격·평가불가를 분리하고 30건 미만은 표본 부족으로 표시합니다.
  당시 Git 보관본을 확인할 수 없는 예측은 채점하지 않습니다.
- 예측 전수와 실패 사례를 보존하되, 모집단은 TOP 후보이므로 전체 시장에 대한
  무편향 성능을 주장하지 않습니다. 거래·주문·수익 보장을 수행하지 않습니다.

기존 스냅샷/성과 일정에 연결되어 있으며 새로운 정기 실행 일정은 없습니다.
무결성 오류가 있어도 유효 기록은 분석에 포함되고 불량 기록은 격리됩니다.
오류 무결성 보고서는 실패한 실행의 artifact에 90일간 보관되며 작업은 실패
상태를 유지합니다. 오류 시 저장소 health 파일은 이전 값일 수 있습니다.

```sh
pip install -r requirements-research.txt
python -m unittest discover -s tests -v
python scripts/build_performance_analysis.py
python scripts/build_persistence_performance.py
python scripts/build_prediction_validation.py
```

`research_predictions.py issue --market KR` / `--market US`는 실행 당일
스냅샷만 받습니다. 과거 날짜를 지정하여 예측을 만드는 옵션은 없습니다.

예측 보고서의 `explicit_predictions.cumulative_groups`는 시장×평가 기간×
예측 유형×규칙 버전별로 모든 발행월과 종목을 누적합니다. 기존 종목×월 세부
`groups`와 전체 `records`는 유지됩니다. 원가격 오차는 가격 수준이 다른 종목을
섞지 않도록 누적 집계에서도 종목별로 분리합니다. `evaluated_count`만 적중률과
30건 표본 기준의 분모이며, `pending_count`와 상태별 수, 판단보류 부분집합인
`abstained_count`를 별도로 표시합니다. 중첩 기간과 종목 상관 때문에 30건은
독립 표본 30개 또는 통계적 유의성을 뜻하지 않습니다.
