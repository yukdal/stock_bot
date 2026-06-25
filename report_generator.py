import os
import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL

def build_prompt(filtered_stocks, is_nxt=False):
    """
    Construct the analysis prompt for Gemini to strictly output the requested layout.
    """
    stocks_data_str = ""
    for idx, s in enumerate(filtered_stocks, 1):
        sd = s["supply_demand"]
        # Convert values to 억 (100,000,000)
        f_val_eok = sd['foreigner_val'] / 100000000
        o_val_eok = sd['organ_val'] / 100000000
        i_val_eok = sd['individual_val'] / 100000000
        
        # Format news
        news_str = ""
        for n_idx, n in enumerate(s["news"], 1):
            news_str += f"   - [{n['source']}] {n['title']}\n"
            
        ma1000_val = f"{s['ma_1000']:,.0f}원" if s['ma_1000'] else "N/A"
        ma_status = "위" if "ABOVE" in s['price_vs_ma_1000'] else "아래"
        alignment_str = "5-20-60일 정배열 완료" if "Aligned" in s['alignment'] and "Non" not in s['alignment'] else "정배열 아님"
        
        # Finance 3y formatting
        ni_y0 = f"{s['net_income_3y'][0]/100000000:.0f}억" if s['net_income_3y'][0] is not None else "N/A"
        ni_y1 = f"{s['net_income_3y'][1]/100000000:.0f}억" if s['net_income_3y'][1] is not None else "N/A"
        ni_y2 = f"{s['net_income_3y'][2]/100000000:.0f}억" if s['net_income_3y'][2] is not None else "N/A"
        
        stocks_data_str += f"""
[종목 데이터 #{idx}]
종목명: {s['name']} {s.get('signal_tag', '')}
티커: {s['ticker']}
시장구분: {s['market']}
현재가: {s['close']:,}원
당일 등락률: {s['change_pct']:+.2f}%
당일 거래대금: {s['approx_value']/100000000:,.0f}억 원

1000일선 위치: {ma_status}
1000일선 값: {ma1000_val}
단기 이평선 상태: {alignment_str}
거래량 폭발 비율: {s['volume_ratio']:.1f}%

외국인 수급: {f_val_eok:+.0f}억
기관 수급: {o_val_eok:+.0f}억
개인 수급: {i_val_eok:+.0f}억

2023년 순이익: {ni_y0}
2024년 순이익: {ni_y1}
2025년 순이익: {ni_y2}
부채비율: {s['debt_ratios_3y'][0]:.1f}%
유보율: {s['reserve_ratios_3y'][0]:.1f}%

뉴스 헤드라인 원본 데이터:
{news_str if news_str else '없음'}
"""

    report_title = "🚀 [NXT 통합] 오후 9시 넥스트레이드 반영 스윙 주도주 브리핑" if is_nxt else "🚀 오후 8시 Gemini Pro 연동 스윙 주도주 브리핑"

    prompt = f"""
당신은 대한민국 최고의 주식 시장 퀀트 분석가입니다. 아래 필터링된 주도주 데이터를 바탕으로 다음 [출력 양식 가이드]를 100% 동일하게 준수하여 리포트를 작성하십시오. 
제공된 데이터를 철저히 분석하여 스윙 매매 관점에서 매력적인 종목을 '오늘의 TOP 스윙 추천주'로 선정하십시오. 최대 3개까지 선정할 수 있으며, 조건에 부합하는 뛰어난 종목이 3개라면 3개, 2개라면 2개, 1개라면 1개를 선정하십시오. 만약 추천할 만큼 매력적인 종목이 없다면 추천 종목 없이 '현재 시장 상황에서 확실한 주도주로 추천할 만한 종목이 없습니다.'라고 작성하십시오.
선정된 종목이 있다면, 예상 매수가, 목표 매도가, 손절가, 추천 사유를 당신의 전문 지식을 활용해 작성하십시오. 나머지 종목들은 맨 아래 '필터링 통과 종목 전체 요약' 표에만 포함시키십시오.

[출력 양식 가이드 시작]
{report_title}

🏆 오늘의 TOP 스윙 추천주
(추천 종목마다 아래 블록을 반복 생성)
■ 종목명: {{종목명}} ({{티커}}) {{시장구분}} {{signal_tag}}
- 주도 테마: {{네이버 증권 등에서 추출한 핵심 주도 테마명 1~2개}}
- 당일 등락률: {{당일 등락률}} | 거래대금: {{당일 거래대금}}
- 💰 예상 매수가: {{구체적인 가격대}} ({{매수 전략 및 이유}})
- 🎯 목표 매도가: {{구체적인 가격대}} ({{매도 전략 및 이유}})
- 🛑 손절가: {{구체적인 가격대}} ({{손절 기준}})
- 💡 추천 사유: {{펀더멘털, 수급, 기술적 분석을 종합한 구체적인 추천 사유}}
📈 기술적 추세 (Trend Check)
- 1000일선 위치: [{{1000일선 위치}}] (현재가: {{현재가}} / 1000일선: {{1000일선 값}})
- 단기 이평선: {{단기 이평선 상태}}
- 거래량 폭발 비율: 최근 20일 평균 대비 {{거래량 폭발 비율}} 폭발
💵 당일 최종 수급 (Supply & Demand)
- 외국인: {{외국인 수급}} / 기관: {{기관 수급}} / 개인: {{개인 수급}}
📋 재무 안정성 점검 (DART Verified)
- 당기순이익(3년): 2023({{2023년 순이익}}) / 2024({{2024년 순이익}}) / 2025({{2025년 순이익}}) 적격
- 부채비율: {{부채비율}} < 유보율: {{유보율}} -> 적격
📰 관련 핵심 뉴스 (Gemini 요약)
- "{{뉴스 데이터에서 당일 급등 원인이 된 가장 중요한 핵심 헤드라인 1개 발췌 및 요약}}" (출처: {{해당 뉴스의 실제 출처}})
--------------------------------------

📊 필터링 통과 종목 전체 요약
| 종목명 | 티커 | 등락률 | 거래대금 | MA1000 위치 | 외국인수급 | 기관수급 |
|---|---|---|---|---|---|---|
(여기에 필터링을 통과한 전체 종목들의 요약 데이터를 마크다운 표로 작성)
[출력 양식 가이드 끝]

[주도주 데이터]
{stocks_data_str}
"""
    return prompt

