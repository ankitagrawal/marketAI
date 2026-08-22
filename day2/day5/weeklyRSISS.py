import os
from datetime import datetime

import yfinance as yf


def calculate_rsi(symbol, period=14):
    try:
        df = yf.download(
            symbol,
            period="5y",
            interval="1wk",
            auto_adjust=True,
            progress=False,
        )

        # Skip if no data
        if df.empty:
            print(f"Skipping {symbol}: No data found")
            return None

        # Handle both MultiIndex and single-column DataFrames
        if ("Close", symbol) in df.columns:
            close = df[("Close", symbol)]
        elif "Close" in df.columns:
            close = df["Close"]
        else:
            print(f"Skipping {symbol}: Close price not found")
            return None

        close = close.dropna()

        if len(close) < period:
            print(f"Skipping {symbol}: Insufficient data")
            return None

        delta = close.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        if rsi.dropna().empty:
            print(f"Skipping {symbol}: RSI could not be calculated")
            return None

        return round(float(rsi.dropna().iloc[-1]), 2)

    except Exception as e:
        print(f"Skipping {symbol}: {e}")
        return None


def calculate_wma_44(symbol, slope_lookback=6, min_slope_pct=0.5):
    """Return (last_close, 44 WMA, is_above_wma, is_rising, slope_pct).

    For swing trading, the 44 WMA is considered rising when it has climbed at
    least `min_slope_pct` percent over the last `slope_lookback` weeks. The
    lookback filters out single-week noise and the strength floor skips
    nearly-flat averages.
    """
    try:
        df = yf.download(
            symbol,
            period="5y",
            interval="1wk",
            auto_adjust=True,
            progress=False,
        )

        # Skip if no data
        if df.empty:
            print(f"Skipping {symbol}: No data found")
            return None

        # Handle both MultiIndex and single-column DataFrames
        if ("Close", symbol) in df.columns:
            close = df[("Close", symbol)]
        elif "Close" in df.columns:
            close = df["Close"]
        else:
            print(f"Skipping {symbol}: Close price not found")
            return None

        close = close.dropna()

        if len(close) < 44:
            print(f"Skipping {symbol}: Insufficient data for 44 WMA")
            return None

        wma_44 = close.rolling(window=44).mean().dropna()

        if wma_44.empty:
            print(f"Skipping {symbol}: 44 WMA could not be calculated")
            return None

        last_close = float(close.iloc[-1])
        last_wma = float(wma_44.iloc[-1])
        is_above = last_close > last_wma

        # 44 WMA slope over the lookback window (percentage change).
        # Rising = current WMA is above where it was `slope_lookback` weeks ago.
        if len(wma_44) > slope_lookback:
            prior_wma = float(wma_44.iloc[-1 - slope_lookback])
            slope_pct = round((last_wma - prior_wma) / prior_wma * 100, 2)
        else:
            slope_pct = 0.0
        is_rising = slope_pct >= min_slope_pct

        return round(last_close, 2), round(last_wma, 2), is_above, is_rising, slope_pct

    except Exception as e:
        print(f"Skipping {symbol}: {e}")
        return None


