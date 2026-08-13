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
