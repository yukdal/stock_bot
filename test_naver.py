import requests
from bs4 import BeautifulSoup
HEADERS = {"User-Agent": "Mozilla/5.0"}
url = "https://finance.naver.com/sise/sise_index.naver?code=KOSPI"
r = requests.get(url, headers=HEADERS)
r.encoding = "euc-kr"
soup = BeautifulSoup(r.text, "lxml")
now_value_el = soup.find(id="now_value")
change_el = soup.find(id="change_value_and_rate")
print("now_value_el:", now_value_el.text if now_value_el else "None")
print("change_el:", change_el.text if change_el else "None")
