from scraper import fetch_naver_rise_list
import urllib.parse
print("kospi url param ?sosok=0")
l = fetch_naver_rise_list("kospi")
print(len(l), l[:3] if l else "None")

print("kosdaq url param ?sosok=1")
from bs4 import BeautifulSoup
import requests
r = requests.get("https://finance.naver.com/sise/sise_rise.naver?sosok=1")
r.encoding="euc-kr"
soup = BeautifulSoup(r.text, 'lxml')
tb = soup.find("table", {"class": "type_2"})
if tb:
    for tr in tb.find_all("tr")[:10]:
        cols = tr.find_all("td")
        if len(cols) > 5:
            link = cols[1].find("a")
            if link: print("KOSDAQ item:", link.text.strip())

print("marketType=kosdaq")
r = requests.get("https://finance.naver.com/sise/sise_rise.naver?marketType=kosdaq")
r.encoding="euc-kr"
soup = BeautifulSoup(r.text, 'lxml')
tb = soup.find("table", {"class": "type_2"})
if tb:
    for tr in tb.find_all("tr")[:10]:
        cols = tr.find_all("td")
        if len(cols) > 5:
            link = cols[1].find("a")
            if link: print("KOSDAQ item:", link.text.strip())
