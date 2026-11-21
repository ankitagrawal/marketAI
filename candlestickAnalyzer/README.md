# Candlestick Analyzer

Standalone technical-analysis project built from the EIFS "Charting" notes.

- `patterns.py` – detection engine (Hammer, Hanging Man, Shooting Star, Inverted Hammer, Engulfing, Piercing, Dark Cloud, Harami (+Cross), Morning/Evening (Doji) Star, Rising/Falling Three Methods) with trend context, confirmation status, stop-loss and R-multiple target.
- `data.py` – yfinance loader / symbol parsing (`.NS` default).
- `panel.py` – Streamlit panel: multi-symbol scanner, candlestick chart with markers, trade-plan table, pattern guide.
- `tests/` – synthetic-candle unit tests.

```
pip install -r requirements.txt
streamlit run panel.py
python -m pytest tests   # or: python tests/test_patterns.py
```
