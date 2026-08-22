# pip install yfinance pandas matplotlib textblob openai python-dateutil

import os
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from textblob import TextBlob
from datetime import datetime
from dateutil.tz import tzlocal

# ========== CONFIG ==========
STOCKS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "CUMMINSIND.NS"]     # add more tickers as needed
NEWS_PER_STOCK = 80                               # number of headlines per stock
PRICE_PERIOD = "180d"                             # e.g., "90d", "1y"
OUT_DIR = "outputs"                               # where plots + report will be saved
USE_OPENAI = bool(os.environ.get("OPENAI_API_KEY"))
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
# ============================

os.makedirs(OUT_DIR, exist_ok=True)

# ---------- Utilities ----------
def safe_get(d, *keys, default=None):
    out = d
    try:
        for k in keys:
            out = out.get(k, {})
        if out == {}:
            return default
        return out
    except Exception:
        return default

def calc_sentiment(text: str):
    a = TextBlob(text or "")
    p = a.sentiment.polarity
    if p > 0.05: lbl = "Positive"
    elif p < -0.05: lbl = "Negative"
    else: lbl = "Neutral"
    return p, lbl

def fetch_news_sentiment(ticker: str, n: int = 80) -> pd.DataFrame:
    """Fetch latest Yahoo Finance news for ticker and score sentiment on the title."""
    tk = yf.Ticker(ticker)
    items = tk.news or []
    rows = []
    for item in items[:n]:
        content = item.get("content", {})
        title = content.get("title") or ""
        url = safe_get(content, "canonicalUrl", default={}).get("url", "")
        provider = safe_get(content, "provider", default={}).get("displayName", "")
        pub = content.get("pubDate", None)
        try:
            ts = pd.to_datetime(pub, utc=True)
        except Exception:
            ts = pd.NaT
        score, label = calc_sentiment(title)
        rows.append({
            "stock": ticker,
            "title": title,
            "url": url,
            "provider": provider,
            "pubDate": ts,
            "sentiment_score": score,
            "sentiment_label": label
        })
    df = pd.DataFrame(rows)
    df = df.dropna(subset=["pubDate"])
    return df

