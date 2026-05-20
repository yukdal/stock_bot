import datetime
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL

def build_prompt(filtered_stocks):
    """
    Construct the analysis prompt for Gemini.
    """
    stocks_data_str = ""
    for idx, s in enumerate(filtered_stocks, 1):
        # Format supply demand
        sd = s["supply_demand"]
        sd_str = (
            f"외국인: {sd['foreigner_qty']:+,}주 ({sd['foreigner_val']:+,}원), "
            f"기관: {sd['organ_qty']:+,}주 ({sd['organ_val']:+,}원), "
            f"개인: {sd['individual_qty']:+,}주 ({sd['individual_val']:+,}원)"
        )
        
        # Format news
        news_str = ""
        for n_idx, n in enumerate(s["news"], 1):
            news_str += f"   {n_idx}. [{n['source']}] {n['title']} ({n['link']})\n"
            
        stocks_data_str += f"""
---
[{idx}] {s['name']} ({s['ticker']}) - {s['market']}
- 업종/섹터: {s['sector']}
- 당일 종가: {s['close']:,}원 (등락률: {s['change_pct']:+.2f}%)
- 당일 거래량: {s['volume']:,}주 (당일 거래대금: {s['approx_value']:,}원 / 약 {s['approx_value'] / 100000000:.1f}억 원)
- 기술적 지표:
  * 1000일 이동평균선 대비 위치: {s['price_vs_ma_1000']} (MA1000: {s['ma_1000'] if s['ma_1000'] else 'N/A'})
  * 5일/20일/60일 이평선 배열: {s['alignment']}
  * 20일 평균 거래량 대비 당일 거래량 비율: {s['volume_ratio']:.1f}%
- 재무 지표 (DART):
  * 최근 3개년 당기순이익 (Y0, Y1, Y2): {[f"{val:+,}원" for val in s['net_income_3y']]}
  * 최근 3개년 부채비율 (Y0, Y1, Y2): {[f"{val:.1f}%" for val in s['debt_ratios_3y']]}
  * 최근 3개년 유보율 (Y0, Y1, Y2): {[f"{val:.1f}%" for val in s['reserve_ratios_3y']]}
  * 부채총계: {s['liabilities']:+,}원
  * 자본총계: {s['equity']:+,}원
- 당일 수급: {sd_str}
- 관련 뉴스:
{news_str if news_str else '   (관련 뉴스 없음)'}
"""

    today_str = datetime.date.today().strftime("%Y년 %m월 %d일")
    prompt = f"""
당신은 대한민국 최고의 주식 시장 퀀트 분석가이자 투자 전략가입니다.
오늘 날짜는 **{today_str}** 입니다.
아래의 1차 퀀트 필터링 및 DART 재무 요건을 통과한 오늘(당일)의 주도주 데이터를 바탕으로 최고의 '스윙 주도주 리포트'를 생성해주세요.

[필터링 통과 주종 목록]
{stocks_data_str}

[작성 및 요약 지침]
1. **리포트 제목**: 반드시 오늘 날짜({today_str})를 포함하여 정교하고 신뢰감 있는 제목을 작성해주세요. (예: `[스윙 주도주 리포트] {today_str} 마켓 브리핑 & 핵심 종목 분석`)
2. **시장 요약**: 오늘 필터링된 주도주들을 관통하는 핵심 테마와 시장의 주요 흐름(주도 섹터)을 2-3문장으로 간략히 짚어주세요.
3. **종목별 심층 분석**:
   각 종목에 대해 다음 양식으로 정밀 분석을 수행해주세요.
   - **[종목명 (코드)]** (예: 삼성전자 (005930) - KOSPI)
     * **테마/상승 사유**: 업종 및 최신 뉴스를 분석하여 주가가 오늘 급등한 구체적인 원인(핵심 재료 및 호재)을 설명해주세요. 뉴스 헤드라인과 출처를 결합하여 분석을 풍성하게 해주세요.
     * **거래 규모**: 당일 거래량 및 **당일 거래대금**(원화 및 '억 원' 단위 환산 표기)을 명시해주세요.
     * **수급 분석**: 외국인, 기관, 개인의 순매수 경향을 분석하여 유의미한 수급 주체를 명시해주세요. (예: "외국인/기관 양매수 유입 및 개인 매도세")
     * **기술적/재무적 진단**: 1000일선 위의 위치, 5/20/60 정배열 여부, 거래량 폭발 비율과 3년 연속 당기순이익 흑자 및 **3개년 부채비율 vs 유보율 수치 비교**를 바탕으로 스윙 매매 관점의 종합 평점(A, B, C 등급)과 진단을 내려주세요.
4. **최종 탑픽(Top Pick) 종목**: 분석된 종목 중 스윙 매매 관점에서 가장 유망해 보이는 종목 1-2개를 선정하고 이유를 짤막하게 제시해주세요.
5. **어조**: 전문가답고, 통찰력 있으며, 가독성이 뛰어난 Markdown 형식으로 한글로 작성해주세요.
"""
    return prompt

