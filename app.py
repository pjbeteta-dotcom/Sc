import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3

# ============================================================
# CONFIG STREAMLIT
# ============================================================
st.set_page_config(page_title="Screener USA", layout="wide")
st.title("Screener USA – Versión con criterios fundamentales + feedback")

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

    # 2. Market cap 2B–50B
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
    margin_expansion = "Requiere API"
    roic_trend = "Requiere API"
    funds_trend = "Requiere API"
    guidance_trend = "Requiere API"

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
