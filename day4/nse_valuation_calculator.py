"""
NSE Sector Valuation Calculator
================================
Replicates the Excel valuation model with automated calculations.

Formula:
1. Base EPS = avg(EPS_2016, EPS_2017, EPS_2018) — pre-COVID stable cycle
2. Projected EPS = Base EPS × (1.15)^9  [9 years from 2017 midpoint to 2026]
3. Fair Value = Projected EPS × Avg P/E (sector-specific)
4. MOS Price = Fair Value × 0.65 (35% margin of safety)
5. SELL signal = Current Price > 1.2 × Fair Value
6. BUY signal = MOS Price ≥ 0.85 × Current Price
"""

import pandas as pd
from datetime import datetime, timedelta
from openpyxl import load_workbook


# ============================================================================
# SECTOR CONFIGURATION (from your Excel — hardcoded per sector)
# ============================================================================

SECTOR_CONFIG = {
    'Nifty': {
        'label': 'NIFTY 50',
        'avgPe': 20.8,
        'sheet_name': 'Nifty'
    },
    'IT': {
        'label': 'NIFTY IT',
        'avgPe': 24.0,
        'sheet_name': 'IT'
    },
    'Auto': {
        'label': 'NIFTY AUTO',
        'avgPe': 33.0,
        'sheet_name': 'Auto'
    },
    'Bank': {
        'label': 'NIFTY BANK',
        'avgPe': 18.36,
        'sheet_name': 'Bank'
    },
    'FMCG': {
        'label': 'NIFTY FMCG',
        'avgPe': 38.0,
        'sheet_name': 'FMCG'
    },
    'PHARMA': {
        'label': 'NIFTY PHARMA',
        'avgPe': 39.0,
        'sheet_name': 'PHARMA'
    },
    'Finance': {
        'label': 'NIFTY FIN SERVICES',
        'avgPe': 22.0,
        'sheet_name': 'Finance'
    },
    'Metal': {
        'label': 'NIFTY METAL',
        'avgPe': 15.0,
        'sheet_name': 'Metal'
    },
    'Energy': {
        'label': 'NIFTY ENERGY',
        'avgPe': 13.0,
        'sheet_name': 'Energy'
    },
    'pvtBank': {
        'label': 'NIFTY PRIVATE BANK',
        'avgPe': 26.0,
        'sheet_name': 'pvtBank'
    },
    'INFRA': {
        'label': 'NIFTY INFRASTRUCTURE',
        'avgPe': 27.0,
        'sheet_name': 'INFRA'
    },
}

# Base years for EPS calculation (pre-COVID stable)
BASE_YEARS = [2016, 2017, 2018]
BASE_MIDPOINT = 2017

# FV calculation years (from base midpoint to current year)
CURRENT_YEAR = 2026
FV_YEARS = CURRENT_YEAR - BASE_MIDPOINT  # = 9 years

# Growth rate (15% CAGR)
GROWTH_RATE = 0.15


# ============================================================================
# CORE VALUATION FUNCTIONS
# ============================================================================

def calculate_eps(price, pe):
    """Calculate EPS from price and P/E ratio."""
    if pe and pe > 0:
        return round(price / pe, 2)
    return 0


def calculate_base_eps(yearly_data, base_years=BASE_YEARS):
    """
    Calculate base EPS as average of specified years.
    Excludes COVID years (2020, 2021) even if in base_years list.
    """
    base_rows = [
        row for row in yearly_data 
        if row['year'] in base_years 
        and row['eps'] > 0
        and row['year'] not in [2020, 2021]  # Exclude COVID years
    ]
    
    if not base_rows:
        return 0
    
    return round(sum(r['eps'] for r in base_rows) / len(base_rows), 2)


def calculate_projected_eps(base_eps, fv_years=FV_YEARS, growth_rate=GROWTH_RATE):
    """
    Project EPS forward using FV formula: BaseEPS × (1 + growth_rate)^fv_years
    This replicates Excel's =FV(15%, N, 0, -BaseEPS)
    """
    return round(base_eps * ((1 + growth_rate) ** fv_years), 2)


