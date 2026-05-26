import os
import sys
import argparse
import datetime
import time
import schedule
import pandas as pd
from pathlib import Path
from config import validate_config
from quant_filter import run_quant_filtering
from report_generator import generate_report
from notifier import send_telegram_message, send_telegram_document
from bot_listener import start_bot_listener
import threading

# Global lock to prevent concurrent executions
pipeline_lock = threading.Lock()

BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

def execute_pipeline():
    """
    Core pipeline:
    1. Check if today is weekend (skip if Saturday or Sunday)
    2. Quant filtering
    3. Gemini report generation
    4. Save report locally
    5. Send Telegram notification
    """
    if not pipeline_lock.acquire(blocking=False):
        print("⚠️ Pipeline is already running. Skipping this execution request.")
        return

    try:
        today = datetime.date.today()
        print(f"\n🔔 [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Screener Pipeline...")
        
        # Skip weekends in standard run
        if today.weekday() >= 5:
            print("📅 Today is a weekend. The Korean stock market is closed. Skipping run.")
            return
            
        # 1. Run Quantitative and DART Financial Filters
        filtered_stocks, analysis_log = run_quant_filtering()
        
        # Save analysis log to CSV for Notion import
        csv_path = None
        if analysis_log:
            df_log = pd.DataFrame(analysis_log)
            date_str = today.strftime("%Y%m%d")
            csv_path = REPORTS_DIR / f"analysis_source_{date_str}.csv"
            df_log.to_csv(csv_path, index=False, encoding="utf-8-sig")
            print(f"📊 Analysis source data saved locally to {csv_path}")
        
        # 2. Generate Analyst Report
        report_text = generate_report(filtered_stocks, analysis_log)
        
        # 3. Save Report Locally
        date_str = today.strftime("%Y%m%d")
        report_path = REPORTS_DIR / f"report_{date_str}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"💾 Report saved locally to {report_path}")
        
        # 4. Dispatch Telegram Notification
        send_telegram_message(report_text)
        if csv_path:
            send_telegram_document(csv_path)
            
        print("🎉 Screener pipeline run finished successfully!")
        
    except Exception as e:
        print(f"❌ Error occurred during pipeline execution: {e}")
    finally:
        pipeline_lock.release()
        print("🔓 Pipeline lock released.")

def main():
    parser = argparse.ArgumentParser(description="K-Stock Quant & DART Swing Screener")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run the screening pipeline immediately and exit."
    )
    args = parser.parse_args()
    
    # Validate .env config
    validate_config(test_mode=True)
    
    if args.now:
        print("🏃 Running manual one-off execution...")
        execute_pipeline()
        sys.exit(0)
        
    # Schedule mode
    print("🕰️ Starting daily scheduler mode...")
    
    # Calculate local system time corresponding to 20:00 KST
    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    kst_target = datetime.datetime.combine(datetime.date.today(), datetime.time(20, 0)).replace(tzinfo=kst_tz)
    local_target = kst_target.astimezone()
    local_time_str = local_target.strftime("%H:%M")
    
    print(f"📅 Screener is scheduled to run every day at 20:00 KST (System Local Time: {local_time_str}).")
    print("👉 Use Ctrl+C to terminate.")
    
    # Start bot listener thread in the background
    start_bot_listener(run_callback=execute_pipeline)
    
    # Schedule daily at system local time equivalent to 20:00 KST
    schedule.every().day.at(local_time_str).do(execute_pipeline)
    
    # Keep the script running
    try:
        while True:
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n👋 Scheduler terminated by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()
