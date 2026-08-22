import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import datetime



startdt="2025-01-01"
enddt = datetime.date.today().strftime("%Y-%m-%d")
# Download Reliance stock data
reliance = yf.download("RELIANCE.NS", start=startdt, end=enddt)

print(reliance.head())


# Daily returns
reliance['Daily Return'] = reliance['Close'].pct_change()

# Cumulative returns
reliance['Cumulative Return'] = (1 + reliance['Daily Return']).cumprod()

# Plot
plt.figure(figsize=(10,6))
plt.plot(reliance['Cumulative Return'], label="Reliance Cumulative Return")
plt.legend()
plt.show()