import yfinance as yf
df = yf.download('^KS11', period='5d')
print("yf.download date:", df.index[-1] if not df.empty else "Empty")
print("yf.download close:", df['Close'].iloc[-1] if not df.empty else "Empty")

idx = yf.Ticker('^KS11')
df2 = idx.history(period='5d')
print("yf.Ticker date:", df2.index[-1] if not df2.empty else "Empty")
print("yf.Ticker close:", df2['Close'].iloc[-1] if not df2.empty else "Empty")