def calculate_fair_value(projected_eps, avg_pe):
    """Calculate fair value: Projected EPS × Average P/E."""
    return round(projected_eps * avg_pe, 2)


def calculate_mos(fair_value, mos_discount=0.65):
    """Calculate Margin of Safety price: Fair Value × 0.65 (35% discount)."""
    return round(fair_value * mos_discount, 2)


def calculate_signals(current_price, fair_value, mos_price):
    """
    Calculate BUY/SELL signals based on Excel logic:
    - SELL: Current Price > 1.2 × Fair Value
    - BUY: MOS Price ≥ 0.85 × Current Price
    - HOLD: Neither condition met
    """
    sell_signal = current_price > 1.2 * fair_value
    buy_signal = mos_price >= 0.85 * current_price
    
    if buy_signal:
        return 'BUY'
    elif sell_signal:
        return 'SELL'
    else:
        return 'HOLD'


def calculate_sector_valuation(sector_key, yearly_data, current_price, current_pe):
    """
    Complete valuation calculation for a sector.
    
    Args:
        sector_key: Key in SECTOR_CONFIG
        yearly_data: List of dicts with 'year', 'close', 'pe', 'eps'
        current_price: Current index price (May 2026)
        current_pe: Current P/E ratio (May 2026)
    
    Returns:
        Dictionary with all valuation metrics
    """
    config = SECTOR_CONFIG[sector_key]
    
    # Step 1: Calculate base EPS
    base_eps = calculate_base_eps(yearly_data)
    
    # Step 2: Project EPS forward
    projected_eps = calculate_projected_eps(base_eps)
    
    # Step 3: Calculate fair value
    fair_value = calculate_fair_value(projected_eps, config['avgPe'])
    
    # Step 4: Calculate MOS
    mos_price = calculate_mos(fair_value)
    
    # Step 5: Calculate signals
    signal = calculate_signals(current_price, fair_value, mos_price)
    
    # Calculate percentage differences
    diff_vs_fair = round((current_price - fair_value) / fair_value * 100, 1)
    diff_vs_mos = round((current_price - mos_price) / mos_price * 100, 1)
    
    return {
        'sector': config['label'],
        'current_price': current_price,
        'current_pe': current_pe,
        'avg_pe': config['avgPe'],
        'base_eps': base_eps,
        'base_years': BASE_YEARS,
        'projected_eps': projected_eps,
        'fv_years': FV_YEARS,
        'fair_value': fair_value,
        'mos_price': mos_price,
        'signal': signal,
        'diff_vs_fair_pct': diff_vs_fair,
        'diff_vs_mos_pct': diff_vs_mos,
        'sell_threshold': round(fair_value * 1.2, 2),
        'buy_threshold': round(mos_price / 0.85, 2),
    }


# ============================================================================
# DATA EXTRACTION FROM EXCEL
# ============================================================================

def extract_daily_data_from_excel(excel_path, sheet_name):
    """
    Extract daily OHLC + PE data from Excel sheet.
    Columns: B=Date, F=Close, I=PE
    """
    wb = load_workbook(excel_path, data_only=True)
    ws = wb[sheet_name]
    
    daily_data = {}
    for row_idx in range(2, 4000):  # Start from row 2, go till data ends
        date_val = ws.cell(row_idx, 2).value  # Column B
        close_val = ws.cell(row_idx, 6).value  # Column F
        pe_val = ws.cell(row_idx, 9).value     # Column I
        
        if date_val is None:
            break
        
        if close_val and pe_val:
            try:
                date_str = str(date_val)[:10]
                close_float = float(str(close_val))
                pe_float = float(str(pe_val).replace(',', ''))
                daily_data[date_str] = (close_float, pe_float)
            except:
                continue
    
    return daily_data


