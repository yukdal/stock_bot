import sys
sys.stdout.reconfigure(encoding='utf-8')
from notifier import send_telegram_message

name = 'KOSDAQ (테스트)'
current_10_level = 30
buy_tier = 1
c_close = '712.45'
pt_chg = '▼15.22'
pct_chg = '-2.09%'
actual_drop_pct = '-32.05'

msg = f"🚨 시장 급락 경보 {name} 직전 고점 대비 -{current_10_level}% 돌파! 🚨\n\n"
msg += f"현재 지수가 최근 전고점 대비 심각한 하락 구간에 진입하여 <b>[{buy_tier}차 매수 추천]</b> 알림을 발송합니다.\n"
msg += f"■ 현재 {name} 지수: {c_close} ({pt_chg}pt, {pct_chg})\n"
msg += f"<b>■ 전고점 대비 하락률: {actual_drop_pct}%</b>\n\n"
msg += "투심 악화 및 반대매매 물량 출회 가능성에 유의하시되, 룰 베이스 분할 매수 전략에 의거해 대응하시길 바랍니다.\n\n"
msg += "💡 연동 상품 실시간 현재가:\n\n"
msg += "KODEX 코스닥150 (229200): 15,480원 (-6.89%)\n\n"
msg += "KODEX 코스닥150레버리지 (233740): 9,320원 (-14.10%)"

send_telegram_message(msg, parse_mode="HTML")
print("Test message sent to all chats!")
