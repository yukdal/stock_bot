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
    Returns a tuple: (list of dictionaries with complete details of filtered stocks, list of analysis logs).
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
    analysis_log = []
    
    # 3. Fetch History and Calculate Technical Indicators
    for s in price_val_filtered:
        ticker = s["ticker"]
        name = s["name"]
        market = s["market"]
        
        # Initialize log entry
        log_entry = {
            "종목명": name,
            "티커": ticker,
            "시장": market,
            "현재가": s["close"],
            "등락률(%)": s["change_pct"],
            "거래량": s["volume"],
            "거래대금": s["approx_value"],
            "MA1000": None,
            "MA1000_위치": None,
            "이평선_배열": None,
            "거래량_비율(%)": None,
            "Y0_순이익": None,
            "Y1_순이익": None,
            "Y2_순이익": None,
            "Y0_부채비율(%)": None,
            "Y0_유보율(%)": None,
            "유보율>부채비율_충족": None,
            "외국인_수급": None,
            "기관_수급": None,
            "개인_수급": None,
            "Status": "Processing",
            "탈락사유": ""
        }
        
        # Format ticker for yfinance
        yf_symbol = f"{ticker}.KS" if market == "KOSPI" else f"{ticker}.KQ"
        print(f"📈 Fetching price history for {name} ({yf_symbol})...")
        
        try:
            # Fetch 5 years of daily history to ensure we have 1000 trading days
            ticker_obj = yf.Ticker(yf_symbol)
            hist = ticker_obj.history(period="5y")
            
            if hist.empty or len(hist) < 60:
                print(f"⚠️ Not enough history for {name} ({len(hist)} days). Skipping.")
                log_entry["Status"] = "Failed"
                log_entry["탈락사유"] = f"과거 데이터 부족 ({len(hist)}일)"
                analysis_log.append(log_entry)
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
            
            log_entry["MA1000"] = ma_1000
            log_entry["MA1000_위치"] = price_vs_ma_1000
            log_entry["이평선_배열"] = alignment_status
            log_entry["거래량_비율(%)"] = round(volume_ratio, 1)
            
            print(f"   -> Price vs MA1000: {price_vs_ma_1000} | MAs: {alignment_status} | Volume Ratio: {volume_ratio:.1f}%")
            
            # 4. Check DART Financials
            if ticker not in corp_map:
                print(f"⚠️ {name} ({ticker}) not found in DART corporate map. Skipping due to missing financials.")
                log_entry["Status"] = "Failed"
                log_entry["탈락사유"] = "DART 기업코드 매핑 실패"
                analysis_log.append(log_entry)
                continue
                
            corp_code = corp_map[ticker]["corp_code"]
            print(f"🏢 Querying DART financials for {name} ({corp_code})...")
            
            # Fetch 2025 financials (with 2024 fallback)
            financials = fetch_dart_financials(DART_API_KEY, corp_code, year=2025)
            
            if not financials:
                print(f"⚠️ Could not retrieve financials for {name}. Skipping.")
                log_entry["Status"] = "Failed"
                log_entry["탈락사유"] = "DART 재무제표 수신 실패"
                analysis_log.append(log_entry)
                continue
                
            # Verify 3-year net income (black/positive)
            ni_0 = financials.get("net_income_y0")
            ni_1 = financials.get("net_income_y1")
            ni_2 = financials.get("net_income_y2")
            
            log_entry["Y0_순이익"] = ni_0
            log_entry["Y1_순이익"] = ni_1
            log_entry["Y2_순이익"] = ni_2
            
            if ni_0 is None or ni_1 is None or ni_2 is None:
                print(f"⚠️ Missing 3-year net income data for {name} (Y0:{ni_0}, Y1:{ni_1}, Y2:{ni_2}). Skipping.")
                log_entry["Status"] = "Failed"
                log_entry["탈락사유"] = "3개년 순이익 데이터 누락"
                analysis_log.append(log_entry)
                continue
                
            is_net_income_black = (ni_0 > 0 and ni_1 > 0 and ni_2 > 0)
            if not is_net_income_black:
                print(f"❌ {name} excluded: Net income is not positive for 3 consecutive years (Y0:{ni_0:+,}, Y1:{ni_1:+,}, Y2:{ni_2:+,})")
                log_entry["Status"] = "Failed"
                log_entry["탈락사유"] = "3년 연속 흑자 조건 미달"
                analysis_log.append(log_entry)
                continue
                
            # Verify debt vs retention conditions for 3 years
            liab_0 = financials.get("liabilities_y0")
            liab_1 = financials.get("liabilities_y1")
            liab_2 = financials.get("liabilities_y2")
            
            eq_0 = financials.get("equity_y0")
            eq_1 = financials.get("equity_y1")
            eq_2 = financials.get("equity_y2")
            
            cap_0 = financials.get("capital_stock_y0")
            cap_1 = financials.get("capital_stock_y1")
            cap_2 = financials.get("capital_stock_y2")
            
            if None in [liab_0, liab_1, liab_2, eq_0, eq_1, eq_2, cap_0, cap_1, cap_2]:
                print(f"⚠️ Missing liabilities/equity/capital stock data for {name}. Skipping.")
                log_entry["Status"] = "Failed"
                log_entry["탈락사유"] = "부채/자본/자본금 데이터 누락"
                analysis_log.append(log_entry)
                continue
                
            # Calculate ratios (%)
            debt_ratio_0 = (liab_0 / eq_0 * 100) if eq_0 > 0 else 0
            debt_ratio_1 = (liab_1 / eq_1 * 100) if eq_1 > 0 else 0
            debt_ratio_2 = (liab_2 / eq_2 * 100) if eq_2 > 0 else 0
            
            reserve_ratio_0 = ((eq_0 - cap_0) / cap_0 * 100) if cap_0 > 0 else 0
            reserve_ratio_1 = ((eq_1 - cap_1) / cap_1 * 100) if cap_1 > 0 else 0
            reserve_ratio_2 = ((eq_2 - cap_2) / cap_2 * 100) if cap_2 > 0 else 0
            
            log_entry["Y0_부채비율(%)"] = round(debt_ratio_0, 1)
            log_entry["Y0_유보율(%)"] = round(reserve_ratio_0, 1)
            
            # Check condition: 부채비율 < 유보율 for all 3 years
            cond_0 = debt_ratio_0 < reserve_ratio_0
            cond_1 = debt_ratio_1 < reserve_ratio_1
            cond_2 = debt_ratio_2 < reserve_ratio_2
            
            log_entry["유보율>부채비율_충족"] = bool(cond_0 and cond_1 and cond_2)
            
            if not (cond_0 and cond_1 and cond_2):
                print(f"❌ {name} excluded: Debt ratio >= Retention rate in one of the 3 years.")
                print(f"   -> Y0 (Debt: {debt_ratio_0:.1f}% vs Reserve: {reserve_ratio_0:.1f}%)")
                print(f"   -> Y1 (Debt: {debt_ratio_1:.1f}% vs Reserve: {reserve_ratio_1:.1f}%)")
                print(f"   -> Y2 (Debt: {debt_ratio_2:.1f}% vs Reserve: {reserve_ratio_2:.1f}%)")
                log_entry["Status"] = "Failed"
                log_entry["탈락사유"] = "유보율 > 부채비율 3년 조건 미달"
                analysis_log.append(log_entry)
                continue
                
            print(f"✅ {name} passed DART checks (3y net income and debt < retention)!")
            
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
            
            log_entry["외국인_수급"] = foreigner_qty
            log_entry["기관_수급"] = organ_qty
            log_entry["개인_수급"] = individual_qty
            
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
                "liabilities": liab_0,
                "equity": eq_0,
                "debt_ratios_3y": [debt_ratio_0, debt_ratio_1, debt_ratio_2],
                "reserve_ratios_3y": [reserve_ratio_0, reserve_ratio_1, reserve_ratio_2],
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
            
            log_entry["Status"] = "Passed"
            analysis_log.append(log_entry)
            
        except Exception as e:
            print(f"❌ Error processing {name} ({ticker}): {e}")
            log_entry["Status"] = "Error"
            log_entry["탈락사유"] = f"예외 발생: {str(e)}"
            analysis_log.append(log_entry)
            continue
            
    print(f"🎉 Filtering complete! {len(filtered_results)} stocks passed all quant and DART criteria.")
    return filtered_results, analysis_log