def build_yearly_snapshots(daily_data, anchor_date, years_back=10):
    """
    Build yearly snapshots using VLOOKUP logic.
    For each year going back from anchor_date, find price + PE on same calendar date.
    """
    yearly = []
    
    if isinstance(anchor_date, datetime):
        anchor = anchor_date.date()
    else:
        anchor = anchor_date
    
    for yr_back in range(years_back + 1):
        target_year = anchor.year - yr_back
        
        # Try to find data on same month/day
        try:
            target_date = anchor.replace(year=target_year)
        except ValueError:
            # Handle leap year edge case (Feb 29)
            target_date = anchor.replace(year=target_year, day=28)
        
        # Search within ±7 days for the nearest trading day
        found = None
        for offset in range(-7, 8):
            try:
                check_date = target_date + timedelta(days=offset)
                date_key = str(check_date)
                if date_key in daily_data:
                    found = (date_key, daily_data[date_key][0], daily_data[date_key][1])
                    break
            except:
                continue
        
        if found:
            date_str, close, pe = found
            eps = calculate_eps(close, pe)
            is_covid = target_year in [2020, 2021]
            
            yearly.append({
                'year': target_year,
                'date': date_str,
                'close': close,
                'pe': round(pe, 2),
                'eps': eps,
                'covid': is_covid
            })
    
    return yearly


def load_sector_from_excel(excel_path, sector_key):
    """
    Load complete sector data from Excel file.
    """
    config = SECTOR_CONFIG[sector_key]
    sheet_name = config['sheet_name']
    
    # Extract daily data
    daily_data = extract_daily_data_from_excel(excel_path, sheet_name)
    
    # Get anchor date (latest date in data)
    wb = load_workbook(excel_path, data_only=True)
    ws = wb[sheet_name]
    anchor_date = ws.cell(2, 2).value  # B2
    
    # Build yearly snapshots
    yearly_data = build_yearly_snapshots(daily_data, anchor_date)
    
    # Get latest price and PE from Excel
    latest_close = float(str(ws.cell(2, 6).value))
    latest_pe = float(str(ws.cell(2, 9).value))
    
    return yearly_data, latest_close, latest_pe


# ============================================================================
# CONVENIENCE FUNCTION FOR UPDATED CURRENT PRICES
# ============================================================================

def calculate_with_updated_prices(excel_path, current_prices_2026):
    """
    Calculate valuations with updated current prices.
    
    Args:
        excel_path: Path to your Excel file
        current_prices_2026: Dict like {'Nifty': (24176.2, 21.00), ...}
                            where tuple is (close_price, pe_ratio)
    
    Returns:
        Dictionary with valuation results for all sectors
    """
    results = {}
    
    for sector_key in SECTOR_CONFIG.keys():
        # Load historical data from Excel
        yearly_data, excel_close, excel_pe = load_sector_from_excel(excel_path, sector_key)
        
        # Use updated prices if provided, otherwise use Excel prices
        if sector_key in current_prices_2026:
            current_price, current_pe = current_prices_2026[sector_key]
            
            # Add 2026 row to yearly data
            eps_2026 = calculate_eps(current_price, current_pe)
            yearly_data.insert(0, {
                'year': 2026,
                'date': '2026-05-08',
                'close': current_price,
                'pe': current_pe,
                'eps': eps_2026,
                'covid': False
            })
        else:
            current_price, current_pe = excel_close, excel_pe
        
        # Calculate valuation
        valuation = calculate_sector_valuation(
            sector_key, 
            yearly_data, 
            current_price, 
            current_pe
        )
        
        results[sector_key] = valuation
    
    return results


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def print_valuation_summary(results):
    """Print formatted summary of all sector valuations."""
    print("\n" + "="*100)
    print("NSE SECTOR VALUATION SUMMARY — MAY 2026")
    print("="*100)
    print(f"Base: avg(EPS_2016, EPS_2017, EPS_2018) | FV: 9 years @ 15% CAGR | MOS: 35% discount")
    print("="*100)
    print()
    
    # Create DataFrame for nice formatting
    data = []
    for sector_key, val in results.items():
        data.append({
            'Sector': val['sector'],
            'Current': f"₹{val['current_price']:,.0f}",
            'P/E': f"{val['current_pe']:.2f}×",
            'Base EPS': f"₹{val['base_eps']:,.0f}",
            'Proj EPS': f"₹{val['projected_eps']:,.0f}",
            'Fair Value': f"₹{val['fair_value']:,.0f}",
            'MOS': f"₹{val['mos_price']:,.0f}",
            'vs Fair': f"{val['diff_vs_fair_pct']:+.1f}%",
            'Signal': val['signal']
        })
    
    df = pd.DataFrame(data)
    print(df.to_string(index=False))
    print()
    
    # Buy signals
    buy_sectors = [v['sector'] for v in results.values() if v['signal'] == 'BUY']
    if buy_sectors:
        print(f"✓ BUY SIGNALS ({len(buy_sectors)}): {', '.join(buy_sectors)}")
    
    sell_sectors = [v['sector'] for v in results.values() if v['signal'] == 'SELL']
    if sell_sectors:
        print(f"✗ SELL SIGNALS ({len(sell_sectors)}): {', '.join(sell_sectors)}")
    
    print("="*100)
    print()


