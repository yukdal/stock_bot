import os
import sys
import argparse
import datetime
import time
import socket
import schedule
import pandas as pd
from pathlib import Path
from config import validate_config
from quant_filter import run_quant_filtering
from report_generator import generate_report
from notifier import send_telegram_message, send_telegram_document
from bot_listener import start_bot_listener
from index_closing import execute_index_closing, check_and_send_crash_alerts

BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

def execute_pipeline(is_nxt=False):
    """
    Core pipeline:
    1. Check if today is weekend (skip if Saturday or Sunday)
    2. Quant filtering
    3. Gemini report generation
    4. Save report locally
    5. Send Telegram notification
    """
    today = datetime.date.today()
    pipeline_type = "NXT-Inclusive " if is_nxt else ""
    print(f"\n🔔 [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting {pipeline_type}Screener Pipeline...")
    
    # Skip weekends in standard run
    if today.weekday() >= 5:
        print("📅 Today is a weekend. The Korean stock market is closed. Skipping run.")
        return
        
    try:
        # 1. Run Quantitative and DART Financial Filters
        filtered_stocks, analysis_log = run_quant_filtering(is_nxt=is_nxt)
        
        # Save analysis log to CSV for Notion import
        csv_path = None
        if analysis_log:
            df_log = pd.DataFrame(analysis_log)
            date_str = today.strftime("%Y%m%d")
            file_suffix = "_NXT" if is_nxt else ""
            csv_path = REPORTS_DIR / f"analysis_source_{date_str}{file_suffix}.csv"
            df_log.to_csv(csv_path, index=False, encoding="utf-8-sig")
            print(f"📊 Analysis source data saved locally to {csv_path}")
        
        # 2. Generate Analyst Report
        while True:
            try:
                report_text = generate_report(filtered_stocks, analysis_log, is_nxt=is_nxt)
                break
            except Exception as api_err:
                error_msg = (
                    f"⚠️ **[안내] 현재 AI 분석이 불가능하여 목업(Mock) 데이터만 사용 가능한 상태입니다.**\n\n"
                    f"- 원인: {api_err}\n"
                    f"- 안내: 부정확한 목업 데이터 기반의 종목 분석은 진행하지 않습니다.\n"
                    f"- 조치: 30분 단위로 자동 재시도하며, 정상적으로 AI 분석이 가능한 시점에 종목 분석 리포트를 생성하여 알려드리겠습니다."
                )
                print(error_msg)
                send_telegram_message(error_msg)
                time.sleep(1800)
        
        # 3. Save Report Locally
        date_str = today.strftime("%Y%m%d")
        file_suffix = "_NXT" if is_nxt else ""
        report_path = REPORTS_DIR / f"report_{date_str}{file_suffix}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"💾 Report saved locally to {report_path}")
        
        # 4. Dispatch Telegram Notification
        send_telegram_message(report_text)
        if csv_path:
            send_telegram_document(csv_path)
        
        # 5. Generate per-stock infographic cards (1 image per TOP pick)
        if filtered_stocks:
            try:
                from stock_card_generator import generate_stock_cards
                # Use a specific output dir or name logic for NXT if needed, but it's okay to overwrite or just generate
                generate_stock_cards(filtered_stocks, report_text)
            except Exception as card_err:
                import traceback
                tb = traceback.format_exc()
                error_msg = f"⚠️ 종목 카드 생성 모듈 로딩 오류:\n{str(card_err)}\n\n{tb[-500:]}"
                print(error_msg)
                send_telegram_message(error_msg)
            
        print(f"🎉 {pipeline_type}Screener pipeline run finished successfully!")
        
    except Exception as e:
        print(f"❌ Error occurred during pipeline execution: {e}")

LOCK_PORT = 18386
lock_socket = None

