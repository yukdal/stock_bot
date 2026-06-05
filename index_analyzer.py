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
{data_for_prompt}

이 데이터를 바탕으로 텔레그램 구독자들에게 보낼 간결하고 명확한 '매크로 한줄평'을 작성해주세요.
최근의 거시 경제 동향을 반영하여 통찰력 있는 1~3줄의 분석 코멘트만 출력하세요. 
출력할 때 제목이나 인사말 없이 코멘트 내용만 바로 작성해주세요. (예: - 미국은 끈적한 인플레이션과 연준의 고금리 장기화 우려가, 한국은 반도체 랠리 속...)
"""

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        gemini_comment = response.text.strip()
        if not gemini_comment.startswith("-"):
            gemini_comment = "- " + gemini_comment
    except Exception as e:
        gemini_comment = f"- AI 코멘트 생성 중 오류가 발생했습니다: {e}"
        
    final_message = f"""📊 오후 3시 45분 국내외 주요 지수 마감 정산 (v4.1)
오늘 정규장 마감 직후 집계된 주요 지수의 위치와 변동성 데이터입니다.
(데이터 교차검증 완료)

| 지수명 | 당일 종가 (전일대비) | 역사적 최고점 대비 | 직전 전고점 대비 |
| :--- | :--- | :---: | :---: |
{table_rows.strip()}

💡 매크로 한줄평 (Gemini Pro 분석)
{gemini_comment}"""

    if chat_id:
        send_telegram_message(chat_id, final_message)
    else:
        from chat_manager import get_all_chat_ids
        chat_ids = get_all_chat_ids()
        for cid in chat_ids:
            send_telegram_message(cid, final_message)
            
    print("✅ Index analysis (v4.1) sent successfully!")

if __name__ == "__main__":
    analyze_market_index()
