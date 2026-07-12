import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3

# ============================================================
# CONFIG STREAMLIT
# ============================================================
st.set_page_config(page_title="Screener USA (rápido)", layout="wide")
st.title("Screener avanzado USA – Versión ultrarrápida (5 acciones)")

# ============================================================
# BASE DE DATOS FEEDBACK
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
# TICKERS (solo 5 para evitar bloqueos)
# ============================================================
TICKERS = ["AAPL", "MSFT", "AMZN", "GOOGL", "META"]

# ============================================================
# PARÁMETROS
# ============================================================
min_mcap = 2_000_000_000
max_mcap = 50_000_000_000
max_dist_high = 0.25
sma_short = 50
sma_long = 100

# ============================================================
# FUNCIONES
# ============================================================
@st.cache_data(ttl=3600)
def get_price_data(ticker):
    try:
        return yf.download(ticker, period="3mo", auto_adjust=True)
    except:
        return None

@st.cache_data(ttl=3600)
def get_fast_info(ticker):
    try:
        return yf.Ticker(ticker).fast_info
    except:
        return None

def compute_sma(series, window):
    return series.rolling(window).mean()

# ============================================================
# SCREENER
# ============================================================
results = []
progress = st.progress(0)
total = len(TICKERS)

for i, ticker in enumerate(TICKERS):
    progress.progress((i + 1) / total)

    info = get_fast_info(ticker)
    if not info:
        continue

    # Market cap
    mcap = info.get("market_cap", None)
    if mcap is None or not (min_mcap <= mcap <= max_mcap):
        continue

    # Precio
    data = get_price_data(ticker)
    if data is None or data.empty:
        continue

    close = data["Close"]
    last_price = close.iloc[-1]

    # SMA
    sma50 = compute_sma(close, sma_short)
    sma100 = compute_sma(close, sma_long)

    if last_price <= sma50.iloc[-1] or last_price <= sma100.iloc[-1]:
        continue

    # Distancia a máximos
    max_3m = close.max()
    dist_high = (max_3m - last_price) / max_3m
    if dist_high > max_dist_high:
        continue

    results.append({
        "Ticker": ticker,
        "Price": last_price,
        "MarketCap": mcap,
        "DistMax%": round(dist_high * 100, 1)
    })

df = pd.DataFrame(results)

# ============================================================
# RESULTADOS
# ============================================================
st.subheader("Resultados del screener (máx 5 acciones)")
st.dataframe(df.sort_values("DistMax%"))

# ============================================================
# FEEDBACK
# ============================================================
st.subheader("📮 Enviar feedback")

if st.button("Enviar feedback"):
    with st.form("feedback_form", clear_on_submit=True):
        category = st.selectbox("Tipo de feedback", ["Sugerencia", "Error", "Mejora", "Otro"])
        message = st.text_area("Escribe tu mensaje")

        submitted = st.form_submit_button("Enviar")

        if submitted:
            if len(message.strip()) == 0:
                st.warning("El mensaje no puede estar vacío.")
            else:
                save_feedback(message, category)
                st.success("Gracias por tu feedback. Lo hemos registrado correctamente.")

# ============================================================
# PANEL ADMIN
# ============================================================
with st.expander("📊 Ver feedback recibido"):
    cursor.execute("SELECT id, category, message, created_at FROM feedback ORDER BY created_at DESC")
    rows = cursor.fetchall()
    df_fb = pd.DataFrame(rows, columns=["ID", "Categoría", "Mensaje", "Fecha"])
    st.dataframe(df_fb)
