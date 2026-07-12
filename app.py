import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Screener avanzado USA", layout="wide")

st.title("Screener avanzado (USA) – Versión factible con yfinance")

# -----------------------------
# Parámetros básicos
# -----------------------------
st.sidebar.header("Parámetros")

min_mcap = 2_000_000_000      # 2B
max_mcap = 50_000_000_000     # 50B
max_dist_high = 0.25          # 25%
base_months = 3               # base mínima
sma_short = 150
sma_long = 200

# Universo de ejemplo: S&P 500 (puedes sustituir por tu lista)
sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
tables = pd.read_html(sp500_url)
sp500 = tables[0]
tickers = sp500["Symbol"].tolist()

st.sidebar.write(f"Universo: {len(tickers)} tickers (S&P 500)")

# -----------------------------
# Funciones auxiliares
# -----------------------------
@st.cache_data(ttl=3600)
def get_price_data(ticker, period="1y"):
    try:
        data = yf.download(ticker, period=period, auto_adjust=True)
        return data
    except Exception:
        return None

@st.cache_data(ttl=3600)
def get_info(ticker):
    try:
        return yf.Ticker(ticker).info
    except Exception:
        return {}

def compute_sma(series, window):
    return series.rolling(window).mean()

def volatility_decreasing(close, window=20):
    # Compara volatilidad (std) últimos N días vs N días anteriores
    if len(close) < 2 * window:
        return False
    recent = close[-window:]
    prev = close[-2*window:-window]
    return recent.pct_change().std() < prev.pct_change().std()

def volume_pattern(data):
    # Días de subida con volumen > 1.5x media
    # Días de caída con volumen < media
    if data is None or data.empty:
        return False, False
    vol = data["Volume"]
    close = data["Close"]
    avg_vol = vol.rolling(20).mean()

    up_days = close.diff() > 0
    down_days = close.diff() < 0

    high_vol_up = (vol > 1.5 * avg_vol) & up_days
    low_vol_down = (vol < avg_vol) & down_days

    return high_vol_up.sum() > 3, low_vol_down.sum() > 3

# -----------------------------
# Screener
# -----------------------------
results = []

progress = st.progress(0)
total = len(tickers)

for i, ticker in enumerate(tickers):
    progress.progress((i + 1) / total)

    info = get_info(ticker)
    if not info:
        continue

    # 1. Cotizadas en EEUU
    country = info.get("country", "")
    if country != "United States":
        continue

    # 2. Market cap entre 2B y 50B
    mcap = info.get("marketCap", None)
    if mcap is None or mcap < min_mcap or mcap > max_mcap:
        continue

    # 3. Ventas YoY > 10 % (aprox revenueGrowth)
    rev_growth = info.get("revenueGrowth", None)
    if rev_growth is None or rev_growth < 0.10:
        continue

    # 5. EPS positivo (Diluted EPS ttm)
    eps = info.get("trailingEps", None)
    if eps is None or eps <= 0:
        continue

    # Precio y series
    data = get_price_data(ticker, period="1y")
    if data is None or data.empty:
        continue

    close = data["Close"]
    if len(close) < sma_long:
        continue

    # 8. Precio > SMA 150 y 200
    sma150 = compute_sma(close, sma_short)
    sma200 = compute_sma(close, sma_long)
    last_price = close.iloc[-1]
    last_sma150 = sma150.iloc[-1]
    last_sma200 = sma200.iloc[-1]

    if np.isnan(last_sma150) or np.isnan(last_sma200):
        continue

    if not (last_price > last_sma150 and last_price > last_sma200):
        continue

    # 10. Distancia a máximos < 25 %
    max_1y = close.max()
    dist_high = (max_1y - last_price) / max_1y
    if dist_high > max_dist_high:
        continue

    # 9. Base de al menos 3 meses con volatilidad decreciente (aprox)
    base_days = base_months * 21  # aprox días de mercado
    if len(close) < base_days:
        continue
    base_ok = volatility_decreasing(close[-base_days:])
    if not base_ok:
        continue

    # 11–12. Volumen en subidas vs caídas
    high_vol_up, low_vol_down = volume_pattern(data)
    if not (high_vol_up and low_vol_down):
        continue

    # Campos que requieren APIs avanzadas (placeholder)
    roic_trend = "Requiere API de fundamentales"
    margin_expansion = "Requiere API de fundamentales"
    funds_trend = "Requiere base de datos de fondos"
    guidance_trend = "Requiere parsing de resultados"

    results.append({
        "Ticker": ticker,
        "Name": info.get("shortName", ""),
        "Sector": info.get("sector", ""),
        "MarketCap": mcap,
        "RevenueGrowth": rev_growth,
        "EPS_ttm": eps,
        "Price": last_price,
        "DistMax": round(dist_high * 100, 1),
        "BaseOK": base_ok,
        "HighVolUp": high_vol_up,
        "LowVolDown": low_vol_down,
        "ROIC_trend": roic_trend,
        "Margin_expansion": margin_expansion,
        "Funds_trend": funds_trend,
        "Guidance_trend": guidance_trend
    })

df = pd.DataFrame(results)

st.subheader("Resultados del screener")
if df.empty:
    st.warning("No se han encontrado empresas con estos criterios. Prueba relajando alguno (por ejemplo, base o volumen).")
else:
    st.dataframe(df.sort_values("DistMax"))
