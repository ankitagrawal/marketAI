#!/usr/bin/env python
import json
import certifi
from urllib.request import urlopen

# -----------------------------
# Utility Functions
# -----------------------------
def get_jsonparsed_data(url):
    """Fetch JSON data from a URL with certifi SSL"""
    response = urlopen(url, cafile=certifi.where())
    data = response.read().decode("utf-8")
    return json.loads(data)

def calculate_cagr(start, end, years=3):
    """Calculate CAGR for EPS growth"""
    if start <= 0 or end <= 0:
        return None
    return ((end / start) ** (1 / years) - 1) * 100

# -----------------------------
# Parameters
# -----------------------------
API_KEY = "b060faee646aabe928ef2310b97d48c9"  # Replace with your FMP API key
symbol = "AAPL"           # Replace with your stock symbol
current_pe = 25           # Replace with current PE of the stock

# -----------------------------
# Fetch Data
# -----------------------------
url = f"https://financialmodelingprep.com/api/v3/income-statement/{symbol}?limit=5&apikey={API_KEY}"
data = get_jsonparsed_data(url)

# -----------------------------
# Extract EPS History
# -----------------------------
# Get EPS from last 4 years
eps_history = []
for year_data in data[:4]:
    eps = year_data.get("eps")
    if eps is not None:
        eps_history.append(float(eps))

if len(eps_history) < 4:
    print("Not enough EPS data to calculate 3-year CAGR")
    exit()

eps_3y_ago = eps_history[-4]  # 3 years ago
eps_latest = eps_history[0]   # latest

# -----------------------------
# Calculate 3-Year EPS Growth
# -----------------------------
eps_growth_3y = calculate_cagr(eps_3y_ago, eps_latest)
print(f"3-Year EPS CAGR for {symbol}: {eps_growth_3y:.2f}%")

# -----------------------------
# Calculate PEG Ratio
# -----------------------------
peg = current_pe / eps_growth_3y if eps_growth_3y > 0 else None
print(f"Current PE: {current_pe}")
print(f"PEG Ratio: {peg:.2f}" if peg else "PEG cannot be calculated")

# -----------------------------
# PEG Verdict
# -----------------------------
if peg is not None:
    if peg < 1:
        verdict = "Undervalued"
    elif 1 <= peg <= 2:
        verdict = "Fair"
    else:
        verdict = "Expensive"
    print(f"PEG Verdict: {verdict}")