def calculate_dma_44(symbol, slope_lookback=6, min_slope_pct=0.5,
                     cross_lookback=10):
    """Return DMA metrics used for both momentum and early-entry signals.

    Returns:
        (last_close, 44 DMA, is_above_dma, is_rising, slope_pct,
         dist_pct, is_fresh_cross, is_turning_up)

    where:
        dist_pct       - how far price is above (+) / below (-) the 44 DMA, %
        is_fresh_cross - price is above the DMA now but was below it within
                         the last `cross_lookback` trading days (a reclaim)
        is_turning_up  - the DMA slope just flipped from <= 0 to > 0 (a curl)

    Same swing-trade logic as calculate_wma_44 but on the 44-day moving
    average using daily data. Rising = the 44 DMA has climbed at least
    `min_slope_pct` percent over the last `slope_lookback` trading days.
    """
    try:
        df = yf.download(
            symbol,
            period="1y",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )

        # Skip if no data
        if df.empty:
            print(f"Skipping {symbol}: No data found")
            return None

        # Handle both MultiIndex and single-column DataFrames
        if ("Close", symbol) in df.columns:
            close = df[("Close", symbol)]
        elif "Close" in df.columns:
            close = df["Close"]
        else:
            print(f"Skipping {symbol}: Close price not found")
            return None

        close = close.dropna()

        if len(close) < 44:
            print(f"Skipping {symbol}: Insufficient data for 44 DMA")
            return None

        dma_44 = close.rolling(window=44).mean().dropna()

        if dma_44.empty:
            print(f"Skipping {symbol}: 44 DMA could not be calculated")
            return None

        last_close = float(close.iloc[-1])
        last_dma = float(dma_44.iloc[-1])
        is_above = last_close > last_dma

        # How far price is above (+) / below (-) the 44 DMA, in percent.
        dist_pct = round((last_close - last_dma) / last_dma * 100, 2)

        # 44 DMA slope over the lookback window (percentage change).
        if len(dma_44) > slope_lookback:
            prior_dma = float(dma_44.iloc[-1 - slope_lookback])
            slope_pct = round((last_dma - prior_dma) / prior_dma * 100, 2)
        else:
            slope_pct = 0.0
        is_rising = slope_pct >= min_slope_pct

        # Fresh cross: price is above the DMA now but was below it at some
        # point within the last `cross_lookback` days (a reclaim, not a
        # long-established trend).
        # Align close to the DMA index so the comparison is element-wise.
        aligned_close = close.reindex(dma_44.index)
        recent = min(cross_lookback, len(dma_44) - 1)
        was_below = bool((aligned_close.iloc[-1 - recent:-1] < dma_44.iloc[-1 - recent:-1]).any())
        is_fresh_cross = is_above and was_below

        # Turning up: the DMA slope just flipped from <= 0 to > 0. Compare the
        # most recent 1-day change vs. the change `recent` days earlier.
        if len(dma_44) > recent + 1:
            latest_step = last_dma - float(dma_44.iloc[-2])
            prior_step = float(dma_44.iloc[-1 - recent]) - float(dma_44.iloc[-2 - recent])
            is_turning_up = latest_step > 0 >= prior_step
        else:
            is_turning_up = False

        return (round(last_close, 2), round(last_dma, 2), is_above, is_rising,
                slope_pct, dist_pct, is_fresh_cross, is_turning_up)

    except Exception as e:
        print(f"Skipping {symbol}: {e}")
        return None
watchlist = [
           "PIDILITIND.NS", "SOLARINDS.NS", "APOLLOHOSP.NS",
         "ASIANPAINT.NS", "HDFCBANK.NS",  "TCS.NS",
         "IRCTC.NS",      "DIXON.NS",     "CDSL.NS",
         "KOTAKBANK.NS",  "MARUTI.NS",    "SBIN.NS",
         "BEL.NS",        "HAL.NS",       "LTFOODS.NS",
         "SIEMENS.NS",    "HCLTECH.NS",   "VBL.NS",
     ]
    

