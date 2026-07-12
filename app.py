import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Screener USA", layout="wide")
st.title("Screener USA – Criterios fundamentales avanzados")

# ============================================================
# TICKERS (reducido para evitar bloqueos)
# ============================================================
TICKERS = ["AAPL", "MSFT", "AMZN", "GOOGL", "META"]

# ============================================================
# PARÁMETROS
# ============================================================
min_mcap = 2_000_000_000
max_mcap = 50_000_000_000

# ============================================================
# FUNCIONES
# ============================================================
def get_info(ticker):
    try:
        return yf.Ticker(ticker).info
    except:
        return None

# ============================================================
# SCREENER
# ============================================================
results = []
progress = st.progress(0)
total = len(TICKERS)

for i, ticker in enumerate(TICKERS):
    progress.progress((i + 1) / total)

    info = get_info(ticker)
    if not info:
        continue

    # 1. USA
    if info.get("country", "") != "United States":
        continue

    # 2. Market cap
    mcap = info.get("marketCap", None)
    if mcap is None or not (min_mcap <= mcap <= max_mcap):
        continue

    # 3. Revenue YoY > 20 %
    rev_growth = info.get("revenueGrowth", None)
    if rev_growth is None or rev_growth < 0.20:
        continue

    # 4. EPS positivo
    eps = info.get("trailingEps", None)
    if eps is None or eps <= 0:
        continue

    # ============================================================
    # CAMPOS AVANZADOS (NO DISPONIBLES EN YFINANCE)
    # ============================================================
    margin_expansion = "Requiere API (no disponible en yfinance)"
    roic_trend = "Requiere API (no disponible en yfinance)"
    funds_trend = "Requiere API (no disponible en yfinance)"
    guidance_trend = "Requiere API (no disponible en yfinance)"

    results.append({
        "Ticker": ticker,
        "Name": info.get("shortName", ""),
        "MarketCap": mcap,
        "RevenueGrowth": rev_growth,
        "EPS_ttm": eps,
        "MarginExpansion": margin_expansion,
        "ROIC_trend": roic_trend,
        "Funds_trend": funds_trend,
        "Guidance_trend": guidance_trend
    })

df = pd.DataFrame(results)

# ============================================================
# RESULTADOS
# ============================================================
st.subheader("Resultados del screener")

if df.empty:
    st.warning("No se encontraron acciones que cumplan los criterios.")
else:
    st.dataframe(df)
