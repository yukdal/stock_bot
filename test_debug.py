import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from index_closing import fetch_index_data
from scraper import fetch_naver_index_data

def run_test():
    out = []
    out.append("Naver KOSPI: " + str(fetch_naver_index_data("KOSPI")))
    out.append("Index KOSPI: " + str(fetch_index_data("KOSPI", "^KS11")))
    out.append("Index KOSDAQ: " + str(fetch_index_data("KOSDAQ", "^KQ11")))
    
    with open("test_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out))

if __name__ == "__main__":
    run_test()
