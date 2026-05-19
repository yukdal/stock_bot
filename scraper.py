import os
import requests
import zipfile
import io
import json
import re
import time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import urllib.parse
from config import DART_CORP_MAP_PATH

# HTTP headers to bypass simple bot checks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

def get_corp_code_map(api_key):
    """
    Load DART stock-to-corp-code mapping from cache.
    If not cached, download and parse CORPCODE.xml, then save cache.
    """
    if DART_CORP_MAP_PATH.exists():
        try:
            with open(DART_CORP_MAP_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load DART cache: {e}. Re-downloading...")
            
    print("⏳ Downloading corporate codes from DART API...")
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        if response.status_code != 200:
            raise Exception(f"DART server returned HTTP {response.status_code}")
            
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            xml_data = zf.read("CORPCODE.xml")
            
        root = ET.fromstring(xml_data)
        corp_map = {}
        for corp in root.findall("list"):
            stock_code = corp.find("stock_code").text
            if stock_code and stock_code.strip():
                stock_code = stock_code.strip()
                corp_code = corp.find("corp_code").text.strip()
                corp_name = corp.find("corp_name").text.strip()
                corp_map[stock_code] = {
                    "corp_code": corp_code,
                    "corp_name": corp_name
                }
                
        # Cache mapping
        with open(DART_CORP_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(corp_map, f, ensure_ascii=False, indent=4)
            
        print(f"✅ Successfully cached DART corp codes for {len(corp_map)} stocks.")
        return corp_map
    except Exception as e:
        print(f"❌ Error downloading DART corp codes: {e}")
        return {}

def fetch_dart_financials(api_key, corp_code, year=2025):
    """
    Fetch DART single company key account information for a specific year.
    Returns parsed dictionary of financials or None if failed.
    """
    url = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": "11011"  # Business report (사업보고서)
    }
    
    try:
        # Sleep to comply with DART API limit (15 requests/sec max)
        time.sleep(0.2)
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"⚠️ DART API returned HTTP {response.status_code} for corp {corp_code}")
            return None
            
        data = response.json()
        if data.get("status") != "000":
            # If 2025 is not available, try to fall back to 2024
            if str(year) == "2025":
                print(f"ℹ️ 2025 data not found for corp {corp_code}. Retrying for 2024...")
                return fetch_dart_financials(api_key, corp_code, year=2024)
            print(f"⚠️ DART API error code {data.get('status')}: {data.get('message')}")
            return None
            
        list_data = data.get("list", [])
        
        financials = {
            "bsns_year": year,
            "net_income_y0": None,  # year (e.g. 2025)
            "net_income_y1": None,  # year-1 (e.g. 2024)
            "net_income_y2": None,  # year-2 (e.g. 2023)
            "liabilities": None,
            "equity": None,
            "capital_stock": None
        }
        
        # Account name synonyms
        net_income_synonyms = ["당기순이익", "당기순이익(손실)", "당기순손익", "연결당기순이익", "연결당기순이익(손실)"]
        liabilities_synonyms = ["부채총계", "부채 총계"]
        equity_synonyms = ["자본총계", "자본 총계"]
        capital_stock_synonyms = ["자본금"]
        
        def parse_amount(val_str):
            if not val_str or val_str.strip() == "-" or val_str.strip() == "":
                return None
            # Remove commas and convert
            clean_str = val_str.replace(",", "").strip()
            try:
                return float(clean_str)
            except ValueError:
                return None

        for item in list_data:
            acc_nm = item.get("account_nm", "").replace(" ", "").strip()
            
            # 1. 당기순이익 (Includes last 3 years in the columns thstrm_amount, frmtrm_amount, bfefrmtrm_amount)
            if any(syn.replace(" ", "") in acc_nm for syn in net_income_synonyms):
                financials["net_income_y0"] = parse_amount(item.get("thstrm_amount"))
                financials["net_income_y1"] = parse_amount(item.get("frmtrm_amount"))
                financials["net_income_y2"] = parse_amount(item.get("bfefrmtrm_amount"))
                
            # 2. 부채총계
            elif any(syn.replace(" ", "") == acc_nm for syn in liabilities_synonyms):
                financials["liabilities"] = parse_amount(item.get("thstrm_amount"))
                
            # 3. 자본총계
            elif any(syn.replace(" ", "") == acc_nm for syn in equity_synonyms):
                financials["equity"] = parse_amount(item.get("thstrm_amount"))
                
            # 4. 자본금
            elif any(syn.replace(" ", "") == acc_nm for syn in capital_stock_synonyms):
                financials["capital_stock"] = parse_amount(item.get("thstrm_amount"))
                
        return financials
    except Exception as e:
        print(f"❌ Exception occurred during DART API call: {e}")
        return None

