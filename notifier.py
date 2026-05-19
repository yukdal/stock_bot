import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(text):
    """
    Send a message to the configured Telegram chat.
    If the message exceeds 4096 characters, split it into chunks.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram bot token or chat ID is missing. Skipping notification.")
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
            
    print(f"Sending Telegram notification in {len(chunks)} message(s)...")
    
    success = True
    for idx, chunk in enumerate(chunks, 1):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
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
                print(f"✅ Telegram message {idx}/{len(chunks)} sent successfully.")
            else:
                print(f"❌ Telegram message {idx}/{len(chunks)} failed: {r.text}")
                success = False
        except Exception as e:
            print(f"❌ Exception sending to Telegram: {e}")
            success = False
            
    return success