def export_to_excel(results, output_path='valuation_results.xlsx'):
    """Export results to Excel."""
    data = []
    for sector_key, val in results.items():
        data.append({
            'Sector': val['sector'],
            'Current Price': val['current_price'],
            'Current P/E': val['current_pe'],
            'Avg P/E': val['avg_pe'],
            'Base EPS': val['base_eps'],
            'Projected EPS': val['projected_eps'],
            'Fair Value': val['fair_value'],
            'MOS Price': val['mos_price'],
            'vs Fair Value %': val['diff_vs_fair_pct'],
            'vs MOS %': val['diff_vs_mos_pct'],
            'Signal': val['signal'],
            'Sell Threshold': val['sell_threshold'],
            'Buy Threshold': val['buy_threshold'],
        })
    
    df = pd.DataFrame(data)
    df.to_excel(output_path, index=False, sheet_name='Valuation')
    print(f"✓ Results exported to {output_path}")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    
    # Path to your Excel file
    EXCEL_FILE = '/home/fa064034/Documents/Learnings/GenAI/marketAI/Sectoral-Testing.xlsx'
    
    # Current prices as of May 2026 (from NSE / web search)
    CURRENT_PRICES_MAY_2026 = {
        'Nifty':    (24176.2, 21.00),
        'Bank':     (54547.1, 13.96),
        'IT':       (31200.0, 19.96),
        'Auto':     (22100.0, 30.58),
        'FMCG':     (51266.0, 36.03),
        'PHARMA':   (21500.0, 35.97),
        'Finance':  (25340.0, 17.50),
        'Metal':    (8420.0,  22.40),
        'Energy':   (35800.0, 15.20),
        'pvtBank':  (26495.5, 14.20),
        'INFRA':    (8180.0,  21.85),
    }
    
    # Calculate valuations
    print("Loading data from Excel and calculating valuations...")
    results = calculate_with_updated_prices(EXCEL_FILE, CURRENT_PRICES_MAY_2026)
    
    # Print summary
    print_valuation_summary(results)
    
    # Export to Excel
    export_to_excel(results, 'nse_valuation_may2026.xlsx')
    
    
    # ========================================================================
    # EXAMPLE: Calculate for single sector with custom parameters
    # ========================================================================
    
    print("\n" + "="*100)
    print("EXAMPLE: Custom calculation for Nifty IT with different parameters")
    print("="*100)
    
    # Load IT data
    it_yearly, it_close, it_pe = load_sector_from_excel(EXCEL_FILE, 'IT')
    
    # Calculate with custom parameters
    custom_valuation = calculate_sector_valuation(
        'IT',
        it_yearly,
        current_price=30000,  # Test price
        current_pe=19.96
    )
    
    print(f"\nSector: {custom_valuation['sector']}")
    print(f"Test Price: ₹{custom_valuation['current_price']:,}")
    print(f"Base EPS (avg 2016-2018): ₹{custom_valuation['base_eps']:,}")
    print(f"Projected EPS (9yr @ 15%): ₹{custom_valuation['projected_eps']:,}")
    print(f"Fair Value: ₹{custom_valuation['fair_value']:,}")
    print(f"MOS Price: ₹{custom_valuation['mos_price']:,}")
    print(f"Signal: {custom_valuation['signal']}")
    print()
