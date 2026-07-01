import requests
import time
import os
from pathlib import Path

def update_env_file(env_path, token, chat_id):
    """
    Update or create TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in the specified .env file.
    """
    if not env_path.exists():
        print(f"📝 Creating new .env file at {env_path}")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"TELEGRAM_BOT_TOKEN={token}\nTELEGRAM_CHAT_ID={chat_id}\n")
        return
        
    # Read existing content
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    updated_lines = []
    token_replaced = False
    chat_replaced = False
    
    for line in lines:
        if line.strip().startswith("TELEGRAM_BOT_TOKEN="):
            updated_lines.append(f"TELEGRAM_BOT_TOKEN={token}\n")
            token_replaced = True
        elif line.strip().startswith("TELEGRAM_CHAT_ID="):
            updated_lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")
            chat_replaced = True
        else:
            updated_lines.append(line)
            
    if not token_replaced:
        updated_lines.append(f"TELEGRAM_BOT_TOKEN={token}\n")
    if not chat_replaced:
        updated_lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")
        
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)
    print(f"✅ Successfully updated {env_path.name}")

def main():
    print("==================================================")
    print("🤖 Telegram Bot & Chat ID Auto-Configuration Helper")
    print("==================================================")
    print("\n[Step 1] Create your new Bot:")
    print("1. Search for @BotFather in Telegram.")
    print("2. Send '/newbot' command.")
    print("3. Follow instructions to set the Bot name and username.")
    print("4. BotFather will send you an HTTP API Token (e.g. 123456789:ABCdef...).")
    
    token = input("\n👉 Paste your new Telegram Bot Token here: ").strip()
    if not token:
        print("❌ Token cannot be empty. Exiting.")
        return
        
    print("\n[Step 2] Link your Chat:")
    print("1. Click the link to your new bot provided by BotFather (e.g. t.me/YourBotName).")
    print("2. Click the 'Start' button or send any message (e.g., 'Hello') to the bot.")
    print("\n⏳ Listening for messages to your bot... Please send a message now.")
    
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    
    chat_id = None
    first_name = "User"
    
    # Try polling for up to 60 seconds
    for attempt in range(30):
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                results = data.get("result", [])
                if results:
                    # Get the chat ID from the latest message
                    latest_msg = results[-1]
                    if "message" in latest_msg:
                        chat_info = latest_msg["message"]["chat"]
                        chat_id = chat_info["id"]
                        first_name = chat_info.get("first_name", "User")
                        break
            else:
                print(f"⚠️ API status {r.status_code}. Make sure your token is correct.")
        except Exception as e:
            print(f"⚠️ Connection error: {e}")
            
        time.sleep(2)
        print(".", end="", flush=True)
        
    print()
    if not chat_id:
        print("\n❌ Could not detect any messages. Did you click 'Start' or send a message to the bot?")
        print("Please rerun this script once you have sent a message to the bot.")
        return
        
    print(f"\n🎉 Connection Successful!")
    print(f"👤 User Name: {first_name}")
    print(f"🆔 Chat ID  : {chat_id}")
    
    confirm = input("\n💾 Would you like to save these credentials to your .env files? (y/n): ").strip().lower()
    if confirm == "y" or confirm == "":
        # Update .env in both swing screener and price limit folders
        parent_dir = Path(__file__).resolve().parent
        
        # 1. Update current folder .env
        update_env_file(parent_dir / ".env", token, chat_id)
            
        print("\n✨ Configuration update completed! You are ready to run the bots.")
    else:
        print("\nSkipped saving credentials.")

if __name__ == "__main__":
    main()
