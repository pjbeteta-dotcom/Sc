import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta

# ============================================================
# CONFIGURACIÓN STREAMLIT
# ============================================================
st.set_page_config(page_title="Screener avanzado USA", layout="wide")
st.title("Screener avanzado USA – Versión estable con feedback")

# ============================================================
# BASE DE DATOS (SQLite)
# ============================================================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    category TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

def save_feedback(message, category):
    cursor.execute("""
        INSERT INTO feedback (message, category)
        VALUES (?, ?)
    """, (message, category))
    conn.commit()

# ============================================================
# LISTA DE TICKERS (S&P 500 resumido)
# Puedes sustituir por la lista completa si quieres
# ============================================================
TICKERS_SP500 = [
    "AAPL","MSFT","AMZN","GOOGL","META","NVDA","TSLA","UNH","XOM","JPM",
    "V","MA","HD","PG","KO","PEP","MRK","ABBV","DIS","BAC",
    "ADBE","PFE","CSCO","COST","MCD","WMT","CVX","AVGO","NFLX","INTC"
]

# ============================================================
# PARÁMETROS DEL SCREENER
# ============================================================
min_mcap = 2_000_000_000
max_mcap = 50_000_000_000
max_dist_high = 0.25
base_months = 3
sma_short = 150
sma_long = 200

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================
@st.cache_data(ttl=3600)
def get_price_data(ticker, period="1y"):
    try:
        return yf.download(ticker, period=period, auto_adjust=True)
    except:
        return None

@st.cache_data(ttl=3600)
def get_info(ticker):
    try:
        return yf.Ticker(ticker).info
    except:
        return {}

def compute_sma(series, window):
    return series.rolling(window).mean()

def volatility_decreasing(close, window=20):
    if len(close) < 2 * window:
        return False
    recent = close[-window:]
    prev = close[-2*window:-window]
    return recent.pct_change().std() < prev.pct_change().std()

def volume_pattern(data):
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

# ============================================================
# SCREENER
# ============================================================
results = []
progress = st.progress(0)
total = len(TICKERS_SP500)

for i, ticker in enumerate(TICKERS_SP500):
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

    # 3. Ventas YoY > 10 %
    rev_growth = info.get("revenueGrowth", None)
    if rev_growth is None or rev_growth < 0.10:
        continue

    # 5. EPS positivo
    eps = info.get("trailingEps", None)
    if eps is None or eps <= 0:
        continue

    # Precio
    data = get_price_data(ticker)
    if data is None or data.empty:
        continue

    close = data["Close"]
    if len(close) < sma_long:
        continue

    # 8. Precio > SMA 150 y 200
    sma150 = compute_sma(close, sma_short)
    sma200 = compute_sma(close, sma_long)
    last_price = close.iloc[-1]

    if last_price <= sma150.iloc[-1] or last_price <= sma200.iloc[-1]:
        continue

    # 10. Distancia a máximos < 25 %
    max_1y = close.max()
    dist_high = (max_1y - last_price) / max_1y
    if dist_high > max_dist_high:
        continue

    # 9. Base con volatilidad decreciente
    base_days = base_months * 21
    if len(close) < base_days:
        continue
    if not volatility_decreasing(close[-base_days:]):
        continue

    # 11–12. Volumen
    high_vol_up, low_vol_down = volume_pattern(data)
    if not (high_vol_up and low_vol_down):
        continue

    results.append({
        "Ticker": ticker,
        "Name": info.get("shortName", ""),
        "Sector": info.get("sector", ""),
        "MarketCap": mcap,
        "RevenueGrowth": rev_growth,
        "EPS_ttm": eps,
        "Price": last_price,
        "DistMax%": round(dist_high * 100, 1),
        "HighVolUp": high_vol_up,
        "LowVolDown": low_vol_down
    })

df = pd.DataFrame(results)

# ============================================================
# RESULTADOS
# ============================================================
st.subheader("Resultados del screener")
st.dataframe(df.sort_values("DistMax%"))

# ============================================================
# BOTÓN DE FEEDBACK
# ============================================================
st.subheader("📮 ¿Quieres enviar feedback?")

if st.button("Enviar feedback"):
    with st.form("feedback_form", clear_on_submit=True):
        st.write("Tu opinión nos ayuda a mejorar el screener.")

        category = st.selectbox(
            "Tipo de feedback",
            ["Sugerencia", "Error", "Mejora", "Otro"]
        )

        message = st.text_area("Escribe tu mensaje")

        submitted = st.form_submit_button("Enviar")

        if submitted:
            if len(message.strip()) == 0:
                st.warning("El mensaje no puede estar vacío.")
            else:
                save_feedback(message, category)
                st.success("Gracias por tu feedback. Lo hemos registrado correctamente.")

# ============================================================
# PANEL ADMIN (OPCIONAL)
# ============================================================
with st.expander("📊 Ver feedback recibido (solo admin)"):
    cursor.execute("SELECT id, category, message, created_at FROM feedback ORDER BY created_at DESC")
    rows = cursor.fetchall()
    df_fb = pd.DataFrame(rows, columns=["ID", "Categoría", "Mensaje", "Fecha"])
    st.dataframe(df_fb)
