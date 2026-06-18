import requests
from config import TELEGRAM_BOT_TOKEN

url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
try:
    response = requests.get(url, timeout=10)
    print("Status Code:", response.status_code)
    print("Response JSON:", response.json())
except Exception as e:
    print("Error:", e)
