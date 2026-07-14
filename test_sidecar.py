import datetime
import sys
sys.stdout.reconfigure(encoding='utf-8')
import index_closing

# 기존 함수 저장
original_fetch = index_closing.fetch_index_data

def mock_fetch_index_data(name, ticker):
    # KOSPI에 대해서 강제로 매수 사이드카(5.2% 상승) 상황 연출
    if name == "KOSPI":
        return {
            "current_close": 2800.0,
            "point_change": 140.0,
            "pct_change": 5.2,
            "local_high_pct": -2.0
        }
    # KOSDAQ에 대해서 강제로 매도 사이드카(-6.5% 하락) 상황 연출
    elif name == "KOSDAQ":
         return {
            "current_close": 750.0,
            "point_change": -52.5,
            "pct_change": -6.5,
            "local_high_pct": -8.0
        }
    return None

def run_test():
    print("🚀 [TEST] 사이드카 알림 테스트 시작...")
    
    # 모킹 적용
    index_closing.fetch_index_data = mock_fetch_index_data
    
    # 상태 초기화 (강제 발송을 위해)
    today = datetime.date.today()
    index_closing.SIDECAR_STATE["date"] = today
    index_closing.SIDECAR_STATE["KOSPI"] = False
    index_closing.SIDECAR_STATE["KOSDAQ"] = False

    # 알림 발송 로직 실행
    index_closing.check_and_send_sidecar_alerts()
    
    print("✅ [TEST] 테스트 완료! 텔레그램 메시지를 확인해주세요.")
    
    # 원상 복구
    index_closing.fetch_index_data = original_fetch

if __name__ == "__main__":
    run_test()
