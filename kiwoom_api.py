import os
import json
import time
import requests
import datetime
from pathlib import Path
from config import KIWOOM_APP_KEY, KIWOOM_APP_SECRET, CACHE_DIR

KIWOOM_URL_BASE = "https://openapi.kiwoom.com" # Updated to production REST API url or proxy if needed. But the user's code had "https://api.kiwoom.com". I'll stick to user's code.
KIWOOM_URL_BASE = "https://api.kiwoom.com"
TOKEN_FILE = CACHE_DIR / "kiwoom_token.json"

def get_kiwoom_access_token():
    """
    Get Access Token from Kiwoom REST API. Uses cached token if valid.
    """
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
            # check expiry (Kiwoom tokens usually expire in 86400 seconds / 24 hours)
            if time.time() < data.get("expires_at", 0):
                return data["access_token"]
                
    # Issue new token
    url = f"{KIWOOM_URL_BASE}/oauth2/token"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": KIWOOM_APP_KEY,
        "secretkey": KIWOOM_APP_SECRET
    }
    
    res = requests.post(url, headers=headers, json=body, timeout=10)
    if res.status_code == 200:
        token_data = res.json()
        access_token = token_data.get("token") or token_data.get("access_token")
        
        # Save to cache
        cache_data = {
            "access_token": access_token,
            "expires_at": time.time() + 86400 - 300 # buffer of 5 mins
        }
        with open(TOKEN_FILE, "w") as f:
            json.dump(cache_data, f)
            
        return access_token
    else:
        print(f"❌ Failed to get Kiwoom access token: {res.text}")
        return None

def fetch_kiwoom_daily_price(ticker, base_dt=None):
    """
    Fetch daily price history from Kiwoom REST API (ka10081).
    Returns roughly 600 days of data at once.
    Data format is converted to match KIS API format (stck_clpr, acml_vol, stck_bsop_date).
    """
    token = get_kiwoom_access_token()
    if not token:
        return None
        
    url = f"{KIWOOM_URL_BASE}/api/dostk/chart"
    
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}",
        "appkey": KIWOOM_APP_KEY,
        "appsecret": KIWOOM_APP_SECRET,
        "api-id": "ka10081",
        "cont-yn": "N"
    }
    
    if not base_dt:
        base_dt = datetime.date.today().strftime("%Y%m%d")
        
    body = {
        "stk_cd": ticker,
        "base_dt": base_dt,
        "upd_stkpc_tp": "1" # 수정주가 적용
    }
    
    res = requests.post(url, headers=headers, json=body, timeout=10)
    if res.status_code == 200:
        data = res.json()
        chart_data = data.get("stk_dt_pole_chart_qry", [])
        
        if not chart_data:
            return []
            
        # Transform data to match KIS API keys
        transformed_data = []
        for row in chart_data:
            transformed_data.append({
                "stck_bsop_date": row.get("dt"),
                "stck_clpr": row.get("cur_prc"),
                "acml_vol": row.get("trde_qty")
            })
            
        return transformed_data
    else:
        print(f"⚠️ Kiwoom API Error for {ticker}: {res.status_code} {res.text}")
        return []

if __name__ == "__main__":
    print("Testing Kiwoom API Token...")
    token = get_kiwoom_access_token()
    print("Token fetched." if token else "Failed to fetch token.")
    if token:
        print("Testing price fetch for 005930...")
        hist = fetch_kiwoom_daily_price("005930")
        if hist:
            print(f"Fetched {len(hist)} days from Kiwoom. Latest: {hist[0]}")

def get_kiwoom_current_index(market_type):
    """
    Fetch current real-time index from Kiwoom.
    market_type: "KOSPI" or "KOSDAQ"
    """
    # Note: Kiwoom REST API usually requires different API ID for indices (e.g. opt20001).
    # Since we don't have the exact REST endpoint for index current price in this wrapper yet,
    # we leave it as a template that returns None to trigger the next fallback (Toss/Naver).
    token = get_kiwoom_access_token()
    if not token:
        return None
        
    return None

