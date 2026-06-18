import yfinance as yf
df = yf.Ticker('^KS11').history(period='5d')
print("KS11 index:")
print(df.index)
print("GSPC index:")
print(yf.Ticker('^GSPC').history(period='5d').index)