etfs = [
        "HDFCBANK.NS",
        "INDIGO.NS",
        "ICICIBANK.NS",
        "M&M.NS",
        "SBIN.NS",
        "RELIANCE.NS",
        "INFY.NS",
        "BHARTIARTL.NS",
        "MARUTI.NS",
        "LT.NS",
        "BAJFINANCE.NS",
        "HINDALCO.NS",
        "OFSS.NS",
        "MOTHERSON.NS",
        "AXISBANK.NS",
        "BSE.NS",
        "VEDL.NS",
        "TCS.NS",
        "ASHOKLEY.NS",
        "HSCL.NS",
        "NATIONALUM.NS",
        "MSUMI.NS",
        "SHRIRAMFIN.NS",
        "BEL.NS",
        "TMCV.NS",
        "AEGISLOG.NS",
        "KAYNES.NS",
        "MCX.NS",
        "ONGC.NS",
        "TVSMOTOR.NS",
        "CHOLAFIN.NS",
        "NTPC.NS",
        "KOTAKBANK.NS",
        "HCLTECH.NS",
        "PINELABS.NS",
        "TATASTEEL.NS",
        "HEROMOTOCO.NS",
        "BANDHANBNK.NS",
        "NETWEB.NS",
        "MAXHEALTH.NS",
        "TATACHEM.NS",
        "TMPV.NS",
        "ASIANPAINT.NS",
        "ETERNAL.NS",
        "CANBK.NS",
        "ADANIENT.NS",
        "EICHERMOT.NS",
        "DIXON.NS",
        "HFCL.NS",
        "MUTHOOTFIN.NS",
        "IDEA.NS",
        "SUZLON.NS",
        "SYRMA.NS",
        "GROWW.NS",
        "LODHA.NS",
        "POWERGRID.NS",
        "IRFC.NS",
        "ULTRACEMCO.NS",
        "TRENT.NS",
        "POWERINDIA.NS",
        "COFORGE.NS",
        "MEESHO.NS",
        "NAUKRI.NS",
        "ADANIPOWER.NS",
        "HINDUNILVR.NS",
        "HINDZINC.NS",
        "POLYCAB.NS",
        "PFC.NS",
        "FORCEMOT.NS",
        "WIPRO.NS",
        "TECHM.NS",
        "ADANIGREEN.NS",
        "BHEL.NS",
        "BAJAJ-AUTO.NS",
        "SUNPHARMA.NS",
        "ADANIPORTS.NS",
        "JINDALSTEL.NS",
        "TATACONSUM.NS",
        "OLAELEC.NS",
        "ITC.NS",
        "AUROPHARMA.NS",
        "APOLLOHOSP.NS",
        "HONASA.NS",
        "SWIGGY.NS",
        "TITAN.NS",
        "M&MFIN.NS",
        "HAL.NS",
        "DATAPATTNS.NS",
        "INDUSTOWER.NS",
        "TATACAP.NS",
        "KEI.NS",
        "COALINDIA.NS",
        "CGPOWER.NS",
        "KIRLOSENG.NS",
        "BANKBARODA.NS",
        "PAYTM.NS",
        "BPCL.NS",
        "IFCI.NS",
        "ZEEL.NS",
        "BHARATFORG.NS",
        "NESTLEIND.NS",
        "PAGEIND.NS",
        "LICI.NS",
        "CUMMINSIND.NS",
        "JSWINFRA.NS",
        "WELCORP.NS",
        "OIL.NS",
        "BOSCHLTD.NS",
        "APARINDS.NS",
        "SAMMAANCAP.NS",
        "LTF.NS",
        "TATAPOWER.NS",
        "GMRAIRPORT.NS",
        "GRASIM.NS",
        "UNITDSPR.NS",
        "TEJASNET.NS",
        "DLF.NS",
        "INDHOTEL.NS",
        "MANAPPURAM.NS",
        "CARTRADE.NS",
        "HINDPETRO.NS",
        "AUBANK.NS",
        "RRKABEL.NS",
        "RECLTD.NS",
        "MAZDOCK.NS",
        "DRREDDY.NS",
        "SBICARD.NS",
        "PIDILITIND.NS",
        "EXIDEIND.NS",
        "HDFCAMC.NS",
        "UNIONBANK.NS",
        "YESBANK.NS",
        "GODREJPROP.NS",
        "VBL.NS",
        "JSWSTEEL.NS",
        "JIOFIN.NS",
        "IOC.NS",
        "SONACOMS.NS",
        "FEDERALBNK.NS",
        "LAURUSLABS.NS",
        "AMBER.NS",
        "BAJAJFINSV.NS",
        "SAIL.NS",
        "RVNL.NS",
        "NMDC.NS",
        "RBLBANK.NS",
        "PNB.NS",
        "ANANDRATHI.NS",
        "SUPREMEIND.NS",
        "PERSISTENT.NS",
        "ADANIENSOL.NS",
        "NYKAA.NS",
        "SOLARINDS.NS",
        "SIEMENS.NS",
        "HINDCOPPER.NS",
        "ATHERENERG.NS",
        "CDSL.NS",
        "CIPLA.NS",
        "UNOMINDA.NS",
        "EMCURE.NS",
        "HBLENGINE.NS",
        "GAIL.NS",
        "INDIANB.NS",
        "GRSE.NS",
        "WOCKPHARMA.NS",
        "BDL.NS",
        "SBILIFE.NS",
        "ABB.NS",
        "WAAREEENER.NS",
        "DMART.NS",
        "ABCAPITAL.NS",
        "MARICO.NS",
        "PNBHOUSING.NS",
        "LENSKART.NS",
        "DIVISLAB.NS",
        "TIINDIA.NS",
        "ASTRAL.NS",
        "AADHARHFC.NS",
        "IIFL.NS",
        "HYUNDAI.NS",
        "VMM.NS",
        "OBEROIRLTY.NS",
        "SCI.NS",
        "KPRMILL.NS",
        "GESHIP.NS",
        "ZENTEC.NS",
        "IDBI.NS",
        "COLPAL.NS",
        "INDUSINDBK.NS",
        "AMBUJACEM.NS",
        "RADICO.NS",
        "POLICYBZR.NS",
        "CAMS.NS",
        "PIIND.NS",
        "OLECTRA.NS",
        "DELHIVERY.NS",
        "GLAND.NS",
        "REDINGTON.NS",
        "ZYDUSLIFE.NS",
        "PWL.NS",
        "ENRIN.NS",
        "PHOENIXLTD.NS",
        "ATGL.NS",
        "JSWENERGY.NS",
        "APLAPOLLO.NS",
        "COCHINSHIP.NS",
        "THERMAX.NS",
        "KALYANKJIL.NS",
        "ANGELONE.NS",
        "NHPC.NS",
        "PRESTIGE.NS",
        "MOTILALOFS.NS",
        "HAVELLS.NS",
        "POONAWALLA.NS",
        "IDFCFIRSTB.NS",
        "SRF.NS",
        "PATANJALI.NS",
        "NBCC.NS",
        "MFSL.NS",
        "MAHABANK.NS",
        "CHOICEIN.NS",
        "LICHSGFIN.NS",
        "FORTIS.NS",
        "BRITANNIA.NS",
        "MANKIND.NS",
        "BANKINDIA.NS",
        "BELRISE.NS",
        "BIOCON.NS",
        "GODREJCP.NS",
        "BLUEJET.NS",
        "UPL.NS",
        "PREMIERENE.NS",
        "TATACOMM.NS",
        "TORNTPHARM.NS",
        "LTM.NS",
        "ICICIAMC.NS",
        "HDFCLIFE.NS",
        "NUVAMA.NS",
        "PPLPHARMA.NS",
        "PETRONET.NS",
        "PCBL.NS",
        "AWL.NS",
        "GRAPHITE.NS",
        "TATAELXSI.NS",
        "CROMPTON.NS",
        "MPHASIS.NS",
        "SHREECEM.NS",
        "TARIL.NS",
        "JKTYRE.NS",
        "NAVINFLUOR.NS",
        "KPITTECH.NS",
        "TITAGARH.NS",
        "VOLTAS.NS",
        "ALKEM.NS",
        "NLCINDIA.NS",
        "APOLLOTYRE.NS",
        "NIACL.NS",
        "CUB.NS",
        "360ONE.NS",
        "DABUR.NS",
        "ICICIGI.NS",
        "GLENMARK.NS",
        "LUPIN.NS",
        "VIJAYA.NS",
        "EMMVEE.NS",
        "HDBFS.NS",
        "CGCL.NS",
        "NATCOPHARM.NS",
        "JYOTICNC.NS",
        "IGL.NS",
        "ENGINERSIN.NS",
        "EMAMILTD.NS",
        "ACUTAAS.NS",
        "SAILIFE.NS",
        "LGEINDIA.NS",
        "IREDA.NS",
        "TRITURBINE.NS",
        "KFINTECH.NS",
        "ZFCVINDIA.NS",
        "NAM-INDIA.NS",
        "ACMESOLAR.NS",
        "LEMONTREE.NS",
        "INDIACEM.NS",
        "CONCOR.NS",
        "DALBHARAT.NS",
        "GODFRYPHLP.NS",
        "JPPOWER.NS",
        "JWL.NS",
        "PGEL.NS",
        "ENDURANCE.NS",
        "NEULANDLAB.NS",
        "MRF.NS",
        "JSWCEMENT.NS",
        "HOMEFIRST.NS",
        "KAJARIACER.NS",
        "RPOWER.NS",
        "LLOYDSME.NS",
        "GABRIEL.NS",
        "ANANTRAJ.NS",
        "COHANCE.NS",
        "PIRAMALFIN.NS",
        "HUDCO.NS",
        "INOXWIND.NS",
        "JINDALSAW.NS",
        "JAINREC.NS",
        "IEX.NS",
        "RAMCOCEM.NS",
        "BSOFT.NS",
        "NH.NS",
        "MINDACORP.NS",
        "JUBLFOOD.NS",
        "TENNIND.NS",
        "J&KBANK.NS",
        "BRIGADE.NS",
        "TATAINVEST.NS",
        "TATATECH.NS",
        "CPPLUS.NS",
        "CEATLTD.NS",
        "SUNDARMFIN.NS",
        "CHENNPETRO.NS",
        "ESCORTS.NS",
        "SCHNEIDER.NS",
        "ABREL.NS",
        "ICICIPRULI.NS",
        "SHYAMMETL.NS",
        "AARTIIND.NS",
        "LALPATHLAB.NS",
        "GMDCLTD.NS",
        "GRANULES.NS",
        "SAGILITY.NS",
        "MRPL.NS",
        "WELSPUNLIV.NS",
        "SAREGAMA.NS",
        "STARHEALTH.NS",
        "CEMPRO.NS",
        "ABSLAMC.NS",
        "HEG.NS",
        "TORNTPOWER.NS",
        "BATAINDIA.NS",
        "ITCHOTELS.NS",
        "MMTC.NS",
        "CREDITACC.NS",
        "SYNGENE.NS",
        "APTUS.NS",
        "SIGNATURE.NS",
        "COROMANDEL.NS",
        "FLUOROCHEM.NS",
        "BAJAJHLDNG.NS",
        "JSL.NS",
        "KARURVYSYA.NS",
        "TECHNOE.NS",
        "JBMA.NS",
        "DEEPAKFERT.NS",
        "BAJAJHFL.NS",
        "FIRSTCRY.NS",
        "KEC.NS",
        "ARE&M.NS",
        "ABBOTINDIA.NS",
        "BEML.NS",
        "ASAHIINDIA.NS",
        "PARADEEP.NS",
        "BERGEPAINT.NS",
        "CHAMBLFERT.NS",
        "BHARTIHEXA.NS",
        "IRCTC.NS",
        "LTFOODS.NS",
        "GICRE.NS",
        "ECLERX.NS",
        "JBCHEPHARM.NS",
        "AFFLE.NS",
        "MEDANTA.NS",
        "SCHAEFFLER.NS",
        "CASTROLIND.NS",
        "KPIL.NS",
        "ASTERDM.NS",
        "IGIL.NS",
        "NCC.NS",
        "FINCABLES.NS",
        "WHIRLPOOL.NS",
        "TIMKEN.NS",
        "GLAXO.NS",
        "USHAMART.NS",
        "CENTRALBK.NS",
        "IPCALAB.NS",
        "ABFRL.NS",
        "HEXT.NS",
        "FIVESTAR.NS",
        "AIAENG.NS",
        "ZYDUSWELL.NS",
        "NTPCGREEN.NS",
        "CRAFTSMAN.NS",
        "ELGIEQUIP.NS",
        "ACC.NS",
        "BLS.NS",
        "ACE.NS",
        "JKCEMENT.NS",
        "ANURAS.NS",
        "URBANCO.NS",
        "GPIL.NS",
        "ELECON.NS",
        "BALKRISIND.NS",
        "CYIENT.NS",
        "NEWGEN.NS",
        "AFCONS.NS",
        "CONCORDBIO.NS",
        "JMFINANCIL.NS",
        "LATENTVIEW.NS",
        "IRCON.NS",
        "ONESOURCE.NS",
        "EIDPARRY.NS",
        "TRIDENT.NS",
        "CLEAN.NS",
        "RITES.NS",
        "PVRINOX.NS",
        "POLYMED.NS",
        "LTTS.NS",
        "CAPLIPOINT.NS",
        "HONAUT.NS",
        "GRAVITA.NS",
        "KIMS.NS",
        "CARBORUNIV.NS",
        "BLUESTARCO.NS",
        "RKFORGE.NS",
        "VTL.NS",
        "NSLNISP.NS",
        "SONATSOFTW.NS",
        "MAPMYINDIA.NS",
        "AIIL.NS",
        "CESC.NS",
        "MGL.NS",
        "INDIAMART.NS",
        "CHOLAHLDNG.NS",
        "ANTHEM.NS",
        "SWANCORP.NS",
        "BALRAMCHIN.NS",
        "IRB.NS",
        "PTCIL.NS",
        "UCOBANK.NS",
        "GILLETTE.NS",
        "CCL.NS",
        "RAILTEL.NS",
        "THELEELA.NS",
        "DEEPAKNTR.NS",
        "GODREJIND.NS",
        "ZENSARTECH.NS",
        "DOMS.NS",
        "FSL.NS",
        "SARDAEN.NS",
        "DEVYANI.NS",
        "IKS.NS",
        "FACT.NS",
        "INTELLECT.NS",
        "SUMICHEM.NS",
        "CHALET.NS",
        "AAVAS.NS",
        "TBOTEK.NS",
        "ITI.NS",
        "SJVN.NS",
        "AJANTPHARM.NS",
        "BAYERCROP.NS",
        "LINDEINDIA.NS",
        "NIVABUPA.NS",
        "AEGISVOPAK.NS",
        "ATUL.NS",
        "JSWDULUX.NS",
        "UTIAMC.NS",
        "ABLBL.NS",
        "RAINBOW.NS",
        "SAPPHIRE.NS",
        "CRISIL.NS",
        "CANFINHOME.NS",
        "NUVOCO.NS",
        "NAVA.NS",
        "SBFC.NS",
        "JUBLPHARMA.NS",
        "ABDL.NS",
        "SOBHA.NS",
        "IOB.NS",
        "TTML.NS",
        "JUBLINGREA.NS",
        "RHIM.NS",
        "PFIZER.NS",
        "BIKAJI.NS",
        "BLUEDART.NS",
        "SUNTV.NS",
        "CIEINDIA.NS",
        "TEGA.NS",
        "UBL.NS",
        "INDGN.NS",
        "CANHLIFE.NS",
        "3MINDIA.NS",
        "BBTC.NS",
        "ERIS.NS",
        "SPLPETRO.NS",
        "TRAVELFOOD.NS",
        "GODIGIT.NS",
        "EIHOTEL.NS",
        "GALLANTT.NS",
        "DCMSHRIRAM.NS",
    ]