def fetch_naver_rise_list(market_type="kospi"):
    """
    Scrape the daily rise list page from Naver Finance.
    market_type: 'kospi' or 'kosdaq'
    Returns list of dicts.
    """
    m_type = "kospi" if market_type.lower() == "kospi" else "kosdaq"
    url = f"https://finance.naver.com/sise/sise_rise.naver?marketType={m_type}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        # sise_rise is encoded in EUC-KR
        response.encoding = "euc-kr"
        
        if response.status_code != 200:
            print(f"⚠️ Naver sise_rise HTTP {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, "lxml")
        table = soup.find("table", {"class": "type_2"})
        if not table:
            return []
            
        stocks = []
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) > 5:
                link = cols[1].find("a")
                if link:
                    name = link.text.strip()
                    code = link["href"].split("=")[-1].strip()
                    
                    # Prices and Change Pct
                    try:
                        price_str = cols[2].text.replace(",", "").strip()
                        close_price = int(price_str)
                        
                        pct_str = cols[4].text.replace("%", "").replace("+", "").replace("-", "").strip()
                        # If minus sign was present, restore it
                        if "-" in cols[4].text:
                            change_pct = -float(pct_str)
                        else:
                            change_pct = float(pct_str)
                            
                        vol_str = cols[5].text.replace(",", "").strip()
                        volume = int(vol_str)
                        
                        # Approximate trading value (거래대금 = Close * Volume)
                        approx_value = close_price * volume
                        
                        stocks.append({
                            "ticker": code,
                            "name": name,
                            "close": close_price,
                            "change_pct": change_pct,
                            "volume": volume,
                            "approx_value": approx_value,
                            "market": "KOSPI" if m_type == "kospi" else "KOSDAQ"
                        })
                    except ValueError:
                        continue
        return stocks
    except Exception as e:
        print(f"❌ Exception in Naver rise scraping ({market_type}): {e}")
        return []

