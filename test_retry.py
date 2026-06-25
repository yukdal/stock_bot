import time
import sys
from unittest.mock import patch
import main
from report_generator import generate_report

call_count = 0
original_generate_report = generate_report

def mock_generate_report(*args, **kwargs):
    global call_count
    call_count += 1
    if call_count == 1:
        print("💡 [테스트용] 첫 번째 호출: 고의로 에러를 발생시킵니다.")
        raise Exception("강제 테스트 에러: 503 UNAVAILABLE (Simulated)")
    else:
        print("💡 [테스트용] 두 번째 호출: 정상적으로 리포트를 생성합니다.")
        return original_generate_report(*args, **kwargs)

if __name__ == "__main__":
    print("========================================")
    print("🚀 재시도 로직(Retry) 테스트를 시작합니다.")
    print("========================================")
    
    # main.py 내의 time.sleep과 generate_report를 가로채기(mocking)합니다.
    # 이렇게 하면 원본 코드를 수정하지 않고도 테스트가 가능합니다.
    with patch("main.time.sleep") as mock_sleep:
        def mock_sleep_impl(secs):
            print(f"\n💡 [테스트용] 원래 {secs}초를 기다려야 하지만, 빠른 테스트를 위해 5초만 대기합니다...")
            time.sleep(5)
            
        mock_sleep.side_effect = mock_sleep_impl
        
        with patch("main.generate_report", side_effect=mock_generate_report):
            # 봇의 메인 파이프라인(스크리닝 -> 리포트 -> 텔레그램 전송)을 단발성으로 실행합니다.
            main.execute_pipeline(is_nxt=False)
            
    print("\n✅ 테스트 완료! 텔레그램 메세지를 확인해보세요.")
