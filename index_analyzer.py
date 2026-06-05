import datetime
import yfinance as yf
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL
from notifier import send_telegram_message

def get_index_stats(ticker, name):
    try:
        # Fetch max history to get all-time high
        hist = yf.download(ticker, period="max")
        if hist.empty:
            return None
        
        # Current and previous close
        current_close = float(hist['Close'].iloc[-1].item() if hasattr(hist['Close'].iloc[-1], 'item') else hist['Close'].iloc[-1])
        prev_close = float(hist['Close'].iloc[-2].item() if hasattr(hist['Close'].iloc[-2], 'item') else hist['Close'].iloc[-2])
        
        # Point change and pct change
        change_pt = current_close - prev_close
        change_pct = (change_pt / prev_close) * 100
        
        # Direction arrow
        if change_pt > 0:
            arrow = f"▲{change_pt:,.2f}pt, +{change_pct:.2f}%"
        elif change_pt < 0:
            arrow = f"▼{abs(change_pt):,.2f}pt, {change_pct:.2f}%"
        else:
            arrow = f"- 0.00pt, 0.00%"
            
        # All time high
        ath = float(hist['High'].max().item() if hasattr(hist['High'].max(), 'item') else hist['High'].max())
        ath_diff = ((current_close - ath) / ath) * 100
        
        # 52-week high (approximate for '직전 전고점 대비')
        hist_1y = hist.tail(252)
        if not hist_1y.empty:
            local_high = float(hist_1y['High'].max().item() if hasattr(hist_1y['High'].max(), 'item') else hist_1y['High'].max())
        else:
            local_high = ath
            
        local_diff = ((current_close - local_high) / local_high) * 100
        
        return {
            "name": name,
            "close": current_close,
            "arrow": arrow,
            "ath_diff": f"{ath_diff:+.2f}%",
            "local_diff": f"{local_diff:+.2f}%"
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def analyze_market_index(chat_id=None):
    print(f"\n📈 [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Index Analysis (v4.1)...")
    
    # Skip weekends for scheduled run, but allow if manual (/index)
    if chat_id is None and datetime.date.today().weekday() >= 5:
        print("Skipping index analysis on weekends.")
        return
        
    indices = [
        ("^KS11", "KOSPI"),
        ("^KQ11", "KOSDAQ"),
        ("^GSPC", "S&P 500")
    ]
    
    stats = []
    for ticker, name in indices:
        res = get_index_stats(ticker, name)
        if res:
            stats.append(res)
            
    if not stats:
        error_msg = "❌ 지수 데이터를 가져오는데 실패했습니다."
        if chat_id:
            send_telegram_message(chat_id, error_msg)
        print(error_msg)
        return
        
    table_rows = ""
    data_for_prompt = ""
    for s in stats:
        table_rows += f"| {s['name']} | {s['close']:,.2f} ({s['arrow']}) | {s['ath_diff']} | {s['local_diff']} |\n"
        data_for_prompt += f"{s['name']}: 종가 {s['close']:,.2f}, {s['arrow']}, 최고점대비 {s['ath_diff']}\n"
        
    prompt = f"""
당신은 거시경제 및 주식 시장 전문 애널리스트입니다.
오늘 장 마감 직후의 한국 및 미국 주요 지수 데이터가 아래와 같습니다.

[시장 데이터]

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
    send_telegram_message(report_text)
    print("🚀 Index analysis sent to Telegram.")

if __name__ == "__main__":
    analyze_market_index()