# Slope lookback used inside the MA functions (must match their default).
SLOPE_LOOKBACK = 6

# Early-entry tuning:
#   MAX_EXTENSION_PCT - reject stocks more than this % above the 44 DMA
#                       (too extended = late, not early).
#   RSI_LOW/RSI_HIGH  - weekly RSI band for "momentum building, not overbought".
MAX_EXTENSION_PCT = 5.0
RSI_LOW = 50.0
RSI_HIGH = 65.0

# Save results to a timestamped file named after this source script.
_source_name = os.path.splitext(os.path.basename(__file__))[0]
_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
_output_dir = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(_output_dir, exist_ok=True)
_output_path = os.path.join(_output_dir, f"{_source_name}_{_timestamp}.txt")
_output_file = open(_output_path, "w", encoding="utf-8")


def out(*args, **kwargs):
    """Print to console AND append to the timestamped results file."""
    print(*args, **kwargs)
    kwargs.pop("flush", None)
    print(*args, file=_output_file, **kwargs)


out(
    f"{'ETF':<20} {'Weekly RSI':<12} {'Close':<12} "
    f"{'44 WMA':<12} {'W>WMA':<8} {'WMA Rise':<10} {'W Slope%':<10} "
    f"{'44 DMA':<12} {'D>DMA':<8} {'DMA Rise':<10} {'D Slope%':<10} "
    f"{'Dist%':<8} {'Momentum':<10} {'Early':<8} {'Turn'}"
)
out("-" * 175)

