import requests
from config import TELEGRAM_BOT_TOKEN
from chat_manager import get_all_chat_ids

def send_telegram_message(text):
    """
    Send a message to all configured Telegram chats.
    If the message exceeds 4096 characters, split it into chunks.
    """
    chat_ids = get_all_chat_ids()
    if not TELEGRAM_BOT_TOKEN or not chat_ids:
        print("⚠️ Telegram bot token or chat IDs are missing. Skipping notification.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Telegram max limit is 4096. We slice at 4000 to be safe and avoid breaking markdown tags.
    MAX_LENGTH = 4000
    chunks = []
    
    if len(text) <= MAX_LENGTH:
        chunks.append(text)
    else:
        # Split by paragraphs or newlines to preserve readable formatting
        lines = text.split("\n")
        current_chunk = ""
        for line in lines:
            if len(current_chunk) + len(line) + 1 > MAX_LENGTH:
                chunks.append(current_chunk)
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        if current_chunk:
            chunks.append(current_chunk)
            
    success = True
    for chat_id in chat_ids:
        print(f"Sending Telegram notification to chat {chat_id} in {len(chunks)} message(s)...")
        for idx, chunk in enumerate(chunks, 1):
            payload = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            try:
                r = requests.post(url, json=payload, timeout=15)
                # If markdown parsing fails (e.g. unclosed asterisks), fall back to plain text
                if r.status_code != 200:
                    print(f"⚠️ Telegram returned status {r.status_code}. Retrying without Markdown parsing...")
                    payload.pop("parse_mode", None)
                    r = requests.post(url, json=payload, timeout=15)
                    
                if r.status_code == 200:
                    print(f"✅ Telegram message {idx}/{len(chunks)} sent successfully to {chat_id}.")
                else:
                    print(f"❌ Telegram message {idx}/{len(chunks)} to {chat_id} failed: {r.text}")
                    success = False
            except Exception as e:
                print(f"❌ Exception sending to Telegram chat {chat_id}: {e}")
                success = False
            
    return success

def send_telegram_document(file_path):
    """
    Send a document file to all configured Telegram chats.
    """
    chat_ids = get_all_chat_ids()
    if not TELEGRAM_BOT_TOKEN or not chat_ids:
        print("⚠️ Telegram bot token or chat IDs are missing. Skipping document notification.")
        return False
        
    import os
    if not os.path.exists(file_path):
        print(f"⚠️ File not found: {file_path}")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    
    success = True
    for chat_id in chat_ids:
        print(f"Sending document {file_path} to Telegram chat {chat_id}...")
        try:
            with open(file_path, "rb") as f:
                files = {"document": f}
                payload = {"chat_id": chat_id}
                r = requests.post(url, data=payload, files=files, timeout=30)
                
            if r.status_code == 200:
                print(f"✅ Telegram document sent successfully to {chat_id}.")
            else:
                print(f"❌ Telegram document send to {chat_id} failed: {r.text}")
                success = False
        except Exception as e:
            print(f"❌ Exception sending document to Telegram chat {chat_id}: {e}")
            success = False
            
    return success

def send_telegram_photo(photo_bytes):
    """
    Send an image file (in-memory bytes) to all configured Telegram chats.
    """
    chat_ids = get_all_chat_ids()
    if not TELEGRAM_BOT_TOKEN or not chat_ids:
        print("⚠️ Telegram bot token or chat IDs are missing. Skipping photo notification.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    
    success = True
    for chat_id in chat_ids:
        print(f"Sending photo to Telegram chat {chat_id}...")
        try:
            files = {"photo": ("infographic.png", photo_bytes, "image/png")}
            payload = {"chat_id": chat_id}
            r = requests.post(url, data=payload, files=files, timeout=30)
                
            if r.status_code == 200:
                print(f"✅ Telegram photo sent successfully to {chat_id}.")
            else:
                print(f"❌ Telegram photo send to {chat_id} failed: {r.text}")
                success = False
        except Exception as e:
            print(f"❌ Exception sending photo to Telegram chat {chat_id}: {e}")
            success = False
            
    return success