def build_sentiment_indices(df_news: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return weekly and monthly sentiment index per stock."""
    df = df_news.copy()
    df["pubDate"] = pd.to_datetime(df["pubDate"], utc=True)

    # Weekly (period end Sunday)
    weekly = (df
              .set_index("pubDate")
              .groupby("stock")
              .resample("W")["sentiment_score"]
              .mean()
              .reset_index()
              .rename(columns={"pubDate": "Date", "sentiment_score": "avg_sentiment_weekly"}))
    # Monthly (month-end) -> use 'ME' to avoid deprecation warning
    monthly = (df
               .set_index("pubDate")
               .groupby("stock")
               .resample("ME")["sentiment_score"]
               .mean()
               .reset_index()
               .rename(columns={"pubDate": "Date", "sentiment_score": "avg_sentiment_monthly"}))

    # Make both naive (no tz) to match yfinance price dates
    weekly["Date"] = pd.to_datetime(weekly["Date"]).dt.tz_localize(None)
    monthly["Date"] = pd.to_datetime(monthly["Date"]).dt.tz_localize(None)
    return weekly, monthly

def download_prices(stocks: list[str], period: str = "180d") -> pd.DataFrame:
    """Download adjusted price for multiple tickers and flatten columns."""
    px = yf.download(stocks, period=period, auto_adjust=True)
    if isinstance(px.columns, pd.MultiIndex):
        px.columns = ['_'.join(c).strip() for c in px.columns.to_flat_index()]
    px = px.reset_index()
    px["Date"] = pd.to_datetime(px["Date"]).dt.tz_localize(None)
    return px

def normalized_close_for(stocks: list[str], px: pd.DataFrame) -> pd.DataFrame:
    """Return normalized close (=100 at start) for comparative plot."""
    out = pd.DataFrame({"Date": px["Date"]})
    for s in stocks:
        col_close = None
        for c in px.columns:
            if c.lower().endswith(s.lower()) and c.startswith("Close"):
                col_close = c
                break
        if col_close is None:
            maybe = [c for c in px.columns if c.startswith("Close")]
            col_close = maybe[0] if maybe else None
        if col_close and px[col_close].notna().any():
            base = px[col_close].dropna().iloc[0]
            out[s.replace(".NS","")] = (px[col_close] / base) * 100.0
        else:
            out[s.replace(".NS","")] = pd.NA
    return out

def merge_price_with_sentiment(price_df: pd.DataFrame,
                               sentiment_idx: pd.DataFrame,
                               ticker: str,
                               kind: str = "weekly") -> pd.DataFrame:
    """
    Merge a single stock's Close with its weekly/monthly sentiment index using asof (backward).
    kind: 'weekly' or 'monthly'
    """
    assert kind in ("weekly", "monthly")
    base_sym = ticker.replace(".NS", "")
    close_col = f"Close_{base_sym}"

    # price_df should already have Date tz-naive; enforce
    price_df = price_df.copy()
    price_df["Date"] = pd.to_datetime(price_df["Date"]).dt.tz_localize(None)

    # Ensure we only keep the desired Close column
    if close_col not in price_df.columns:
        # try to find Close_<tickerstring> ending with ticker
        for c in price_df.columns:
            if c.startswith("Close_") and c.split("Close_")[-1].lower().endswith(base_sym.lower()):
                close_col = c
                break

    base = price_df[["Date", close_col]].dropna().sort_values("Date")

    # pick correct column name
    val_col = "avg_sentiment_weekly" if kind == "weekly" else "avg_sentiment_monthly"

    s = sentiment_idx[sentiment_idx["stock"] == ticker][["Date", val_col]].copy()
    s["Date"] = pd.to_datetime(s["Date"]).dt.tz_localize(None)
    s = s.sort_values("Date")

    merged = pd.merge_asof(base, s, on="Date", direction="backward")
    merged[val_col] = merged[val_col].fillna(0.0)
    merged["ticker"] = base_sym
    merged["period_type"] = kind
    return merged

def save_plot_price_vs_sentiment(merged: pd.DataFrame, stock_label: str, val_col: str, title_suffix: str, out_path: str):
    """Plot price (left axis) vs sentiment (right axis)."""
    fig, ax1 = plt.subplots(figsize=(12, 6))
    close_col = [c for c in merged.columns if c.startswith("Close_")][0]
    ax1.plot(merged["Date"], merged[close_col], label="Price")
    ax1.set_ylabel("Price (INR)")
    ax2 = ax1.twinx()
    ax2.plot(merged["Date"], merged[val_col], linestyle="--", label="Sentiment")
    ax2.set_ylabel("Avg Sentiment")
    plt.title(f"{stock_label} — Price vs {title_suffix} Sentiment")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)

def comparative_plot(px_norm: pd.DataFrame, out_path: str):
    """Plot normalized comparative returns for all stocks."""
    fig, ax = plt.subplots(figsize=(12, 6))
    for col in px_norm.columns:
        if col != "Date":
            ax.plot(px_norm["Date"], px_norm[col], label=col)
    ax.set_ylabel("Normalized Return (100 = start)")
    ax.legend()
    plt.title("Comparative Performance (Normalized)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)

def try_ai_summary(stock_name: str, weekly_df: pd.DataFrame, monthly_df: pd.DataFrame) -> str:
    """Use OpenAI (optional) to summarize sentiment trend."""
    if not USE_OPENAI:
        return "(AI summary skipped — set OPENAI_API_KEY to enable.)"
    try:
        from openai import OpenAI
        client = OpenAI()
        w_tail = weekly_df.tail(12).to_dict(orient="records")
        m_tail = monthly_df.tail(6).to_dict(orient="records")
        prompt = (
            f"Provide a concise 2–3 sentence summary of news sentiment trend for {stock_name}.\n"
            f"Weekly data (tail): {w_tail}\n"
            f"Monthly data (tail): {m_tail}\n"
            "Focus on overall direction, notable positive/negative spikes, and momentum."
        )
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=0.3
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"(AI summary error: {e})"

# ---------- Main flow ----------
def main():
    # 1) Fetch news + sentiment for each stock, concat
    all_news = []
    for t in STOCKS:
        df = fetch_news_sentiment(t, n=NEWS_PER_STOCK)
        all_news.append(df)
    df_news = pd.concat(all_news, ignore_index=True) if all_news else pd.DataFrame(columns=[
        "stock","title","url","provider","pubDate","sentiment_score","sentiment_label"
    ])
    if df_news.empty:
        print("No news fetched. Exiting.")
        return

    # 2) Build weekly & monthly sentiment indices
    weekly, monthly = build_sentiment_indices(df_news)

    # 3) Prices (auto-adjusted)
    px = download_prices(STOCKS, PRICE_PERIOD)

    # 4) Per-stock merges + plots + summaries
    report_lines = []
    ts_now = datetime.now(tzlocal()).strftime("%Y-%m-%d %H:%M %Z")
    report_lines.append(f"# Multi-Stock Price & Sentiment Report\n\n_Generated: {ts_now}_\n")

    # Add a comparative normalized chart across all stocks
    # Rename Close_<ticker> to Close_<base_sym> for consistency
    px_renamed = px.copy()
    for t in STOCKS:
        base = t.replace(".NS", "")
        old = f"Close_{t}"
        new = f"Close_{base}"
        if old in px_renamed.columns and new not in px_renamed.columns:
            px_renamed.rename(columns={old: new}, inplace=True)

    px_norm = normalized_close_for(STOCKS, px_renamed)
    comp_path = os.path.join(OUT_DIR, "comparative_normalized.png")
    comparative_plot(px_norm, comp_path)
    report_lines.append(f"![Comparative](./{os.path.basename(comp_path)})\n")

    for t in STOCKS:
        base = t.replace(".NS","")

        # weekly merged
        mw = merge_price_with_sentiment(px_renamed[["Date", f"Close_{base}"]], weekly, t, kind="weekly")
        # monthly merged
        mm = merge_price_with_sentiment(px_renamed[["Date", f"Close_{base}"]], monthly, t, kind="monthly")

        # plots
        w_plot = os.path.join(OUT_DIR, f"{base}_price_vs_weekly_sentiment.png")
        m_plot = os.path.join(OUT_DIR, f"{base}_price_vs_monthly_sentiment.png")
        save_plot_price_vs_sentiment(mw, base, "avg_sentiment_weekly", "Weekly", w_plot)
        save_plot_price_vs_sentiment(mm, base, "avg_sentiment_monthly", "Monthly", m_plot)

        # simple numeric snapshot
        last_week_senti = mw["avg_sentiment_weekly"].tail(1).iloc[0] if not mw.empty else 0
        last_month_senti = mm["avg_sentiment_monthly"].tail(1).iloc[0] if not mm.empty else 0

        # AI summary (optional)
        ai_sum = try_ai_summary(base, mw[["Date","avg_sentiment_weekly"]], mm[["Date","avg_sentiment_monthly"]])

        report_lines.append(f"\n## {base}\n")
        report_lines.append(f"- Latest weekly sentiment: **{last_week_senti:.2f}**")
        report_lines.append(f"- Latest monthly sentiment: **{last_month_senti:.2f}**\n")
        report_lines.append(f"**AI Summary:** {ai_sum}\n")
        report_lines.append(f"![{base} Weekly](./{os.path.basename(w_plot)})\n")
        report_lines.append(f"![{base} Monthly](./{os.path.basename(m_plot)})\n")

    # 5) Save a compact news table (last 15 headlines)
    tail_news = (df_news
                 .sort_values("pubDate", ascending=False)
                 .head(15))[["stock","pubDate","sentiment_label","title","url","provider"]]
    csv_path = os.path.join(OUT_DIR, "latest_headlines.csv")
    tail_news.to_csv(csv_path, index=False)
    report_lines.append("\n---\n### Latest headlines (CSV)\n")
    report_lines.append(f"- `{os.path.basename(csv_path)}` saved in `{OUT_DIR}`.\n")

    # 6) Write report
    report_path = os.path.join(OUT_DIR, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"Done. See {report_path}")

if __name__ == "__main__":
    main()
