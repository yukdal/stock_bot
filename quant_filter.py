import os
import datetime
import pandas as pd
import yfinance as yf
from scraper import (
    get_corp_code_map,
    fetch_dart_financials,
    fetch_naver_rise_list,
    aggregate_news
)
import requests
from config import DART_API_KEY

def run_quant_filtering():
    """
    Execute Phase 1 filtering:
    1. Scrape Naver Rise list (KOSPI & KOSDAQ).
    2. Filter by Price (10% - 30%) and Trading Value (>= 10B KRW).
    3. Check Moving Averages (1000-day location, 5/20/60 alignment) and Volume Explosion using yfinance.
    4. Check DART financials (3-year net income black, liabilities < equity).
    Returns a list of dictionaries with complete details of filtered stocks.
    """
    print("🚀 Starting Phase 1: Quantitative Filtering...")
    
    # 1. Fetch Rise Lists
    kospi_rise = fetch_naver_rise_list("kospi")
    kosdaq_rise = fetch_naver_rise_list("kosdaq")
    all_rise = kospi_rise + kosdaq_rise
    
    # Deduplicate by ticker to prevent duplicate processing
    seen_tickers = set()
    unique_rise = []
    for s in all_rise:
        if s["ticker"] not in seen_tickers:
            seen_tickers.add(s["ticker"])
            unique_rise.append(s)
    all_rise = unique_rise
    
    print(f"📋 Total rise stocks scraped: {len(all_rise)} (KOSPI: {len(kospi_rise)}, KOSDAQ: {len(kosdaq_rise)})")
    
    # 2. Filter by price return (10% to 30%) and trading value (>= 10 billion KRW)
    # Note: 10 billion KRW is 10,000,000,000 KRW
    price_val_filtered = []
    for s in all_rise:
        if 10.0 <= s["change_pct"] <= 30.5:
            if s["approx_value"] >= 10_000_000_000:
                price_val_filtered.append(s)
                
    print(f"🔍 Stocks passing price (10%-30%) and value (>= 10B KRW) filter: {len(price_val_filtered)}")
    
    # Load DART mapping
    corp_map = get_corp_code_map(DART_API_KEY)
    
    filtered_results = []
    
    # 3. Fetch History and Calculate Technical Indicators
    for s in price_val_filtered:
        ticker = s["ticker"]
        name = s["name"]
        market = s["market"]
        
        # Format ticker for yfinance
        yf_symbol = f"{ticker}.KS" if market == "KOSPI" else f"{ticker}.KQ"
        print(f"📈 Fetching price history for {name} ({yf_symbol})...")
        
        try:
            # Fetch 5 years of daily history to ensure we have 1000 trading days
            ticker_obj = yf.Ticker(yf_symbol)
            hist = ticker_obj.history(period="5y")
            
            if hist.empty or len(hist) < 60:
                print(f"⚠️ Not enough history for {name} ({len(hist)} days). Skipping.")
                continue
                
            # Current prices and volumes
            current_price = hist["Close"].iloc[-1]
            volume_today = hist["Volume"].iloc[-1]
            
            # Technical Indicators
            # A. 1000-day Moving Average (MA 1000)
            ma_1000 = None
            price_vs_ma_1000 = "N/A"
            if len(hist) >= 1000:
                ma_1000 = hist["Close"].tail(1000).mean()
                price_vs_ma_1000 = "위 (ABOVE)" if current_price >= ma_1000 else "아래 (BELOW)"
                
            # B. 5, 20, 60-day Moving Averages alignment (정배열)
            ma_5 = hist["Close"].rolling(5).mean().iloc[-1]
            ma_20 = hist["Close"].rolling(20).mean().iloc[-1]
            ma_60 = hist["Close"].rolling(60).mean().iloc[-1]
            is_aligned = (ma_5 > ma_20 > ma_60)
            alignment_status = "정배열 (Aligned)" if is_aligned else "역배열/혼조 (Non-aligned)"
            
            # C. Volume Explosion (vs 20-day average volume)
            volume_avg_20 = hist["Volume"].iloc[-21:-1].mean()
            volume_ratio = (volume_today / volume_avg_20 * 100) if volume_avg_20 > 0 else 0
            
            print(f"   -> Price vs MA1000: {price_vs_ma_1000} | MAs: {alignment_status} | Volume Ratio: {volume_ratio:.1f}%")
            
            # 4. Check DART Financials
            if ticker not in corp_map:
                print(f"⚠️ {name} ({ticker}) not found in DART corporate map. Skipping due to missing financials.")
                continue
                
            corp_code = corp_map[ticker]["corp_code"]
            print(f"🏢 Querying DART financials for {name} ({corp_code})...")
            
            # Fetch 2025 financials (with 2024 fallback)
            financials = fetch_dart_financials(DART_API_KEY, corp_code, year=2025)
            
            if not financials:
                print(f"⚠️ Could not retrieve financials for {name}. Skipping.")
                continue
                
            # Verify 3-year net income (black/positive)
            ni_0 = financials.get("net_income_y0")
            ni_1 = financials.get("net_income_y1")
            ni_2 = financials.get("net_income_y2")
            
            if ni_0 is None or ni_1 is None or ni_2 is None:
                print(f"⚠️ Missing 3-year net income data for {name} (Y0:{ni_0}, Y1:{ni_1}, Y2:{ni_2}). Skipping.")
                continue
                
            is_net_income_black = (ni_0 > 0 and ni_1 > 0 and ni_2 > 0)
            if not is_net_income_black:
                print(f"❌ {name} excluded: Net income is not positive for 3 consecutive years (Y0:{ni_0:+,}, Y1:{ni_1:+,}, Y2:{ni_2:+,})")
                continue
                
            # Verify debt condition (liabilities < equity)
            liab = financials.get("liabilities")
            eq = financials.get("equity")
            
            if liab is None or eq is None:
                print(f"⚠️ Missing liabilities/equity data for {name} (Liab:{liab}, Eq:{eq}). Skipping.")
                continue
                
            if liab >= eq:
                print(f"❌ {name} excluded: Liabilities ({liab:+,}) >= Equity ({eq:+,})")
                continue
                
            print(f"✅ {name} passed DART checks!")
            
            # 5. Fetch Supply/Demand & News
            # Fetch mobile integration data for investor trend
            investor_url = f"https://m.stock.naver.com/api/stock/{ticker}/integration"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            
            r_inv = requests.get(investor_url, headers=headers, timeout=10)
            foreigner_qty = 0
            organ_qty = 0
            individual_qty = 0
            
            if r_inv.status_code == 200:
                inv_data = r_inv.json()
                dt_list = inv_data.get("dealTrendInfos", [])
                if dt_list:
                    latest = dt_list[0]
                    foreigner_qty = int(latest["foreignerPureBuyQuant"].replace(",", ""))
                    organ_qty = int(latest["organPureBuyQuant"].replace(",", ""))
                    individual_qty = int(latest["individualPureBuyQuant"].replace(",", ""))
                    
            foreigner_val = foreigner_qty * current_price
            organ_val = organ_qty * current_price
            individual_val = individual_qty * current_price
            
            # Aggregate news and sector
            sector, news_list = aggregate_news(name, ticker)
            
            filtered_results.append({
                "ticker": ticker,
                "name": name,
                "market": market,
                "close": current_price,
                "change_pct": s["change_pct"],
                "volume": volume_today,
                "approx_value": s["approx_value"],
                "ma_1000": ma_1000,
                "price_vs_ma_1000": price_vs_ma_1000,
                "alignment": alignment_status,
                "volume_ratio": volume_ratio,
                "net_income_3y": [ni_0, ni_1, ni_2],
                "liabilities": liab,
                "equity": eq,
                "supply_demand": {
                    "foreigner_qty": foreigner_qty,
                    "foreigner_val": foreigner_val,
                    "organ_qty": organ_qty,
                    "organ_val": organ_val,
                    "individual_qty": individual_qty,
                    "individual_val": individual_val,
                    "program_qty": "N/A",  # KRX source restriction
                    "program_val": "N/A"
                },
                "sector": sector,
                "news": news_list
            })
            
        except Exception as e:
            print(f"❌ Error processing {name} ({ticker}): {e}")
            continue
            
    print(f"🎉 Filtering complete! {len(filtered_results)} stocks passed all quant and DART criteria.")
    return filtered_results
