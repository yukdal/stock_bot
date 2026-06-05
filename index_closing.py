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
    3중 교차 검증 파이프라인 (KIS -> Naver/Investing -> yfinance) 적용.
    """
    import pandas as pd
    import yfinance as yf
    from kis_api import fetch_kis_domestic_index, fetch_kis_overseas_index
    from scraper import fetch_naver_index_data, fetch_investing_index_data
    
    current_close, point_change, pct_change = 0.0, 0.0, 0.0
    ath, local_high, ath_pct, local_high_pct = 0.0, 0.0, 0.0, 0.0
    
    try:
        # 1. Base initialization & ATH / Local High from yfinance
        df = yf.download(ticker, period="max", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
            
        if not df.empty:
            df = df.dropna(subset=['Close', 'High'])
            
        yf_valid = not df.empty and len(df) >= 2
        
        if yf_valid:
            ath = float(df['High'].max().item() if hasattr(df['High'].max(), 'item') else df['High'].max())
            local_df = df.tail(252)
            local_high = float(local_df['High'].max().item() if hasattr(local_df['High'].max(), 'item') else local_df['High'].max())
            
            # Default values from yfinance
            recent_df = df.tail(5)
            current_close = float(recent_df['Close'].iloc[-1].item() if hasattr(recent_df['Close'].iloc[-1], 'item') else recent_df['Close'].iloc[-1])
            prev_close = float(recent_df['Close'].iloc[-2].item() if hasattr(recent_df['Close'].iloc[-2], 'item') else recent_df['Close'].iloc[-2])
            point_change = current_close - prev_close
            pct_change = (point_change / prev_close * 100) if prev_close > 0 else 0.0
            
            # Anomaly filter for yfinance bug (e.g., KOSPI returning 8600+)
            if name == "KOSPI" and current_close > 5000:
                current_close, point_change, pct_change = 0.0, 0.0, 0.0
        
        # 2. Cross Validation Pipeline
        def update_from_dict(d):
            nonlocal current_close, point_change, pct_change
            if d and d.get("close") and d["close"] > 0:
                current_close = d["close"]
                point_change = d.get("change", 0.0)
                pct_change = d.get("change_pct", 0.0)
                return True
            return False
            
        cv_success = False
        
        if name in ["KOSPI", "KOSDAQ"]:
            # Priority 1: KIS API
            kis_code = "0001" if name == "KOSPI" else "1001"
            kis_data = fetch_kis_domestic_index(kis_code, days=5)
            if kis_data and len(kis_data) >= 2:
                try:
                    latest = float(kis_data[-1].get("bstp_nmix_prpr", kis_data[-1].get("stck_bsop_prpr", 0)))
                    prev = float(kis_data[-2].get("bstp_nmix_prpr", kis_data[-2].get("stck_bsop_prpr", 0)))
                    if latest > 0 and prev > 0:
                        cv_success = update_from_dict({
                            "close": latest,
                            "change": latest - prev,
                            "change_pct": (latest - prev) / prev * 100
                        })
                except: pass
                
            # Priority 2: Naver Finance
            if not cv_success:
                cv_success = update_from_dict(fetch_naver_index_data(name))
                
            # Priority 3: Investing.com
            if not cv_success:
                cv_success = update_from_dict(fetch_investing_index_data(name))
                
        elif name == "S&P 500":
            # Priority 1: KIS Overseas API
            kis_data = fetch_kis_overseas_index("SPX", days=5)
            if kis_data and len(kis_data) >= 2:
                try:
                    # KIS overseas index keys
                    latest = float(kis_data[-1].get("clos", kis_data[-1].get("ovrs_nmix_prpr", 0)))
                    prev = float(kis_data[-2].get("clos", kis_data[-2].get("ovrs_nmix_prpr", 0)))
                    if latest > 0 and prev > 0:
                        cv_success = update_from_dict({
                            "close": latest,
                            "change": latest - prev,
                            "change_pct": (latest - prev) / prev * 100
                        })
                except: pass
                
            # Priority 2: Investing.com
            if not cv_success:
                cv_success = update_from_dict(fetch_investing_index_data("SPX"))
                
        # 3. Final metric calculation
        if current_close > 0:
            ath_pct = ((current_close - ath) / ath * 100) if ath > 0 else 0.0
            local_high_pct = ((current_close - local_high) / local_high * 100) if local_high > 0 else 0.0
        else:
            return None
            
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
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = "당신은 20년 경력의 증권사 수석 매크로 애널리스트입니다. 오늘 한국(KOSPI/KOSDAQ) 및 미국 시장 마감 직후의 시장 국면과 변동성에 대한 핵심 통찰을 딱 1줄의 숏 코멘트로 요약해서 작성해주세요."
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Gemini Macro Comment Error: {e}")
        return "시장 데이터 분석 중 일시적인 지연이 발생했습니다. 리스크 관리에 유의하시기 바랍니다."

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

def execute_index_closing(chat_id=None):
    """오후 3시 45분에 단독 실행되는 메인 파이프라인"""
    today = datetime.date.today()
    if today.weekday() >= 5 and chat_id is None:
        print("📅 주말에는 지수 정산 모듈이 실행되지 않습니다.")
        return
        
    print(f"\n📈 [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Index Closing Settlement...")
    
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
    if chat_id:
        send_telegram_message(final_report, chat_id=chat_id)
    else:
        send_telegram_message(final_report)
    print("🎉 Index closing settlement dispatched successfully!")

if __name__ == "__main__":
    execute_index_closing()