def fetch_naver_sector_and_news(ticker):
    """
    Scrape sector name and latest news from Naver Finance.
    """
    headers = HEADERS.copy()
    headers["Referer"] = f"https://finance.naver.com/item/main.naver?code={ticker}"
    
    sector = "기타 / 업종 미분류"
    news_items = []
    
    # 1. Fetch Sector (업종) from stock main page
    try:
        url_main = f"https://finance.naver.com/item/main.naver?code={ticker}"
        r_main = requests.get(url_main, headers=HEADERS, timeout=10)
        r_main.encoding = "utf-8"  # main page is UTF-8
        
        soup_main = BeautifulSoup(r_main.text, "lxml")
        sector_a = soup_main.find("a", href=re.compile(r"sise_group_detail\.naver"))
        if sector_a:
            sector = sector_a.text.strip()
    except Exception as e:
        print(f"⚠️ Failed to scrape sector for {ticker}: {e}")
        
    # 2. Fetch News list
    try:
        url_news = f"https://finance.naver.com/item/news_news.naver?code={ticker}"
        r_news = requests.get(url_news, headers=headers, timeout=10)
        r_news.encoding = "euc-kr"  # news list is EUC-KR
        
        soup_news = BeautifulSoup(r_news.text, "lxml")
        tb = soup_news.find("table", {"class": "type5"})
        if tb:
            for tr in tb.find_all("tr"):
                cells = [td.text.strip() for td in tr.find_all("td")]
                links = [a['href'] for a in tr.find_all("a")]
                
                # Check for individual news article row (normally contains 3 tds: Title, Source, Date)
                if len(cells) == 3 and links and not cells[0].startswith("연관기사"):
                    title = cells[0]
                    source = cells[1]
                    date = cells[2]
                    raw_link = links[0]
                    
                    # Parse query parameters to build a direct link and bypass JavaScript redirection
                    parsed_url = urllib.parse.urlparse(raw_link)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    article_id_list = query_params.get("article_id")
                    office_id_list = query_params.get("office_id")
                    
                    if article_id_list and office_id_list:
                        link = f"https://n.news.naver.com/mnews/article/{office_id_list[0]}/{article_id_list[0]}"
                    else:
                        link = "https://finance.naver.com" + raw_link
                        
                    news_items.append({
                        "title": title,
                        "source": source,
                        "date": date,
                        "link": link,
                        "origin": "Naver"
                    })
                    if len(news_items) >= 3:  # Only top 3 articles
                        break
    except Exception as e:
        print(f"⚠️ Failed to scrape news for {ticker}: {e}")
        
    return sector, news_items

def fetch_google_news(stock_name):
    """
    Fetch news from Google News RSS for the stock name.
    """
    news_items = []
    try:
        query = urllib.parse.quote(stock_name)
        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            items = root.findall(".//item")
            for item in items[:3]:  # Top 3 articles
                title = item.find("title").text
                link = item.find("link").text
                source = item.find("source").text if item.find("source") is not None else "Google Finance"
                pub_date = item.find("pubDate").text
                news_items.append({
                    "title": title,
                    "source": source,
                    "date": pub_date,
                    "link": link,
                    "origin": "Google Finance"
                })
    except Exception as e:
        print(f"⚠️ Failed to fetch Google News for {stock_name}: {e}")
    return news_items

def fetch_investing_news(stock_name):
    """
    Try to fetch news from Investing.com.
    Since Cloudflare 403 block is expected, this catches exceptions and returns an empty list.
    """
    news_items = []
    try:
        query = urllib.parse.quote(stock_name)
        url = f"https://kr.investing.com/search/?q={query}&tab=news"
        # We try to make a request but expect 403
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            # Sample parsing logic if ever successful
            articles = soup.find_all("a", class_=lambda x: x and "article" in x)
            for a in articles[:3]:
                title = a.text.strip()
                link = "https://kr.investing.com" + a.get("href", "")
                news_items.append({
                    "title": title,
                    "source": "Investing.com",
                    "date": "당일",
                    "link": link,
                    "origin": "Investing.com"
                })
        else:
            # Silent logging for Cloudflare Block
            pass
    except Exception:
        # Prevent crash at all costs
        pass
    return news_items

def aggregate_news(stock_name, ticker):
    """
    Fetch news from all three sources, deduplicate, and compile a raw text list for Gemini.
    """
    naver_sector, naver_news = fetch_naver_sector_and_news(ticker)
    google_news = fetch_google_news(stock_name)
    investing_news = fetch_investing_news(stock_name)
    
    # Merge news
    all_news = naver_news + google_news + investing_news
    
    # Simple deduplication by title similarity
    unique_news = []
    seen_titles = set()
    for item in all_news:
        # Simplify title for comparison
        clean_title = re.sub(r'[^가-힣a-zA-Z0-9]', '', item["title"])
        if clean_title not in seen_titles:
            seen_titles.add(clean_title)
            unique_news.append(item)
            
    return naver_sector, unique_news
