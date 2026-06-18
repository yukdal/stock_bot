import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from index_closing import fetch_index_data
from scraper import fetch_naver_index_data

print("Naver:", fetch_naver_index_data("KOSPI"))
print("Index Closing:", fetch_index_data("KOSPI", "^KS11"))