above_rising_wma = []
above_rising_dma = []
strong_momentum = []
early_pullback = []
fresh_turn = []

for ticker in etfs:
    rsi = calculate_rsi(ticker)
    wma = calculate_wma_44(ticker)
    dma = calculate_dma_44(ticker)

    if rsi is not None and wma is not None and dma is not None:
        last_close, last_wma, w_above, w_rising, w_slope = wma
        (_, last_dma, d_above, d_rising, d_slope,
         dist_pct, is_fresh_cross, is_turning_up) = dma

        # Normalize both slopes to "% per trading day" so the daily and weekly
        # trends are compared on the same time basis (1 week ~ 5 trading days).
        w_slope_per_day = w_slope / (SLOPE_LOOKBACK * 5)
        d_slope_per_day = d_slope / SLOPE_LOOKBACK

        # Strong, fresh momentum (may already be extended / late):
        #   1. proper stacking: price > 44 DMA > 44 WMA
        #   2. both averages rising
        #   3. daily trend accelerating faster than the weekly trend
        is_stacked = last_close > last_dma > last_wma
        is_fresh = d_slope_per_day > w_slope_per_day
        is_momentum = is_stacked and w_rising and d_rising and is_fresh

        # Early / pullback-in-uptrend (better entry, not chased):
        #   - long-term trend up (44 WMA rising)
        #   - price above 44 DMA but NOT extended (within MAX_EXTENSION_PCT)
        #   - 44 DMA rising or just turning up
        #   - weekly RSI in the "building" band, not overbought
        is_early = (
            w_rising
            and d_above
            and 0 <= dist_pct <= MAX_EXTENSION_PCT
            and (d_rising or is_turning_up)
            and RSI_LOW <= rsi <= RSI_HIGH
        )

        # Fresh turn / crossover (earliest, more speculative):
        #   - long-term trend up
        #   - price just reclaimed the 44 DMA OR the DMA is just curling up
        is_turn = w_rising and (is_fresh_cross or is_turning_up)

        out(
            f"{ticker:<20} {rsi:<12} {last_close:<12} "
            f"{last_wma:<12} {('Yes' if w_above else 'No'):<8} "
            f"{('Yes' if w_rising else 'No'):<10} {w_slope:<10} "
            f"{last_dma:<12} {('Yes' if d_above else 'No'):<8} "
            f"{('Yes' if d_rising else 'No'):<10} {d_slope:<10} "
            f"{dist_pct:<8} {('Yes' if is_momentum else 'No'):<10} "
            f"{('Yes' if is_early else 'No'):<8} {'Yes' if is_turn else 'No'}"
        )
        if w_above and w_rising:
            above_rising_wma.append(ticker)
        if d_above and d_rising:
            above_rising_dma.append(ticker)
        if is_momentum:
            strong_momentum.append(ticker)
        if is_early:
            early_pullback.append(ticker)
        if is_turn:
            fresh_turn.append(ticker)

