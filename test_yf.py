import yfinance as yf
print("KOSPI:")
print(yf.Ticker('^KS11').history(period='5d')[['Close']])
print("S&P 500:")
print(yf.Ticker('^GSPC').history(period='5d')[['Close']])
