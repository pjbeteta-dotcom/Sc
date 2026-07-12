import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# ---------------------------------------------------------
# CONFIGURACIÓN STREAMLIT
# ---------------------------------------------------------
st.set_page_config(page_title="Screener Avanzado", layout="wide")
st.title("Screener Avanzado de Acciones")
st.caption("Versión estable para Streamlit Cloud – PMV funcional")

# ---------------------------------------------------------
# LISTA DE TICKERS (puedes ampliar)
# ---------------------------------------------------------
DEFAULT_TICKERS = [
    "NVDA", "AMD", "AVGO", "SMCI", "MCHP", "ON", "GE", "ETN", "HUBB",
    "META", "MSFT", "AAPL", "TSLA"
]

# ---------------------------------------------------------
# FUNCIONES DE DATOS
# ---------------------------------------------------------
def get_price_data(ticker):
    try:
        df = yf.download(ticker, period="1y", progress=False)
        if df.empty:
            return None

        df["SMA150"] = df["Close"].rolling(150).mean()
        df["SMA200"] = df["Close"].rolling(200).mean()
        df["Returns"] = df["Close"].pct_change()
        return df
    except:
        return None


def get_fundamentals(ticker):
    try:
        info = yf.Ticker(ticker).info
    except:
        return None

    return {
        "market_cap": info.get("marketCap"),
        "sector": info.get("sector", "N/A"),
        "country": info.get("country", "N/A"),
        "eps_ttm": info.get("trailingEps", None),
        "revenue_growth": info.get("revenueGrowth", None),
    }


# ---------------------------------------------------------
# FILTROS TÉCNICOS
# ---------------------------------------------------------
def filtros_tecnicos(df):
    last = df.iloc[-1]

    cond_sma = (
        last["Close"] > last["SMA150"]
        and last["Close"] > last["SMA200"]
    )

    max_52w = df["Close"].tail(252).max()
    distance_high = (max_52w - last["Close"]) / max_52w if max_52w else 1
    cond_distance = distance_high < 0.25

    if len(df) >= 120:
        last_60 = df["Returns"].tail(60).std()
        prev_60 = df["Returns"].tail(120).head(60).std()
        base_3m = last_60 < prev_60
    else:
        base_3m = False

    avg_vol_50 = df["Volume"].tail(50).mean()
    up_days = df[(df["Close"] > df["Open"]) & (df["Volume"] > 1.5 * avg_vol_50)]
    down_days = df[(df["Close"] < df["Open"]) & (df["Volume"] < avg_vol_50)]

    vol_up = len(up_days) > 0
    vol_down = len(down_days) > 0

    return {
        "cond_sma": cond_sma,
        "distance_high": distance_high,
        "cond_distance": cond_distance,
        "base_3m": base_3m,
        "vol_up": vol_up,
        "vol_down": vol_down,
    }


# ---------------------------------------------------------
# SCORE
# ---------------------------------------------------------
PRIORITY_SECTORS = [
    "Industrials", "Semiconductors", "Technology", "Energy", "Utilities"
]

def compute_score(fund, tech):
    score = 0

    if fund["revenue_growth"] and fund["revenue_growth"] > 0.10:
        score += 10
    if fund["eps_ttm"] and fund["eps_ttm"] > 0:
        score += 10

    if tech["cond_sma"]:
        score += 10
    if tech["cond_distance"]:
        score += 10
    if tech["base_3m"]:
        score += 10
    if tech["vol_up"] and tech["vol_down"]:
        score += 5

    if any(s in (fund["sector"] or "") for s in PRIORITY_SECTORS):
        score += 10

    return score


# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------
st.sidebar.header("Parámetros del Screener")

tickers_input = st.sidebar.text_area(
    "Tickers (separados por comas)",
    value=", ".join(DEFAULT_TICKERS)
)

tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

run = st.sidebar.button("Ejecutar Screener")


# ---------------------------------------------------------
# EJECUCIÓN
# ---------------------------------------------------------
if run:
    st.subheader("Resultados del Screener")

    rows = []
    progress = st.progress(0.0)

    for i, ticker in enumerate(tickers, start=1):
        progress.progress(i / len(tickers))

        df = get_price_data(ticker)
        if df is None:
            continue

        fund = get_fundamentals(ticker)
        if fund is None:
            continue

        if fund["country"] != "United States":
            continue

        if not fund["market_cap"] or not (2e9 <= fund["market_cap"] <= 50e9):
            continue

        tech = filtros_tecnicos(df)
        score = compute_score(fund, tech)

        last = df.iloc[-1]

        rows.append({
            "Empresa": yf.Ticker(ticker).info.get("shortName", ticker),
            "Ticker": ticker,
            "Sector": fund["sector"],
            "Market Cap": fund["market_cap"],
            "Ventas YoY (aprox)": fund["revenue_growth"],
            "EPS TTM": fund["eps_ttm"],
            "Precio > SMA150/200": tech["cond_sma"],
            "Base 3m vol↓": tech["base_3m"],
            "Dist. Máx (%)": round(tech["distance_high"] * 100, 2),
            "Vol. subidas >1.5x": tech["vol_up"],
            "Vol. caídas bajo": tech["vol_down"],
            "Precio actual": round(last["Close"], 2),
            "Score": score,
        })

    if rows:
        df_res = pd.DataFrame(rows).sort_values("Score", ascending=False)
        st.dataframe(df_res, use_container_width=True)
        st.success("Screener ejecutado correctamente")
    else:
        st.warning("No se encontraron empresas que cumplan los criterios.")

else:
    st.info("Pulsa 'Ejecutar Screener' para comenzar.")
