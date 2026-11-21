import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
from patterns import detect_patterns


def frame(candles):
    idx = pd.date_range("2024-01-01", periods=len(candles), freq="D")
    return pd.DataFrame(candles, columns=["Open", "High", "Low", "Close"], index=idx)


def trend(start, step, n=8):
    out, p = [], start
    for _ in range(n):
        o, c = p, p + step
        out.append((o, max(o, c) + 0.3, min(o, c) - 0.3, c))
        p = c
    return out, p


def names(df):
    return set(detect_patterns(df).pattern)


def down(): return trend(100, -2)
def up(): return trend(100, 2)


def test_hammer():
    c, p = down()
    c.append((p, p + 0.1, p - 4, p + 0.4))
    assert "Hammer" in names(frame(c))


def test_hanging_man_confirmation():
    c, p = up()
    c.append((p, p + 0.1, p - 4, p + 0.4))
    c.append((p, p + 0.2, p - 3, p - 2))
    h = detect_patterns(frame(c))
    r = h[h.pattern == "Hanging Man"].iloc[0]
    assert r.status == "Confirmed"


def test_shooting_star_and_inverted_hammer():
    c, p = up(); c.append((p + 1, p + 6, p + 0.9, p + 1.3))
    assert "Shooting Star" in names(frame(c))
    c, p = down(); c.append((p - 1, p + 4, p - 1.1, p - 1.4))
    assert "Inverted Hammer" in names(frame(c))


def test_engulfing():
    c, p = down()
    c.append((p, p + 0.2, p - 1.2, p - 1))          # small black
    c.append((p - 1.5, p + 2, p - 1.6, p + 1.5))     # white engulfs
    assert "Bullish Engulfing" in names(frame(c))
    c, p = up()
    c.append((p, p + 1.2, p - 0.2, p + 1))
    c.append((p + 1.5, p + 1.6, p - 2, p - 1.5))
    assert "Bearish Engulfing" in names(frame(c))


def test_piercing_and_dark_cloud():
    c, p = down()
    c.append((p, p + 0.2, p - 4.2, p - 4))           # long black
    c.append((p - 4.5, p - 0.5, p - 4.6, p - 1))     # opens below, closes >50%
    assert "Piercing Pattern" in names(frame(c))
    c, p = up()
    c.append((p, p + 4.2, p - 0.2, p + 4))
    c.append((p + 4.5, p + 4.6, p + 0.5, p + 1))
    assert "Dark Cloud Cover" in names(frame(c))


def test_harami():
    c, p = down()
    c.append((p, p + 0.2, p - 4.2, p - 4))
    c.append((p - 1.5, p - 0.8, p - 3.2, p - 2.5))
    assert "Bullish Harami" in names(frame(c))


def test_morning_evening_star():
    c, p = down()
    c.append((p, p + 0.2, p - 4.2, p - 4))
    c.append((p - 5, p - 4.6, p - 5.4, p - 4.8))
    c.append((p - 4.7, p - 0.9, p - 4.8, p - 1))
    assert "Morning Star" in names(frame(c))
    c, p = up()
    c.append((p, p + 4.2, p - 0.2, p + 4))
    c.append((p + 5, p + 5.4, p + 4.6, p + 4.8))
    c.append((p + 4.7, p + 4.8, p + 0.9, p + 1))
    assert "Evening Star" in names(frame(c))


def test_three_methods():
    c, p = up()
    c.append((p, p + 6.2, p - 0.2, p + 6))
    for o, cl in [(p + 5.5, p + 4.5), (p + 4.6, p + 4), (p + 4.1, p + 3.6)]:
        c.append((o, max(o, cl) + 0.2, min(o, cl) - 0.2, cl))
    c.append((p + 3.7, p + 8.2, p + 3.6, p + 8))
    assert "Rising Three Methods" in names(frame(c))


def test_no_false_signal_on_flat():
    c = [(100, 100.5, 99.5, 100.1)] * 30
    assert detect_patterns(frame(c)).empty


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("ok", k)
