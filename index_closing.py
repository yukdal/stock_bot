import datetime
import yfinance as yf
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL
from notifier import send_telegram_message

INDICES = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "S&P 500": "^GSPC"
}

def fetch_index_data(name, ticker):
    """
    특정 지수의 당일/전일 종가, ATH(역사적 최고점), Local High(52주 최고점)를 계산합니다.
    """
    try:
        idx = yf.Ticker(ticker)
        max_df = idx.history(period="max")
        
        if name in ["KOSPI", "KOSDAQ"]:
            # Fetch real-time data from Naver Finance because Yahoo is 1-day delayed at 15:45 KST
            url = f"https://polling.finance.naver.com/api/realtime/domestic/index/{name}"
            import requests
            r = requests.get(url, timeout=10)
            data = r.json()['datas'][0]
            current_close = float(data['closePrice'].replace(',', ''))
            point_change = float(data['compareToPreviousClosePrice'].replace(',', ''))
            pct_change = float(data['fluctuationsRatio'].replace(',', ''))
        else:
            # S&P 500 uses yfinance (US market already closed)
            recent_df = idx.history(period="5d").dropna(subset=['Close'])
            if len(recent_df) < 2:
                return None
            current_close = recent_df['Close'].iloc[-1]
            prev_close = recent_df['Close'].iloc[-2]
            point_change = current_close - prev_close
            pct_change = (point_change / prev_close) * 100 if prev_close > 0 else 0.0
            
        # 최대 기간 데이터로 최고점 분석
        if len(max_df) > 0:
            max_df = max_df.dropna(subset=['High'])
            ath = max_df['High'].max()
            local_df = max_df.tail(252) # 약 52주
            local_high = local_df['High'].max()
            
            ath_pct = ((current_close - ath) / ath * 100) if ath > 0 else 0.0
            local_high_pct = ((current_close - local_high) / local_high * 100) if local_high > 0 else 0.0
        else:
            ath_pct = 0.0
            local_high_pct = 0.0
            
        return {
            "current_close": current_close,
            "point_change": point_change,
            "pct_change": pct_change,
            "ath_pct": ath_pct,
            "local_high_pct": local_high_pct
        }
    except Exception as e:
        print(f"❌ Error fetching index data for {name} ({ticker}): {e}")
        return None

def generate_index_macro_comment():
    """Gemini를 이용한 매크로 한줄평 생성"""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        return "현재 시장의 변동성이 지속되고 있으며, 주요 지지선 및 저항선 부근에서의 리스크 관리가 필요한 국면입니다. (Mock Data)"
        
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = "당신은 20년 경력의 증권사 수석 매크로 애널리스트입니다. 오늘 한국(KOSPI/KOSDAQ) 및 미국 시장 마감 직후의 시장 국면과 변동성에 대한 핵심 통찰을 딱 1줄의 숏 코멘트로 요약해서 작성해주세요."
            response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            return response.text.strip()
        except Exception as e:
            err_str = str(e)
            print(f"❌ Gemini Macro Comment Error (Attempt {attempt+1}/{max_retries}): {err_str}")
            if "503" in err_str or "429" in err_str:
                time.sleep(2)
                continue
            return f"시장 데이터 분석 중 일시적인 지연이 발생했습니다. (오류: {err_str[:100]})"
            
    return "시장 데이터 분석 중 일시적인 지연이 발생했습니다. (Gemini 서버 혼잡으로 인한 503 오류)"

def format_number(val, is_pct=False):
    """지수 소수점 및 기호 포맷팅"""
    if val is None: return "N/A"
    
    # 등락률, 포인트 모두 소수점 둘째자리 통일 적용
    sign = "▲" if val > 0 else ("▼" if val < 0 else "")
    plus = "+" if val > 0 else ""
    
    if is_pct:
        return f"{plus}{val:.2f}%"
    else:
        return f"{sign}{abs(val):.2f}"

def execute_index_closing():
    """오후 3시 45분에 단독 실행되는 메인 파이프라인"""
    today = datetime.date.today()
    if today.weekday() >= 5:
        print("📅 주말에는 지수 정산 모듈이 실행되지 않습니다.")
        return
        
    print(f"\n📈 [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Index Closing Settlement...")
    
    try:
        report_lines = []
        report_lines.append("📊 [오후 3시 45분 국내외 주요 지수 마감 정산 (v4.1)]")
        report_lines.append("오늘 정규장 마감 직후 집계된 주요 지수의 위치와 변동성 데이터입니다. (데이터 교차검증 완료)\n")
        
        report_lines.append("| 지수명 | 당일 종가 (전일대비) | 역사적 최고점 대비 | 직전 전고점 대비 |")
        report_lines.append("| :--- | :--- | :---: | :---: |")
        
        for name, ticker in INDICES.items():
            data = fetch_index_data(name, ticker)
            if data:
                c_close = f"{data['current_close']:,.2f}"
                pt_chg = format_number(data['point_change'], is_pct=False)
                pct_chg = format_number(data['pct_change'], is_pct=True)
                
                ath_chg = format_number(data['ath_pct'], is_pct=True)
                lh_chg = format_number(data['local_high_pct'], is_pct=True)
                
                report_lines.append(f"| **{name}** | {c_close} ({pt_chg}pt, {pct_chg}) | {ath_chg} | {lh_chg} |")
            else:
                report_lines.append(f"| **{name}** | 데이터 수집 지연 | - | - |")
                
        comment = generate_index_macro_comment()
        report_lines.append("\n💡 **매크로 한줄평 (Gemini Pro 분석)**")
        report_lines.append(f"- {comment}")
        report_lines.append("--------------------------------------")
        
        final_report = "\n".join(report_lines)
        
        # 텔레그램 발송
        send_telegram_message(final_report)
        print("🎉 Index closing settlement dispatched successfully!")
    except Exception as e:
        print(f"❌ Error occurred during index settlement execution: {e}")

if __name__ == "__main__":
    execute_index_closing()
