import requests
from config import TELEGRAM_BOT_TOKEN
from chat_manager import get_all_chat_ids

def send_telegram_message(text, chat_id=None):
    """
    Send a message to all configured Telegram chats, or a specific chat_id if provided.
    If the message exceeds 4096 characters, split it into chunks.
    """
    chat_ids = [chat_id] if chat_id else get_all_chat_ids()
    if not TELEGRAM_BOT_TOKEN or not chat_ids:
        print("⚠️ Telegram bot token or chat IDs are missing. Skipping notification.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Telegram max limit is 4096. We slice at 4000 to be safe and avoid breaking markdown tags.
    MAX_LENGTH = 4000
    chunks = []
    
    # 1. Pre-split by explicit delimiter if present
    pre_chunks = text.split("<!-- SPLIT_HERE -->")
    
    for pt in pre_chunks:
        pt = pt.strip()
        if not pt:
            continue
            
        if len(pt) <= MAX_LENGTH:
            chunks.append(pt)
        else:
            # 2. Split by newlines to preserve readable formatting
            lines = pt.split("\n")
            current_chunk = ""
            in_table = False
            table_header = ""
            
            for line in lines:
                # Detect markdown table separator line (e.g., | :--- | :--- |)
                if line.strip().startswith("|") and ":---" in line.replace(" ", ""):
                    in_table = True
                    # The previous line is the column names
                    prev_line = current_chunk.strip().split("\n")[-1] if current_chunk.strip() else ""
                    table_header = prev_line + "\n" + line + "\n"
                elif in_table and line.strip() != "" and not line.strip().startswith("|"):
                    in_table = False
                    
                if len(current_chunk) + len(line) + 1 > MAX_LENGTH:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                    if in_table and table_header:
                        current_chunk = table_header
                    current_chunk += line + "\n"
                else:
                    current_chunk += line + "\n"
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            
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