def generate_mock_report(filtered_stocks, is_nxt=False, error_reason="알 수 없는 에러"):
    """
    Generate a high-quality Markdown report locally as a fallback
    when Gemini API key is missing or invalid.
    Matches the required layout exactly.
    """
    report_title = "🚀 [NXT 통합] 오후 9시 넥스트레이드 반영 스윙 주도주 브리핑" if is_nxt else "🚀 [오후 8시 Gemini Pro 연동 스윙 주도주 브리핑]"
    report = f"{report_title}\n\n"
    
    report += f"⚠️ **[안내] 현재 브리핑은 AI 통신 문제로 인해 임시 생성된 비상용(Mock) 데이터입니다.**\n"
    report += f"- 발생 사유: {error_reason}\n"
    report += f"- 조치 안내: 잠시 후 다시 시도하거나 API 키 및 네트워크 상태를 확인해주세요.\n\n"
    
    if not filtered_stocks:
        report += "오늘 조건(가격 10~30.5% 상승, 거래대금 200억 이상 등)을 통과한 종목이 없습니다.\n"
        return report
        
    # Pick Top 3 by trade value
    top_stocks = sorted(filtered_stocks, key=lambda x: x['approx_value'], reverse=True)[:3]
    
    report += "🏆 오늘의 TOP 스윙 추천주 (Mock Data Fallback)\n\n"
    
    for s in top_stocks:
        sd = s["supply_demand"]
        f_val_eok = sd['foreigner_val'] / 100000000
        o_val_eok = sd['organ_val'] / 100000000
        i_val_eok = sd['individual_val'] / 100000000
        
        ma1000_val = f"{s['ma_1000']:,.0f}원" if s['ma_1000'] else "N/A"
        ma_status = "위" if "ABOVE" in s['price_vs_ma_1000'] else "아래"
        alignment_str = "5-20-60일 정배열 완료" if "Aligned" in s['alignment'] and "Non" not in s['alignment'] else "정배열 아님"
        
        ni_y0 = f"{s['net_income_3y'][0]/100000000:.0f}억" if s['net_income_3y'][0] is not None else "N/A"
        ni_y1 = f"{s['net_income_3y'][1]/100000000:.0f}억" if s['net_income_3y'][1] is not None else "N/A"
        ni_y2 = f"{s['net_income_3y'][2]/100000000:.0f}억" if s['net_income_3y'][2] is not None else "N/A"
        
        news_line = "관련 뉴스 수집 불가"
        news_source = "N/A"
        if s["news"]:
            news_line = s["news"][0]["title"]
            news_source = s["news"][0]["source"]
            
        report += f"■ 종목명: {s['name']} ({s['ticker']}) [{s['market']}] {s.get('signal_tag', '')}\n"
        report += f"- 주도 테마: {s['sector']} (Mock Data)\n"
        report += f"- 당일 등락률: {s['change_pct']:+.2f}% | 거래대금: {s['approx_value']/100000000:,.0f}억 원\n"
        report += f"- 💰 예상 매수가: {s['close']:,}원 부근 분할매수 (Mock Data)\n"
        report += f"- 🎯 목표 매도가: {int(s['close']*1.05):,}원 이상 익절 (Mock Data)\n"
        report += f"- 🛑 손절가: {int(s['close']*0.95):,}원 이탈시 손절 (Mock Data)\n"
        report += f"- 💡 추천 사유: 수급 및 거래량 폭발 기반 단기 시세 분출 기대 (Mock Data)\n\n"
        
        report += "📈 기술적 추세 (Trend Check)\n"
        report += f"- 1000일선 위치: [{ma_status}] (현재가: {s['close']:,}원 / 1000일선: {ma1000_val})\n"
        report += f"- 단기 이평선: [{alignment_str}]\n"
        report += f"- 거래량 폭발 비율: 최근 20일 평균 대비 {s['volume_ratio']:.1f}% 폭발\n\n"
        
        report += "💵 당일 최종 수급 (Supply & Demand)\n"
        report += f"- 외국인: {f_val_eok:+.0f}억 / 기관: {o_val_eok:+.0f}억 / 개인: {i_val_eok:+.0f}억\n\n"
        
        report += "📋 재무 안정성 점검 (DART Verified)\n"
        report += f"- 당기순이익(3년): 2023({ni_y0}) / 2024({ni_y1}) / 2025({ni_y2}) [적격]\n"
        report += f"- 부채비율: {s['debt_ratios_3y'][0]:.1f}% < 유보율: {s['reserve_ratios_3y'][0]:.1f}% -> [적격]\n\n"
        
        report += "📰 관련 핵심 뉴스 (Gemini 요약)\n"
        report += f"- \"{news_line}\" (출처: {news_source})\n"
        report += "--------------------------------------\n"
        
    report += "\n📊 필터링 통과 종목 전체 요약\n"
    report += "| 종목명 | 티커 | 등락률 | 거래대금 | MA1000 위치 | 외국인수급 | 기관수급 |\n"
    report += "|---|---|---|---|---|---|---|\n"
    for s in filtered_stocks:
        sd = s["supply_demand"]
        f_val_eok = sd['foreigner_val'] / 100000000
        o_val_eok = sd['organ_val'] / 100000000
        ma_status = "위" if "ABOVE" in s['price_vs_ma_1000'] else "아래"
        report += f"| {s['name']} | {s['ticker']} | {s['change_pct']:+.2f}% | {s['approx_value']/100000000:,.0f}억 | {ma_status} | {f_val_eok:+.0f}억 | {o_val_eok:+.0f}억 |\n"
        
    return report

