"""
stock_card_generator.py
Generates per-stock infographic cards (1 image per TOP pick) and sends via Telegram.
Parses Gemini report text for buy/target/stop prices and recommendation reasons,
then combines with structured quant data for rendering.
"""
import re
import time
import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from notifier import send_telegram_photo

BASE_DIR = Path(__file__).resolve().parent

# ── Sector → Emoji Mapping ──
SECTOR_ICONS = {
    "반도체": "💾", "반도체장비": "💾", "전자부품": "💾",
    "2차전지": "🔋", "배터리": "🔋", "에너지저장": "🔋",
    "바이오": "💊", "제약": "💊", "의약품": "💊", "헬스케어": "💊",
    "IT": "💻", "소프트웨어": "💻", "인터넷": "💻", "플랫폼": "💻",
    "자동차": "🚗", "자동차부품": "🚗", "전기차": "🚗",
    "금융": "🏦", "은행": "🏦", "증권": "🏦", "보험": "🏦",
    "에너지": "⚡", "전력": "⚡", "태양광": "⚡", "신재생에너지": "⚡",
    "건설": "🏗️", "건축": "🏗️", "인프라": "🏗️",
    "화학": "🧪", "정밀화학": "🧪", "석유화학": "🧪",
    "식품": "🍽️", "음식료": "🍽️", "음료": "🍽️",
    "엔터": "🎬", "엔터테인먼트": "🎬", "미디어": "🎬", "게임": "🎮",
    "통신": "📡", "5G": "📡", "네트워크": "📡",
    "로봇": "🤖", "AI": "🤖", "인공지능": "🤖",
    "방산": "🛡️", "국방": "🛡️", "항공우주": "🚀",
    "철강": "⚙️", "금속": "⚙️", "소재": "⚙️",
    "유통": "🛒", "리테일": "🛒", "백화점": "🛒",
    "조선": "🚢", "해운": "🚢", "물류": "🚢",
    "M&A": "🤝", "지주": "🏢", "지배구조": "🏢",
}

def get_sector_icon(sector_text):
    """Match sector/theme text to an emoji icon."""
    if not sector_text:
        return "📊"
    for keyword, icon in SECTOR_ICONS.items():
        if keyword in sector_text:
            return icon
    return "📊"


def parse_gemini_report(report_text):
    """
    Parse the Gemini-generated report text to extract per-stock analysis blocks.
    Returns a list of dicts with keys: name, ticker, theme, buy_price, target_price, stop_loss, reasons
    """
    stocks_parsed = []
    
    # Split report by stock blocks (■ marker)
    blocks = re.split(r'■\s*종목명:', report_text)
    
    for block in blocks[1:]:  # skip header before first ■
        parsed = {
            "name": "", "ticker": "", "theme": "",
            "buy_price": "분석 중", "target_price": "분석 중", "stop_loss": "분석 중",
            "reasons": []
        }
        
        # Extract name & ticker
        name_match = re.search(r'^\s*(.+?)\s*\((\d{6})\)', block)
        if name_match:
            parsed["name"] = name_match.group(1).strip()
            parsed["ticker"] = name_match.group(2).strip()
        
        # Extract theme
        theme_match = re.search(r'주도\s*테마[:\s]*(.+?)(?:\n|$)', block)
        if theme_match:
            parsed["theme"] = theme_match.group(1).strip()
        
        # Extract buy price
        buy_match = re.search(r'예상\s*매수가[:\s]*(.+?)(?:\n|$)', block)
        if buy_match:
            parsed["buy_price"] = buy_match.group(1).strip().lstrip('💰').strip()
        
        # Extract target price
        target_match = re.search(r'목표\s*매도가[:\s]*(.+?)(?:\n|$)', block)
        if target_match:
            parsed["target_price"] = target_match.group(1).strip().lstrip('🎯').strip()
        
        # Extract stop loss
        stop_match = re.search(r'손절가[:\s]*(.+?)(?:\n|$)', block)
        if stop_match:
            parsed["stop_loss"] = stop_match.group(1).strip().lstrip('🛑').strip()
        
        # Extract recommendation reasons
        reason_match = re.search(r'추천\s*사유[:\s]*(.+?)(?:\n📈|\n💵|\n📋|\n📰|\n-{3,}|$)', block, re.DOTALL)
        if reason_match:
            reason_text = reason_match.group(1).strip()
            # Split by newlines or bullet points
            lines = [l.strip().lstrip('-•·').strip() for l in reason_text.split('\n') if l.strip()]
            parsed["reasons"] = [l for l in lines if len(l) > 5][:5]  # Max 5 reasons
        
        if not parsed["reasons"]:
            parsed["reasons"] = ["Gemini 분석 결과를 기반으로 선정된 종목입니다."]
        
        if parsed["ticker"]:
            stocks_parsed.append(parsed)
    
    return stocks_parsed