def acquire_process_lock():
    """
    중복 실행을 방지하기 위해 로컬 소켓을 바인딩합니다.
    이미 다른 스케줄러 인스턴스가 돌고 있다면 에러와 함께 종료됩니다.
    """
    global lock_socket
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', LOCK_PORT))
    except socket.error:
        print(f"\n❌ [중복 실행 방지] 이미 봇 스케줄러 인스턴스가 실행 중입니다. (포트 {LOCK_PORT} 사용 중) 프로그램을 종료합니다.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="K-Stock Quant & DART Swing Screener")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run the screening pipeline immediately and exit."
    )
    parser.add_argument(
        "--now-nxt",
        action="store_true",
        help="Run the NXT-inclusive screening pipeline immediately and exit."
    )
    parser.add_argument(
        "--now-index",
        action="store_true",
        help="Run the index closing settlement immediately and exit."
    )
    args = parser.parse_args()
    
    # Validate .env config
    validate_config(test_mode=True)
    
    if args.now:
        print("🏃 Running manual one-off execution...")
        execute_pipeline(is_nxt=False)
        sys.exit(0)
        
    if args.now_nxt:
        print("🏃 Running manual one-off NXT-inclusive execution...")
        execute_pipeline(is_nxt=True)
        sys.exit(0)
        
    if args.now_index:
        print("🏃 Running manual one-off index settlement execution...")
        execute_index_closing()
        sys.exit(0)
        
    # Schedule mode
    # 중복 실행 방지 락 획득 (OCI 및 로컬 겸용)
    acquire_process_lock()
    
    print("🕰️ Starting daily robust scheduler mode...")
    print("📅 Index Settlement is scheduled to run every Mon-Fri at 15:45 KST.")
    print("📅 KRX Screener is scheduled to run every Mon-Fri at 20:00 KST.")
    print("📅 NXT Screener is scheduled to run every Mon-Fri at 21:00 KST.")
    print("👉 Use Ctrl+C to terminate.")
    
    # 봇 시작 알림 텔레그램 발송
    send_telegram_message("🚀 [시스템 알림] 스윙종목 분석 봇이 정상 작동을 시작했습니다. (스케줄러 대기 중)")
    
    # Define a wrapper to run jobs in background threads so they don't block the scheduler
    def run_threaded(job_func, *args, **kwargs):
        import threading
        job_thread = threading.Thread(target=job_func, args=args, kwargs=kwargs)
        job_thread.daemon = True
        job_thread.start()

    # Start bot listener thread in the background
    def screener_nxt_wrapper():
        execute_pipeline(is_nxt=True)
        
    start_bot_listener(screener_callback=screener_nxt_wrapper, index_callback=execute_index_closing)
    
    # Keep the script running with robust custom time checking
    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    last_run_index = None
    last_run_nxt = None
    last_crash_check = None
    
    # Catch-up logic on startup
    now_kst = datetime.datetime.now(kst_tz)
    current_date = now_kst.date()
    
    if now_kst.time() >= datetime.time(15, 45) and current_date.weekday() < 5:
        print("🚀 Startup Check: Triggering 15:45 KST Index Settlement immediately...")
        run_threaded(execute_index_closing)
        last_run_index = current_date
        
    if now_kst.time() >= datetime.time(21, 0) and current_date.weekday() < 5:
        print("🚀 Startup Check: Triggering 21:00 KST NXT Screener immediately...")
        run_threaded(execute_pipeline, is_nxt=True)
        last_run_nxt = current_date
    
    try:
        while True:
            now_kst = datetime.datetime.now(kst_tz)
            current_time = now_kst.strftime("%H:%M")
            current_date = now_kst.date()
            
            # 30-minute index crash monitor (09:00 ~ 15:30)
            if now_kst.time() >= datetime.time(9, 0) and now_kst.time() <= datetime.time(15, 30) and current_date.weekday() < 5:
                if current_time.endswith(":00") or current_time.endswith(":30"):
                    if last_crash_check != current_time:
                        run_threaded(check_and_send_crash_alerts)
                        last_crash_check = current_time
            
            # 15:45 KST: Index closing settlement
            if current_time == "15:45" and last_run_index != current_date:
                print(f"⏰ Triggering 15:45 KST Index Settlement...")
                run_threaded(execute_index_closing)
                last_run_index = current_date
                
            # 21:00 KST: Screener pipeline (NXT)
            if current_time == "21:00" and last_run_nxt != current_date:
                print(f"⏰ Triggering 21:00 KST Screener (NXT)...")
                run_threaded(execute_pipeline, is_nxt=True)
                last_run_nxt = current_date
                
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n👋 Scheduler terminated by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()