def generate_report(filtered_stocks, analysis_log=None, is_nxt=False):
    """
    Generate the complete analyst report using Gemini.
    Raises exception on API key absence or generation failure to trigger retry logic.
    """
    base_dir = Path(__file__).resolve().parent
    load_dotenv(base_dir / ".env", override=True)
    current_api_key = os.getenv("GEMINI_API_KEY")
    current_model = os.getenv("GEMINI_MODEL", GEMINI_MODEL)
    
    report_title = "🚀 [NXT 통합] 오후 9시 넥스트레이드 반영 스윙 주도주 브리핑" if is_nxt else "🚀 [오후 8시 Gemini Pro 연동 스윙 주도주 브리핑]"

    if not filtered_stocks:
        report_text = f"{report_title}\n\n오늘 조건(가격 10~30.5% 상승, 거래대금 200억 이상 등)을 통과한 종목이 없습니다.\n"
    elif not current_api_key or current_api_key == "YOUR_GEMINI_API_KEY":
        print("⚠️ Gemini API key is missing or placeholder. Raising exception for retry logic...")
        raise Exception("API 키 미설정 (AI 분석 불가 및 목업 데이터만 사용 가능한 상태)")
    else:
        try:
            print(f"🤖 Connecting to Gemini API using model '{current_model}'...")
            client = genai.Client(api_key=current_api_key)
            
            prompt = build_prompt(filtered_stocks, is_nxt=is_nxt)
            
            response = client.models.generate_content(
                model=current_model,
                contents=prompt
            )
            print("✅ Gemini report generated successfully!")
            report_text = response.text
        except Exception as e:
            print(f"❌ Gemini generation error: {e}. Raising exception for retry logic.")
            raise Exception(f"Gemini API 통신 오류 ({e}) (AI 분석 불가 및 목업 데이터만 사용 가능한 상태)")

    if analysis_log:
        report_text += "\n<!-- SPLIT_HERE -->\n"
        report_text += "### 📝 전체 분석 대상 종목 현황\n\n"
        report_text += "| 종목명 | 티커 | MA1000 위치 | 상태 | 탈락 사유 |\n"
        report_text += "| :--- | :--- | :--- | :--- | :--- |\n"
        for log in analysis_log:
            status = "✅ 통과" if log.get("Status") == "Passed" else "❌ 탈락"
            reason = log.get("탈락사유", "") if log.get("탈락사유") else "-"
            ma_pos = log.get("MA1000_위치", "N/A")
            sig_tag = log.get("Signal_Tag", "")
            if not ma_pos: ma_pos = "N/A"
            if sig_tag:
                report_text += f"| {log.get('종목명', '')} {sig_tag} | {log.get('티커', '')} | {ma_pos} | {status} | {reason} |\n"
            else:
                report_text += f"| {log.get('종목명', '')} | {log.get('티커', '')} | {ma_pos} | {status} | {reason} |\n"
            
    return report_text
