import datetime
import yfinance as yf
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL
from notifier import send_telegram_message

def get_market_data(ticker):
    try:
        data = yf.download(ticker, period="5d")
        # Remove NaN rows (e.g. weekends/holidays) to prevent errors
        data = data.dropna(subset=['Close'])
        
        if len(data) < 2:
            return None
        
        # Get latest and previous day to calculate change
        today_close = float(data['Close'].iloc[-1].item() if hasattr(data['Close'].iloc[-1], 'item') else data['Close'].iloc[-1])
        prev_close = float(data['Close'].iloc[-2].item() if hasattr(data['Close'].iloc[-2], 'item') else data['Close'].iloc[-2])
        
        change = today_close - prev_close
        change_pct = (change / prev_close) * 100
        
        return {
            "close": today_close,
            "change": change,
            "change_pct": change_pct
        }
    except Exception as e:
        print(f"⚠️ Error fetching index data for {ticker}: {e}")
        return None

def execute_index_closing(chat_id=None):
    print(f"\n📈 [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Index Analysis...")
    
    # Skip weekends unless triggered by a command
    if datetime.date.today().weekday() >= 5 and chat_id is None:
        print("📅 Today is a weekend. The Korean stock market is closed. Skipping index analysis.")
        return
    
    kospi = get_market_data("^KS11")
    kosdaq = get_market_data("^KQ11")
    
    # Fallback if no data
    kospi_str = f"KOSPI: {kospi['close']:.2f} ({kospi['change']:+.2f}, {kospi['change_pct']:+.2f}%)" if kospi else "KOSPI: 데이터 없음"
    kosdaq_str = f"KOSDAQ: {kosdaq['close']:.2f} ({kosdaq['change']:+.2f}, {kosdaq['change_pct']:+.2f}%)" if kosdaq else "KOSDAQ: 데이터 없음"
    
    print(kospi_str)
    print(kosdaq_str)
    
    # Check Gemini API Key
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        report_text = f"📊 [장 마감 시황 브리핑]\n\n{kospi_str}\n{kosdaq_str}\n\n*Gemini API Key가 설정되지 않아 간략 브리핑만 제공됩니다.*"
        if chat_id:
            send_telegram_message(report_text, chat_id=chat_id)
        else:
            send_telegram_message(report_text)
        return
        
    prompt = f"""
당신은 대한민국 주식 시장 전문 애널리스트입니다.
오늘 장 마감 직후의 한국 시장 지수 데이터가 아래와 같습니다.

[시장 데이터]
{kospi_str}
{kosdaq_str}

이 데이터를 바탕으로 텔레그램 구독자들에게 보낼 간결하고 명확한 '장 마감 지수 브리핑'을 작성해주세요.
다음 포맷을 지켜주세요.

[출력 양식]
📊 장 마감 지수 브리핑

■ KOSPI: [지수] ([등락률])
■ KOSDAQ: [지수] ([등락률])

💡 시장 요약 및 코멘트:
- (오늘의 지수 흐름에 대한 애널리스트의 1~2줄 코멘트)
- (스윙 투자자를 위한 조언 1줄)
"""
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        report_text = response.text
        print("✅ Index analysis report generated successfully.")
    except Exception as e:
        print(f"❌ Error generating index report: {e}")
        report_text = f"📊 [장 마감 시황 브리핑]\n\n{kospi_str}\n{kosdaq_str}\n\n*(AI 분석을 가져오는데 실패했습니다)*"
        
    # Send to Telegram
    if chat_id:
        send_telegram_message(report_text, chat_id=chat_id)
    else:
        send_telegram_message(report_text)
    print("🚀 Index analysis sent to Telegram.")

if __name__ == "__main__":
    execute_index_closing()
