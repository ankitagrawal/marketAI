# pip install yfinance pandas

import yfinance as yf
import pandas as pd
from datetime import datetime


def get_price_pe(symbol, years=12):

    stock = yf.Ticker(symbol)

    hist = stock.history(period=f"{years+2}y")

    if hist.empty:
        return pd.DataFrame()

    # Fix timezone
    hist.index = pd.to_datetime(hist.index)

    if hist.index.tz is not None:
        hist.index = hist.index.tz_convert(None)

    # Annual income statement
    income = stock.income_stmt

    shares = stock.info.get(
        "sharesOutstanding"
    )

    results=[]

    current_year=datetime.now().year

    for i in range(years):

        year=current_year-i

        target_date = pd.Timestamp(
            f"{year}-05-17"
        )

        row=hist.loc[
            hist.index<=target_date
        ].tail(1)

        if row.empty:
            continue

        price=round(
            row["Close"].iloc[0],
            2
        )

        pe=None

        try:

            eps=None

            # find matching annual report
            for col in income.columns:

                report_year=col.year

                if report_year==year:

                    net_income=income.loc[
                        "Net Income",
                        col
                    ]

                    eps=(
                        net_income/
                        shares
                    )

                    break

            if eps and eps>0:

                pe=round(
                    price/eps,
                    2
                )

        except Exception as e:
            print(e)

        results.append({
            "Year":year,
            "Price":price,
            "PE":pe
        })

    return pd.DataFrame(results)


df=get_price_pe(
    "HDFCBANK.NS"
)

print(df.to_string(index=False))