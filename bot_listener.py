import time
import requests
import threading
from config import TELEGRAM_BOT_TOKEN
from chat_manager import add_chat_id

def send_reply(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ Error sending reply to {chat_id}: {e}")

def process_updates(updates, run_callback):
    for update in updates:
        message = update.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = message.get("text", "")
        
        if not chat_id:
            # Handle my_chat_member event (bot added to group)
            my_chat_member = update.get("my_chat_member", {})
            chat = my_chat_member.get("chat", {})
            chat_id = chat.get("id")
            new_status = my_chat_member.get("new_chat_member", {}).get("status")
            if chat_id and new_status in ["member", "administrator"]:
                if add_chat_id(chat_id):
                    send_reply(chat_id, "🤖 안녕하세요! 스윙종목 분석 봇입니다. 등록이 완료되어 앞으로 이 방에 매일 리포트를 보내드릴게요. 작동 확인을 원하시면 `/ping` 명령어를 입력해주세요.")
            continue
            
        # Message processing
        if text.startswith("/start"):
            if add_chat_id(chat_id):
                send_reply(chat_id, "🤖 안녕하세요! 스윙종목 분석 봇입니다. 등록이 완료되어 앞으로 이 방에 매일 리포트를 보내드릴게요. 작동 확인을 원하시면 `/ping` 명령어를 입력해주세요.")
            else:
                send_reply(chat_id, "이미 등록된 채팅방입니다. 매일 리포트를 보내드릴게요!")
                
        elif text.startswith("/ping"):
            send_reply(chat_id, "🏓 봇이 정상적으로 작동 중입니다!\n현재 20:00 KST에 리포트를 발송하기 위해 대기 중입니다. 수동으로 실행하려면 `/run` 명령어를 입력하세요.")
            
        elif text.startswith("/run"):
            send_reply(chat_id, "🔄 즉시 분석을 시작합니다. 데이터 수집 및 분석에 시간이 다소 소요될 수 있습니다. 잠시만 기다려주세요...")
            # Run in a separate thread so we don't block the listener
            if run_callback:
                threading.Thread(target=run_callback, daemon=True).start()

def poll_telegram(run_callback):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    offset = None
    
    print("🎧 Bot listener thread started. Listening for Telegram messages...")
    
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message", "my_chat_member"]}
            if offset:
                params["offset"] = offset
                
            response = requests.get(url, params=params, timeout=40)
            if response.status_code == 200:
                data = response.json()
                updates = data.get("result", [])
                
                if updates:
                    process_updates(updates, run_callback)
                    offset = updates[-1]["update_id"] + 1
            elif response.status_code == 409:
                error_msg = "🚨 [좀비 봇 감지 알림]\n다른 서버(또는 다른 폴더)에서 동일한 토큰으로 봇이 실행 중이어서 충돌(409 Conflict)이 발생했습니다!\n\n이로 인해 리포트가 2개씩 중복 발송되고 있습니다. 중복 발송을 막으려면 반드시 텔레그램 @BotFather 에 가셔서 토큰을 새로 발급(Revoke) 받아주세요."
                print(error_msg)
                
                # 등록된 모든 채팅방에 경고 메시지 발송
                from chat_manager import get_all_chat_ids
                chat_ids = get_all_chat_ids()
                for cid in chat_ids:
                    send_reply(cid, error_msg)
                    
                print("좀비 봇 충돌로 인해 현재 프로세스를 종료합니다. 새 토큰으로 변경 후 다시 실행해주세요.")
                import sys
                sys.exit(1)
            else:
                time.sleep(5)
        except Exception as e:
            time.sleep(5)

def start_bot_listener(run_callback=None):
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ No Telegram Bot Token found. Listener won't start.")
        return
        
    listener_thread = threading.Thread(target=poll_telegram, args=(run_callback,), daemon=True)
    listener_thread.start()
