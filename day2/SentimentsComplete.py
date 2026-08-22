# ===============================================
# Market Sentiment Analysis + Stock Price Dashboard
# ===============================================

# Step 0: Install dependencies
# !pip install yfinance openai pandas matplotlib

# -----------------------------------------------
# Step 1: Imports
# -----------------------------------------------
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from openai import OpenAI

# -----------------------------------------------
# Step 2: Define stocks & download price data
# -----------------------------------------------
stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]  # Add more tickers if needed
stock_data = yf.download(stocks, period="90d")  # last 90 days

# Flatten MultiIndex columns
stock_data.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in stock_data.columns]
stock_data = stock_data.reset_index()
stock_data['Date'] = pd.to_datetime(stock_data['Date'])

# Rename Close columns for convenience
for stock in stocks:
    stock_data.rename(columns={f'Close_{stock}': f'Close_{stock.split(".")[0]}'}, inplace=True)

print(stock_data.head())

# -----------------------------------------------
# Step 3: Prepare news DataFrame (df_news)
# df_news must contain: 'pubDate', 'sentiment_score'
# -----------------------------------------------
# Example structure:
# df_news = pd.DataFrame({
#     'pubDate': ['2025-08-01', '2025-08-02', ...],
#     'sentiment_score': [0.1, -0.2, ...],
#     'stock': ['RELIANCE', 'TCS', ...]  # optional if multiple stocks
# })
df_news['pubDate'] = pd.to_datetime(df_news['pubDate'])

# -----------------------------------------------
# Step 4: Compute weekly & monthly sentiment
# -----------------------------------------------
weekly_sentiment = df_news.groupby(pd.Grouper(key='pubDate', freq='W'))['sentiment_score'].mean().reset_index()
weekly_sentiment.rename(columns={'pubDate':'Date', 'sentiment_score':'avg_sentiment_weekly'}, inplace=True)

monthly_sentiment = df_news.groupby(pd.Grouper(key='pubDate', freq='M'))['sentiment_score'].mean().reset_index()
monthly_sentiment.rename(columns={'pubDate':'Date', 'sentiment_score':'avg_sentiment_monthly'}, inplace=True)

# -----------------------------------------------
# Step 5: Merge stock data with weekly & monthly sentiment
# -----------------------------------------------
def merge_stock_sentiment(stock_name):
    merged_weekly = pd.merge(stock_data[['Date', f'Close_{stock_name}']], 
                             weekly_sentiment, on='Date', how='left').fillna(0)
    merged_monthly = pd.merge(stock_data[['Date', f'Close_{stock_name}']], 
                              monthly_sentiment, on='Date', how='left').fillna(0)
    return merged_weekly, merged_monthly

# -----------------------------------------------
# Step 6: Plot function
# -----------------------------------------------
def plot_stock_sentiment(stock_name, merged_weekly, merged_monthly):
    # Weekly plot
    fig, ax1 = plt.subplots(figsize=(12,6))
    ax1.plot(merged_weekly['Date'], merged_weekly[f'Close_{stock_name}'], color='blue', label='Price')
    ax1.set_ylabel("Price (INR)", color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')

    ax2 = ax1.twinx()
    ax2.plot(merged_weekly['Date'], merged_weekly['avg_sentiment_weekly'], color='red', linestyle='--', label='Weekly Sentiment')
    ax2.set_ylabel("Weekly Avg Sentiment", color='red')
    ax2.tick_params(axis='y', labelcolor='red')

    plt.title(f"{stock_name} Price vs Weekly Sentiment")
    fig.tight_layout()
    plt.show()

    # Monthly plot
    fig, ax1 = plt.subplots(figsize=(12,6))
    ax1.plot(merged_monthly['Date'], merged_monthly[f'Close_{stock_name}'], color='blue', label='Price')
    ax1.set_ylabel("Price (INR)", color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')

    ax2 = ax1.twinx()
    ax2.plot(merged_monthly['Date'], merged_monthly['avg_sentiment_monthly'], color='green', linestyle='--', label='Monthly Sentiment')
    ax2.set_ylabel("Monthly Avg Sentiment", color='green')
    ax2.tick_params(axis='y', labelcolor='green')

    plt.title(f"{stock_name} Price vs Monthly Sentiment")
    fig.tight_layout()
    plt.show()

# -----------------------------------------------
# Step 7: AI summary function
# -----------------------------------------------
def generate_ai_summary(sentiment_df, stock_name):
    client = OpenAI(api_key="YOUR_API_KEY")  # Add your OpenAI API key
    prompt = f"""
    Weekly sentiment index for {stock_name} (last 3 months):
    {sentiment_df.to_dict(orient='records')}
    Provide a simple 2–3 line summary of the trend for a business report.
    """
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role":"user","content":prompt}]
    )
    print(f"AI Summary for {stock_name}:")
    print(response.choices[0].message.content)
    print("-"*50)

# -----------------------------------------------
# Step 8: Run for all stocks
# -----------------------------------------------
for stock in [s.split('.')[0] for s in stocks]:
    merged_weekly, merged_monthly = merge_stock_sentiment(stock)
    plot_stock_sentiment(stock, merged_weekly, merged_monthly)
    generate_ai_summary(merged_weekly, stock)