def generate_mock_report(filtered_stocks):
    """
    Generate a high-quality Markdown report locally as a fallback
    when Gemini API key is missing or invalid.
    """
    today_str = datetime.date.today().strftime("%Y년 %m월 %d일")
    
    report = f"# 📈 [스윙 주도주 리포트] {today_str} 마켓 브리핑 & 핵심 종목 분석\n\n"
    
    if not filtered_stocks:
        report += "오늘 조건(가격 10~30% 상승, 거래대금 100억 이상, DART 3년 흑자 및 부채비율 조건)을 통과한 종목이 없습니다.\n"
        return report
        
    # Summarize sectors
    sectors = [s["sector"] for s in filtered_stocks]
    unique_sectors = list(set(sectors))
    
    report += "## 📊 시장 요약 (Market Summary)\n"
    report += f"금일 조건에 부합하는 스윙 주도주는 총 **{len(filtered_stocks)}개** 종목이 필터링되었습니다.\n"
    report += f"오늘의 주요 강세 섹터는 **{', '.join(unique_sectors)}**입니다.\n"
    report += "필터링된 종목들은 3년 연속 당기순이익 흑자 및 자본총계 대비 부채 비율이 안정적인 건전한 재무 상태를 가진 기업들이며, 거래량 폭발을 통해 스윙 매매 진입 후보군으로 분류됩니다.\n\n"
    
    report += "## 🔍 종목별 심층 분석 (Stock Analysis)\n\n"
    
    for idx, s in enumerate(filtered_stocks, 1):
        sd = s["supply_demand"]
        
        # Determine dominant buyer
        buyers = []
        if sd["foreigner_qty"] > 0: buyers.append("외국인")
        if sd["organ_qty"] > 0: buyers.append("기관")
        buyer_str = " & ".join(buyers) if buyers else "개인"
        
        # DART Financial summary
        ni_y0 = s["net_income_3y"][0]
        debt_ratio = (s["liabilities"] / s["equity"] * 100) if s["equity"] > 0 else 0
        
        # Grade logic
        grade = "B"
        reasons = []
        if s["price_vs_ma_1000"] == "위 (ABOVE)":
            grade = "A"
            reasons.append("장기 이평선(1000일선) 지지/상회")
        if s["alignment"] == "정배열 (Aligned)":
            reasons.append("단기 정배열 추세")
        if sd["foreigner_qty"] > 0 and sd["organ_qty"] > 0:
            grade = "A+"
            reasons.append("외인/기관 양매수 유입")
            
        reason_str = ", ".join(reasons) if reasons else "단기 급등에 따른 추세 정비 필요"
        
        report += f"### {idx}. {s['name']} ({s['ticker']}) - {s['market']}\n"
        report += f"- **섹터/업종**: `{s['sector']}`\n"
        report += f"- **당일 시세**: 종가 `{s['close']:,}원` (`{s['change_pct']:+.2f}%` 상승)\n"
        report += f"- **거래 규모**: 거래량 `{s['volume']:,}주` (대금 약 `{s['approx_value'] / 100000000:.1f}억 원`)\n"
        report += f"- **수급 동향**: 외국인 `{sd['foreigner_qty']:+,}주` | 기관 `{sd['organ_qty']:+,}주` | 개인 `{sd['individual_qty']:+,}주` (주요 매수 주체: **{buyer_str}**)\n"
        report += f"- **기술적 분석**: 1000일선 `{s['price_vs_ma_1000']}`, 이평선 `{s['alignment']}`, 거래량 폭발 비율 `{s['volume_ratio']:.1f}%`\n"
        debt_str = ", ".join([f"{val:.1f}%" for val in s["debt_ratios_3y"]])
        reserve_str = ", ".join([f"{val:.1f}%" for val in s["reserve_ratios_3y"]])
        report += f"- **재무적 분석 (DART)**: 3개년 연속 당기순이익 흑자 유지, 3개년 부채비율(Y0~Y2: `{debt_str}`) vs 유보율(Y0~Y2: `{reserve_str}`) 조건 통과\n"
        report += f"- **스윙 투자 종합 등급**: **{grade}** ({reason_str})\n"
        
        # Add news if any
        if s["news"]:
            report += "- **최신 뉴스/재료**:\n"
            for n in s["news"][:2]:
                report += f"  - [{n['source']}] [{n['title']}]({n['link']}) ({n['date']})\n"
        report += "\n"
        
    # Top Picks
    if filtered_stocks:
        top_picks = [f"{s['name']} ({s['ticker']})" for s in filtered_stocks if s["price_vs_ma_1000"] == "위 (ABOVE)"]
        if not top_picks:
            top_picks = [f"{filtered_stocks[0]['name']} ({filtered_stocks[0]['ticker']})"]
            
        report += "## 🎯 오늘의 스윙 탑픽 (Top Pick)\n"
        for tp in top_picks[:2]:
            report += f"- **{tp}**: 1000일 장기 이평선 위에 위치하여 장기 추세가 살아있으며, 안정적인 재무 지표 및 수급 주체(외인/기관) 유입이 긍정적입니다.\n"
            
    report += "\n*본 리포트는 Naver Finance, Google News 및 DART Open API 데이터를 기반으로 시스템에서 자동 취합/생성한 투자 참고용 보고서입니다.*"
    return report

