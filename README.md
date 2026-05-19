# 📈 K-Stock Quant & DART Swing Screener Bot

매일 한국 주식 시장(KOSPI/KOSDAQ)의 정규장이 종료된 후, 거래대금과 가격 조건을 만족하는 주도주를 선별하고, DART Open API를 통해 3개년 재무 안정성을 검증한 뒤, Google Gemini AI 분석을 결합하여 매일 저녁 **20:00 KST**에 텔레그램으로 최종 스윙 주도주 브리핑 리포트를 발송해 주는 자동화 에이전트 시스템입니다.

---

## ✨ 핵심 기능

1. **1차 퀀트 필터링**: 당일 등락률 상위 종목 중 10% 이상 ~ 30% 이하이면서, 거래대금이 최소 100억 원 이상인 주도주만 선별.
2. **기술적 추세 검증**: `yfinance`를 활용해 1000일 장기 이평선 위치 판별 및 단기 정배열(5-20-60) 추세 정렬 여부, 20일 평균 거래량 대비 당일 거래량 폭발 비율 연산.
3. **DART 재무 건전성 필터**: 3개년 연속 당기순이익 흑자 유지 여부 검증 및 부채비율 조건(`liabilities < equity`) 검증을 거쳐 부실주 완벽 제거.
4. **투자자 수급 및 뉴스 크롤링**: 네이버 모바일 API 및 다중 채널(네이버 금융, 구글 뉴스, 인베스팅닷컴)을 통해 외인/기관/개인 순매수 정보와 당일 관련 호재 뉴스를 수집.
5. **AI 애널리스트 리포트 생성**: Google Gemini 2.5 Flash를 활용하여 해당 주도주의 섹터 분류, 구체적인 상승 사유 및 테마 분석, 스윙 매매 평점(A~C 등급) 부여 및 최종 탑픽 종목을 도출.
6. **텔레그램 알림 시스템**: Markdown 기반 리포트 생성 및 4096자 제한 대응 자동 Chunking 발송 로직 포함.

---

## 🛠️ 설치 및 사용 방법

### 1. 의존성 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음과 같이 인증키 정보를 입력합니다. (※ `.env` 파일은 절대 GitHub에 업로드하지 마세요. `.gitignore`에 포함되어 있습니다.)

```ini
# DART Open API 인증키
DART_API_KEY=your_dart_api_key

# Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key

# 텔레그램 알림 정보
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### 3. 도우미 스크립트로 텔레그램 연동
봇 토큰과 대화방 ID(Chat ID)를 자동으로 찾아 `.env` 파일에 기록해주는 유틸리티가 포함되어 있습니다.
```bash
python get_chat_id.py
```

### 4. 봇 실행 방법

*   **즉시 1회성 스크리닝 실행 (수동)**:
    ```bash
    python main.py --now
    ```
*   **스케줄러 모드 구동 (매일 20시 자동 대기)**:
    ```bash
    python main.py
    ```

---

## 📁 프로젝트 구조

*   `main.py`: 파이프라인 진입점 (스케줄러 및 CLI 모드 제어).
*   `config.py`: 환경 변수 로드 및 설정 검증.
*   `scraper.py`: DART, 네이버, 구글 뉴스 등 웹 및 API 스크래핑 엔진.
*   `quant_filter.py`: 1차 수치/이평선 필터 및 DART 재무 필터 실행부.
*   `report_generator.py`: Gemini API 연동 및 로컬 분석 보고서 컴파일.
*   `notifier.py`: 텔레그램 메시지 포맷팅 및 분할 발송 로직.
*   `get_chat_id.py`: 텔레그램 연동 도우미 스크립트.
*   `requirements.txt`: 의존 패키지 목록.
*   `.gitignore`: 업로드 방지용 설정 파일.
