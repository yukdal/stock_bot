import os
import json
import time
import requests
import datetime
from pathlib import Path
from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_ENV, CACHE_DIR

# Base URL setup
if KIS_ENV.upper() == "PROD":
    KIS_URL_BASE = "https://openapi.koreainvestment.com:9443"
else:
    KIS_URL_BASE = "https://openapivts.koreainvestment.com:29443"

TOKEN_FILE = CACHE_DIR / "kis_token.json"

def get_access_token():
    """
    Get Access Token from KIS. Uses cached token if valid.
    Tokens are valid for 24 hours.
    """
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
            # check expiry
            if time.time() < data.get("expires_at", 0):
                return data["access_token"]
                
    # Issue new token
    url = f"{KIS_URL_BASE}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET
    }
    
    res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
    if res.status_code == 200:
        token_data = res.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 86400) # usually 86400 sec (24h)
        
        # Save to cache
        cache_data = {
            "access_token": access_token,
            "expires_at": time.time() + expires_in - 300 # buffer of 5 mins
        }
        with open(TOKEN_FILE, "w") as f:
            json.dump(cache_data, f)
            
        return access_token
    else:
        print(f"❌ Failed to get KIS access token: {res.text}")
        return None

def fetch_daily_price(ticker):
    """
    Fetch daily price history for technical indicators (MA1000, 5/20/60, volume ratio)
    Combines Kiwoom API (latest 600 days) and KIS API (older 600 days) for optimal speed.
    """
    all_data = []
    
    # 1. Try to fetch latest ~600 days from Kiwoom
    try:
        from kiwoom_api import fetch_kiwoom_daily_price
        kiwoom_data = fetch_kiwoom_daily_price(ticker)
        if kiwoom_data:
            all_data.extend(kiwoom_data)
            print(f"   -> Fetched {len(kiwoom_data)} days from Kiwoom API.")
    except Exception as e:
        print(f"⚠️ Failed to fetch from Kiwoom API: {e}")
        
    # Set the end_date for KIS API
    today = datetime.date.today()
    end_date = today.strftime("%Y%m%d")
    
    # If we got data from Kiwoom, start fetching from the day before Kiwoom's oldest data
    if all_data:
        last_date_str = all_data[-1].get("stck_bsop_date")
        if last_date_str:
            end_date = (datetime.datetime.strptime(last_date_str, "%Y%m%d") - datetime.timedelta(days=1)).strftime("%Y%m%d")
            
    # Calculate how many more chunks (100 days each) we need to reach ~1200 days total
    # If Kiwoom gave us 600, we need about 6 chunks from KIS. If 0, we need 12.
    remaining_days = max(0, 1200 - len(all_data))
    chunks_needed = (remaining_days // 100) + 1 if remaining_days > 0 else 0
    
    if chunks_needed > 0:
        token = get_access_token()
        if not token:
            print("⚠️ Failed to get KIS token.")
            return all_data
            
        url = f"{KIS_URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appKey": KIS_APP_KEY,
            "appSecret": KIS_APP_SECRET,
            "tr_id": "FHKST03010100", # 주식당일추이 API or 일자별 시세
        }
        
        for i in range(chunks_needed):
            start_date = (datetime.datetime.strptime(end_date, "%Y%m%d") - datetime.timedelta(days=120)).strftime("%Y%m%d")
            
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": ticker,
                "FID_INPUT_DATE_1": start_date,
                "FID_INPUT_DATE_2": end_date,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0" 
            }
            
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("rt_cd") == "0":
                    chunk = data.get("output2", [])
                    if not chunk:
                        break
                    all_data.extend(chunk)
                    
                    last_date_str = chunk[-1].get("stck_bsop_date")
                    if last_date_str:
                        end_date = (datetime.datetime.strptime(last_date_str, "%Y%m%d") - datetime.timedelta(days=1)).strftime("%Y%m%d")
                    else:
                        break
                else:
                    break
            else:
                break
                
            time.sleep(0.1)
            
    return all_data

def fetch_investor_trend(ticker):
    """
    Fetch foreign/institutional investor trend.
    TR_ID: FHKST01010900 (주식당일매매종합) - 외국인/기관 수급
    """
    token = get_access_token()
    if not token:
        return None
        
    url = f"{KIS_URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-investor"
    
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appKey": KIS_APP_KEY,
        "appSecret": KIS_APP_SECRET,
        "tr_id": "FHKST01010900",
    }
    
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": ticker
    }
    
    res = requests.get(url, headers=headers, params=params, timeout=10)
    if res.status_code == 200:
        data = res.json()
        if data.get("rt_cd") == "0":
            output = data.get("output", [])
            if output:
                return output[0] # latest day
        else:
            print(f"⚠️ KIS Investor API Error for {ticker}: {data.get('msg1')}")
            return None
    return None

if __name__ == "__main__":
    # Simple test
    print("Testing KIS API Token...")
    token = get_access_token()
    print("Token fetched." if token else "Failed to fetch token.")
    if token:
        print("Testing price fetch for 005930...")
        hist = fetch_daily_price("005930")
        if hist:
            print(f"Fetched {len(hist)} days. Latest: {hist[0]}")
        print("Testing investor trend for 005930...")
        inv = fetch_investor_trend("005930")
        if inv:
            print(f"Investor trend: {inv}")