def generate_report(filtered_stocks, analysis_log=None):
    """
    Generate the complete analyst report using Gemini Pro, falling back to mock report on failure.
    """
    if not filtered_stocks:
        report_text = generate_mock_report(filtered_stocks)
    elif not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        print("⚠️ Gemini API key is placeholder. Generating local structured report...")
        report_text = generate_mock_report(filtered_stocks)
    else:
        try:
            print(f"🤖 Connecting to Gemini API using model '{GEMINI_MODEL}'...")
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            prompt = build_prompt(filtered_stocks)
            
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )
            print("✅ Gemini report generated successfully!")
            report_text = response.text
        except Exception as e:
            print(f"❌ Gemini generation error: {e}. Falling back to structured local report.")
            report_text = generate_mock_report(filtered_stocks)

    if analysis_log:
        report_text += "\n\n---\n\n### 📝 전체 분석 대상 종목 현황\n\n"
        report_text += "| 종목명 | 티커 | 상태 | 탈락 사유 |\n"
        report_text += "| :--- | :--- | :--- | :--- |\n"
        for log in analysis_log:
            status = "✅ 통과" if log.get("Status") == "Passed" else "❌ 탈락"
            reason = log.get("탈락사유", "") if log.get("탈락사유") else "-"
            report_text += f"| {log.get('종목명', '')} | {log.get('티커', '')} | {status} | {reason} |\n"
            
    return report_text
