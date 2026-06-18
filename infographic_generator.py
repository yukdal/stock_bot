import os
import time
import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from notifier import send_telegram_photo

BASE_DIR = Path(__file__).resolve().parent

def get_comment_for_index(name, point_change, pct_change, local_high_pct):
    if name == "KOSPI":
        if local_high_pct > -3:
            return "전고점 회복에 바짝 다가섰습니다."
        elif point_change > 0:
            return "상승세로 마감하며 분위기 반전을 시도하고 있습니다."
        else:
            return "하락 마감하며 저항선 돌파에 어려움을 겪고 있습니다."
    elif name == "KOSDAQ":
        if point_change > 0:
            return "당일 강세를 보였으나 전고점 대비로는 여전히 격차가 있습니다."
        else:
            return "약세를 보이며 하단 지지력을 시험받고 있습니다."
    elif name == "S&P 500":
        if point_change < 0:
            return "소폭 하락하며 전고점 대비 아래 위치를 기록했습니다."
        elif local_high_pct > -1:
            return "전고점을 돌파하거나 근접하며 강한 흐름을 유지하고 있습니다."
        else:
            return "상승세를 이어가며 견조한 흐름을 보이고 있습니다."
    return "시장 상황을 주시하고 있습니다."

def generate_and_send_infographic(indices_data, macro_comment):
    """
    indices_data: dict with keys like "KOSPI", "KOSDAQ", "S&P 500"
    and values from fetch_index_data.
    """
    try:
        templates_dir = BASE_DIR / 'templates'
        templates_dir.mkdir(exist_ok=True)
        
        env = Environment(loader=FileSystemLoader(str(templates_dir)))
        template = env.get_template('infographic_widget.html')
        
        # Prepare context
        context = {
            "date_str": datetime.datetime.now().strftime("%Y년 %m월 %d일"),
            "macro_comment": macro_comment
        }
        
        for name, data in indices_data.items():
            prefix = name.lower().replace("&", "").replace(" ", "")
            
            if data:
                c_close = f"{data['current_close']:,.2f}"
                pt = data['point_change']
                pct = data['pct_change']
                lh_pct = data['local_high_pct']
                
                arrow = "▲" if pt > 0 else ("▼" if pt < 0 else "")
                color = "up" if pt > 0 else ("down" if pt < 0 else "neutral")
                
                pt_str = f"+{pt:.2f}" if pt > 0 else f"{pt:.2f}"
                pct_str = f"+{pct:.2f}%" if pct > 0 else f"{pct:.2f}%"
                
                # 전고점 대비는 부호와 소수점 2자리 고정
                lh_str = f"+{lh_pct:.2f}%" if lh_pct > 0 else f"{lh_pct:.2f}%"
                
                comment = get_comment_for_index(name, pt, pct, lh_pct)
                
                context[f"{prefix}_close"] = c_close
                context[f"{prefix}_pt"] = pt_str
                context[f"{prefix}_pct"] = pct_str
                context[f"{prefix}_lh"] = lh_str
                context[f"{prefix}_arrow"] = arrow
                context[f"{prefix}_color"] = color
                context[f"{prefix}_comment"] = comment
            else:
                context[f"{prefix}_close"] = "N/A"
                context[f"{prefix}_pt"] = "0.00"
                context[f"{prefix}_pct"] = "0.00%"
                context[f"{prefix}_arrow"] = "-"
                context[f"{prefix}_color"] = "neutral"
                context[f"{prefix}_comment"] = "데이터 수집 지연"
                
                # Fallback values as requested
                if name == "KOSPI": context[f"{prefix}_lh"] = "-0.78%"
                elif name == "KOSDAQ": context[f"{prefix}_lh"] = "-16.06%"
                elif name == "S&P 500": context[f"{prefix}_lh"] = "-1.44%"
                else: context[f"{prefix}_lh"] = "-"

        html_content = template.render(**context)
        
        print("🌐 Rendering HTML with Playwright...")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            page = browser.new_page()
            
            # Set HTML content and wait for fonts to load
            page.set_content(html_content, wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            time.sleep(2) # Extra wait for web fonts to apply completely before screenshot
            
            # Select the widget-container to take a screenshot of just that element
            element = page.locator(".widget-container")
            screenshot_bytes = element.screenshot()
            
            browser.close()
            
        print("📸 Infographic image generated successfully.")
        
        # Send via Telegram
        send_telegram_photo(screenshot_bytes)
        
    except Exception as e:
        error_msg = f"❌ 인포그래픽 이미지 렌더링 중 오류가 발생했습니다:\n`{str(e)}`\n\n(Playwright/크롬 브라우저 실행 문제일 가능성이 높습니다)"
        print(error_msg)
        from notifier import send_telegram_message
        send_telegram_message(error_msg)
