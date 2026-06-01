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

def process_updates(updates, screener_callback, index_callback):
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
            send_reply(chat_id, "🏓 봇이 정상적으로 작동 중입니다!\n현재 15:45 지수 정산과 20:00 주도주 리포트 발송을 위해 대기 중입니다.\n\n수동 실행 명령어:\n`/index` - 지수 마감 정산 즉시 실행\n`/run` - 주도주 스크리닝 즉시 실행")
            
        elif text.startswith("/run"):
            send_reply(chat_id, "🔄 즉시 주도주 스크리닝 분석을 시작합니다. 데이터 수집 및 분석에 시간이 다소 소요될 수 있습니다. 잠시만 기다려주세요...")
            if screener_callback:
                threading.Thread(target=screener_callback, daemon=True).start()
                
        elif text.startswith("/index"):
            send_reply(chat_id, "🔄 즉시 지수 마감 정산 분석을 시작합니다. 잠시만 기다려주세요...")
            if index_callback:
                threading.Thread(target=index_callback, daemon=True).start()

def poll_telegram(screener_callback, index_callback):
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
                    process_updates(updates, screener_callback, index_callback)
                    offset = updates[-1]["update_id"] + 1
            elif response.status_code == 409:
                print("⚠️ Telegram API Conflict. Another polling instance might be running. Retrying...")
                time.sleep(10)
            else:
                time.sleep(5)
        except Exception as e:
            time.sleep(5)

def start_bot_listener(screener_callback=None, index_callback=None):
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ No Telegram Bot Token found. Listener won't start.")
        return
        
    listener_thread = threading.Thread(target=poll_telegram, args=(screener_callback, index_callback), daemon=True)
    listener_thread.start()
