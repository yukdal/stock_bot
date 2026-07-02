import os
import datetime
import pandas as pd
import pandas as pd
from kis_api import fetch_daily_price, fetch_investor_trend
from scraper import (
    get_corp_code_map,
    fetch_dart_financials,
    fetch_naver_rise_list,
    aggregate_news
)
import requests
from config import DART_API_KEY
from kiwoom_api import fetch_kiwoom_daily_price

def run_quant_filtering(is_nxt=False):
    """
    Main logic to screen and filter top stocks based on price, volume, and supply/demand.
    """
    phase_name = "NXT-Inclusive Phase 1" if is_nxt else "Phase 1"
    print(f"\n⏳ [{phase_name}] Fetching daily top rising stocks...")
    
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
    
    # 2. Filter by price return (10% to 30.5%) and trading value (>= 5 billion KRW) + Negative Filtering
    price_val_filtered = []
    for s in all_rise:
        # 🚫 네거티브 필터링 제약조건 적용 (동전주, 50억 미만, 위험종목 제외)
        if s["close"] < 1000:
            continue # 동전주(1,000원 미만) 제외
        if s["approx_value"] < 5_000_000_000:
            continue # 거래대금 50억 미만 제외
            
        # 종목명에 투자경고/위험/정지/환기/관리 등 리스크 태그가 있는 경우 제외
        risk_keywords = ["경고", "위험", "정지", "환기", "관리"]
        if any(keyword in s["name"] for keyword in risk_keywords):
            continue
            
        if 10.0 <= s["change_pct"] <= 30.5:
            price_val_filtered.append(s)
                
    print(f"🔍 Stocks passing price (10%-30.5%) and negative filters: {len(price_val_filtered)}")
    
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
            "Signal_Tag": "",
            "탈락사유": ""
        }
        
        # 3. Check DART Financials
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
            
        is_net_income_black = not (ni_0 < 0 and ni_1 < 0 and ni_2 < 0)
        if not is_net_income_black:
            print(f"❌ {name} excluded: Net income is negative for 3 consecutive years (Y0:{ni_0:+,}, Y1:{ni_1:+,}, Y2:{ni_2:+,})")
            log_entry["Status"] = "Failed"
            log_entry["탈락사유"] = "3년 연속 적자"
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
        
        # Risk Check: Extreme debt ratio (> 500%) exclusion
        if debt_ratio_0 > 500:
            print(f"❌ {name} excluded: Extreme debt ratio in latest year ({debt_ratio_0:.1f}%)")
            log_entry["Status"] = "Failed"
            log_entry["탈락사유"] = "과도한 부채비율 (상폐 우려)"
            analysis_log.append(log_entry)
            continue
        
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

        print(f"📈 Fetching price history via KIS API for {name} ({ticker})...")
        
        try:
            # Fetch 1200 days of daily history from KIS API
            hist_data = fetch_daily_price(ticker)
            
            # Fallback to Kiwoom REST API if KIS fails or returns not enough data
            if not hist_data or len(hist_data) < 60:
                print(f"⚠️ KIS API data insufficient or failed for {name}. Falling back to Kiwoom REST API...")
                kiwoom_data = fetch_kiwoom_daily_price(ticker)
                if kiwoom_data and len(kiwoom_data) >= 60:
                    hist_data = kiwoom_data
                    print(f"✅ Successfully fetched data from Kiwoom REST API for {name}.")
                else:
                    print(f"⚠️ Not enough history from both KIS and Kiwoom APIs for {name}. Skipping.")
                    log_entry["Status"] = "Failed"
                    log_entry["탈락사유"] = f"과거 데이터 부족 (KIS/Kiwoom 모두 실패)"
                    analysis_log.append(log_entry)
                    continue
                
            # Convert to DataFrame and reverse to chronological order
            df = pd.DataFrame(hist_data)
            df['stck_clpr'] = df['stck_clpr'].astype(float)
            df['acml_vol'] = df['acml_vol'].astype(float)
            
            # Use safe get for high price if available
            if 'stck_hgpr' in df.columns:
                df['stck_hgpr'] = df['stck_hgpr'].astype(float)
            
            df = df.iloc[::-1].reset_index(drop=True)
            
            # Current prices and volumes
            current_price = df["stck_clpr"].iloc[-1]
            volume_today = df["acml_vol"].iloc[-1]
            
            # Upper tail exclusion check (변동성 지표 임계치)
            if 'stck_hgpr' in df.columns:
                high_price = df["stck_hgpr"].iloc[-1]
                # Calculate approximate previous close
                prev_close = current_price / (1 + s["change_pct"]/100)
                high_pct = (high_price - prev_close) / prev_close * 100
                
                # Rule: High > 25% but Close < 10% indicates long upper tail (차익실현 매물 폭탄)
                if high_pct >= 25.0 and s["change_pct"] < 10.0:
                    print(f"❌ {name} excluded: Long upper tail (High: {high_pct:.1f}%, Close: {s['change_pct']:.1f}%)")
                    log_entry["Status"] = "Failed"
                    log_entry["탈락사유"] = "긴 위꼬리 (매물 출회)"
                    analysis_log.append(log_entry)
                    continue
            
            # Technical Indicators
            # A. 1000-day Moving Average (MA 1000)
            ma_1000 = None
            price_vs_ma_1000 = "N/A"
            if len(df) >= 1000:
                ma_1000 = df["stck_clpr"].tail(1000).mean()
                price_vs_ma_1000 = "위 (ABOVE)" if current_price >= ma_1000 else "아래 (BELOW)"
                
            # B. 5, 20, 60-day Moving Averages alignment (정배열)
            ma_5 = df["stck_clpr"].rolling(5).mean().iloc[-1]
            ma_20 = df["stck_clpr"].rolling(20).mean().iloc[-1]
            ma_60 = df["stck_clpr"].rolling(60).mean().iloc[-1]
            is_aligned = (ma_5 > ma_20 > ma_60)
            alignment_status = "정배열 (Aligned)" if is_aligned else "역배열/혼조 (Non-aligned)"
            
            # C. Volume Explosion (vs 20-day average volume)
            volume_avg_20 = df["acml_vol"].iloc[-21:-1].mean()
            volume_ratio = (volume_today / volume_avg_20 * 100) if volume_avg_20 > 0 else 0
            
            # Liquidity Check (품절주 차단)
            if volume_avg_20 < 100000:
                print(f"❌ {name} excluded: Low liquidity (20-day avg volume: {volume_avg_20:.0f})")
                log_entry["Status"] = "Failed"
                log_entry["탈락사유"] = "품절주 (유동성 부족)"
                analysis_log.append(log_entry)
                continue
            
            log_entry["MA1000"] = ma_1000
            log_entry["MA1000_위치"] = price_vs_ma_1000
            log_entry["이평선_배열"] = alignment_status
            log_entry["거래량_비율(%)"] = round(volume_ratio, 1)
            
            print(f"   -> Price vs MA1000: {price_vs_ma_1000} | MAs: {alignment_status} | Volume Ratio: {volume_ratio:.1f}%")

            
            # 5. Fetch Supply/Demand via KIS API
            inv_data = fetch_investor_trend(ticker)
            foreigner_qty = 0
            organ_qty = 0
            individual_qty = 0
            
            if inv_data:
                fq = inv_data.get("frgn_ntby_qty", "").replace(",", "")
                oq = inv_data.get("orgn_ntby_qty", "").replace(",", "")
                iq = inv_data.get("prsn_ntby_qty", "").replace(",", "")
                
                # Check if not empty
                if fq and fq not in ["", "-"]: foreigner_qty = int(fq)
                if oq and oq not in ["", "-"]: organ_qty = int(oq)
                if iq and iq not in ["", "-"]: individual_qty = int(iq)
                    
            foreigner_val = foreigner_qty * current_price
            organ_val = organ_qty * current_price
            individual_val = individual_qty * current_price
            
            log_entry["외국인_수급"] = foreigner_qty
            log_entry["기관_수급"] = organ_qty
            log_entry["개인_수급"] = individual_qty
            
            # Signal Tagging for NotebookLM Logic
            tech_signal = []
            if is_aligned:
                tech_signal.append("정배열")
            if volume_ratio >= 300:
                tech_signal.append("거래량폭발")
            
            supply_signal = []
            if foreigner_val > 0 and organ_val > 0:
                supply_signal.append("외인기관 양매수")
            elif organ_val > 0:
                supply_signal.append("기관 연속매집" if organ_qty > 50000 else "기관 순매수")
            elif foreigner_val > 0:
                supply_signal.append("외인 순매수")
                
            if not tech_signal: tech_signal.append("기술적양호")
            if not supply_signal: supply_signal.append("개인주도")
            
            signal_tag = f"[수급: {'+'.join(supply_signal)}] [기술적: {'+'.join(tech_signal)}]"
            log_entry["Signal_Tag"] = signal_tag
            
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
                "news": news_list,
                "signal_tag": signal_tag
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