out("\nStocks above a rising 44-week moving average (WMA):")
out("-" * 50)
for ticker in above_rising_wma:
    out(ticker)

out("\nStocks above a rising 44-day moving average (DMA):")
out("-" * 50)
for ticker in above_rising_dma:
    out(ticker)

out("\nStocks above a rising 44 WMA AND a rising 44 DMA:")
out("-" * 50)
for ticker in sorted(set(above_rising_wma) & set(above_rising_dma)):
    out(ticker)

out("\nStrong momentum (price > 44DMA > 44WMA, both rising, DMA accelerating):")
out("  NOTE: these have already run - later/extended entries.")
out("-" * 70)
for ticker in strong_momentum:
    out(ticker)

out(f"\nEARLY - pullback in uptrend (44WMA rising, 0-{MAX_EXTENSION_PCT:.0f}% "
    f"above 44DMA, RSI {RSI_LOW:.0f}-{RSI_HIGH:.0f}):")
out("  Trend confirmed but entry not extended - best risk/reward.")
out("-" * 70)
for ticker in early_pullback:
    out(ticker)

out("\nTURN - fresh reclaim / DMA curling up (44WMA rising):")
out("  Earliest signal, more speculative - confirm before entry.")
out("-" * 70)
for ticker in fresh_turn:
    out(ticker)

_output_file.close()
print(f"\nResults saved to: {_output_path}")