def generate_stock_cards(filtered_stocks, report_text):
    """
    Main entry point: generate and send per-stock infographic cards.
    
    Args:
        filtered_stocks: list of dicts from quant_filter (structured data)
        report_text: Gemini-generated report text string
    """
    if not filtered_stocks:
        print("📭 No filtered stocks to generate cards for.")
        return
    
    from notifier import send_telegram_message
    
    # Parse Gemini report for qualitative analysis
    parsed_report = parse_gemini_report(report_text)
    
    # Build a lookup by ticker for quick matching
    parsed_lookup = {p["ticker"]: p for p in parsed_report}
    
    templates_dir = BASE_DIR / 'templates'
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template('stock_card_widget.html')
    
    cards_sent = 0
    total = len(filtered_stocks)
    
    send_telegram_message(f"🎨 종목별 인포그래픽 카드 생성을 시작합니다... ({total}개 종목)")
    
    for idx, stock in enumerate(filtered_stocks, 1):
        ticker = stock["ticker"]
        name = stock["name"]
        
        # Check if the stock was actually selected by Gemini
        if ticker not in parsed_lookup:
            print(f"⏭️ [{idx}/{total}] Skipping {name} ({ticker}) - Not selected by Gemini")
            continue
            
        try:
                    # Get Gemini analysis if available, else use defaults
                    gemini_data = parsed_lookup.get(ticker, {})
                    
                    # Determine sector icon from theme or sector
                    theme_text = gemini_data.get("theme", stock.get("sector", ""))
                    sector_icon = get_sector_icon(theme_text)
                    
                    # Format supply/demand values
                    sd = stock["supply_demand"]
                    organ_eok = sd['organ_val'] / 100_000_000
                    foreigner_eok = sd['foreigner_val'] / 100_000_000
                    individual_eok = sd['individual_val'] / 100_000_000
                    
                    # Format net income 3y
                    ni = stock['net_income_3y']
                    ni_labels = ["2023", "2024", "2025"]
                    ni_strs = []
                    for i, val in enumerate(ni):
                        if val is not None:
                            eok = val / 100_000_000
                            ni_strs.append(f"{ni_labels[i]}({eok:+.0f}억)")
                        else:
                            ni_strs.append(f"{ni_labels[i]}(N/A)")
                    
                    # Format news
                    news_headline = "관련 뉴스 수집 중..."
                    news_source = ""
                    if stock["news"]:
                        news_headline = stock["news"][0]["title"]
                        news_source = stock["news"][0].get("source", "뉴스")
                    
                    # Build template context
                    context = {
                        "sector_icon": sector_icon,
                        "stock_name": name,
                        "stock_ticker": ticker,
                        "stock_market": stock["market"],
                        "stock_theme": theme_text if theme_text else stock.get("sector", "분석 중"),
                        
                        "change_pct": f"{stock['change_pct']:+.2f}%",
                        "change_arrow": "▲" if stock['change_pct'] > 0 else ("▼" if stock['change_pct'] < 0 else ""),
                        "change_color": "up" if stock['change_pct'] > 0 else "down",
                        "volume_text": f"{stock['approx_value'] / 100_000_000:,.0f}억 원",
                        
                        "reco_reasons": gemini_data.get("reasons", ["Gemini 분석 결과를 기반으로 선정된 종목입니다."]),
                        "buy_price": gemini_data.get("buy_price", "분석 중"),
                        "target_price": gemini_data.get("target_price", "분석 중"),
                        "stop_loss": gemini_data.get("stop_loss", "분석 중"),
                        
                        "ma1000_status": "위" if "ABOVE" in stock.get('price_vs_ma_1000', '') else "아래",
                        "current_price": f"{stock['close']:,}원",
                        "ma1000_value": f"{stock['ma_1000']:,.0f}원" if stock.get('ma_1000') else "N/A",
                        "alignment_status": "5-20-60일 정배열" if "Aligned" in stock.get('alignment', '') and "Non" not in stock.get('alignment', '') else "정배열 아님",
                        "volume_ratio": f"{stock['volume_ratio']:.1f}% (20일 평균 대비)",
                        
                        "organ_supply": f"{organ_eok:+.0f}억",
                        "foreigner_supply": f"{foreigner_eok:+.0f}억",
                        "individual_supply": f"{individual_eok:+.0f}억",
                        
                        "ni_y0": ni_strs[0] if len(ni_strs) > 0 else "N/A",
                        "ni_y1": ni_strs[1] if len(ni_strs) > 1 else "N/A",
                        "ni_y2": ni_strs[2] if len(ni_strs) > 2 else "N/A",
                        "debt_ratio": f"{stock['debt_ratios_3y'][0]:.1f}%",
                        "reserve_ratio": f"{stock['reserve_ratios_3y'][0]:.1f}%",
                        
                        "news_headline": news_headline,
                        "news_source": news_source,
                    }
                    
                    html_content = template.render(**context)
                    
                    print(f"🌐 [{idx}/{total}] Rendering stock card for {name} ({ticker})...")
                    
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            with sync_playwright() as p:
                                browser = p.chromium.launch(
                                    headless=True,
                                    args=['--no-sandbox', '--disable-dev-shm-usage']
                                )
                                # 뷰포트 세로 길이를 3000으로 늘려서 스크롤을 방지 (스크롤 중 타임아웃 됨)
                                page = browser.new_page(viewport={"width": 1280, "height": 3000})
                                
                                page.set_content(html_content, wait_until="load", timeout=20000)
                                try:
                                    page.evaluate("document.fonts.ready")
                                except:
                                    pass
                                time.sleep(1)
                                
                                element = page.locator(".card-container")
                                screenshot_bytes = element.screenshot(timeout=15000)
                                browser.close()
                            
                            print(f"📸 [{idx}/{total}] Stock card image for {name} generated successfully.")
                            send_telegram_photo(screenshot_bytes)
                            cards_sent += 1
                            break  # Success, exit retry loop
                            
                        except Exception as inner_e:
                            print(f"⚠️ 렌더링 시도 {attempt + 1}/{max_retries} 실패 ({name}): {str(inner_e)[:200]}")
                            try: browser.close()
                            except: pass
                            if attempt == max_retries - 1:
                                raise inner_e  # Re-raise to outer try-except on final failure
                            time.sleep(2)
                    
        except Exception as e:
            error_msg = f"⚠️ 종목 카드 렌더링 오류 ({name}): {str(e)[:200]}"
            print(error_msg)
            send_telegram_message(error_msg)
    
    print(f"🎉 Total {cards_sent}/{total} stock card(s) sent via Telegram.")

