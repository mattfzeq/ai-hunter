import streamlit as st
import os
import time
import yfinance as yf
from openai import OpenAI
import json
import pandas as pd
import random
import datetime

# --- 1. CONFIGURATION TERMINAL ---
st.set_page_config(
    layout="wide", 
    page_title="AI Strategic Hunter v14",
    page_icon="🦅",
    initial_sidebar_state="expanded"
)

# --- CSS PRO ---
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 5rem;}
    div[data-testid="stMetricValue"] {font-size: 1.4rem !important;}
    .stCard {background-color: #0e1117; border: 1px solid #303030;}
    /* Style pour le bouton de téléchargement pour le rendre plus visible */
    div[data-testid="stDownloadButton"] button {
        width: 100%;
        border-color: #4CAF50;
        color: #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# --- SÉCURITÉ ---
if "password_correct" not in st.session_state:
    st.session_state.password_correct = False

def check_password():
    if st.session_state.password_correct: return True
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.subheader("🔒 Terminal Access")
        pwd = st.text_input("Password", type="password")
        if st.button("Connect"):
            if pwd == os.getenv("APP_PASSWORD", "admin123"):
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Access Denied")
    return False

if not check_password(): st.stop()

# --- INIT API ---
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

# --- 2. MOTEUR DE DONNÉES ---

def generate_rich_mock_data(ticker):
    """Données de simulation riches"""
    base = random.uniform(50, 800)
    prices = [base]
    for _ in range(50): prices.append(prices[-1] * random.uniform(0.98, 1.02))
    
    micro = {
        "Market Cap": f"{random.uniform(50, 2000):.1f}B",
        "PE Ratio": f"{random.uniform(15, 80):.1f}",
        "PEG": f"{random.uniform(0.8, 3.0):.2f}",
        "EPS": f"{random.uniform(2, 15):.2f}",
        "Div Yield": f"{random.uniform(0, 4):.2f}%",
        "Beta": f"{random.uniform(0.8, 2.5):.2f}",
        "Profit Margin": f"{random.uniform(10, 40):.1f}%",
        "Revenue YoY": f"+{random.uniform(5, 50):.1f}%"
    }
    
    return {
        "Ticker": ticker,
        "Prix": prices[-1],
        "Change": (prices[-1] - prices[0]) / prices[0] * 100,
        "History": pd.DataFrame({"Close": prices}),
        "Sector": "Technology (Simulated)",
        "Micro": micro,
        "Score": random.randint(40, 95),
        "Verdict": "ACHAT (SIMULÉ)",
        "Thesis": f"Simulation : {ticker} présente une opportunité technique intéressante dans un contexte de volatilité maîtrisée.",
        "Risque": "Volatilité API",
        "Source": "⚠️ Simulation"
    }

@st.cache_data(ttl=600)
def analyze_stock_pro(ticker):
    ticker = ticker.strip().upper()
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")
        info = stock.info
        
        if hist.empty: raise Exception("Yahoo Empty")
        
        current = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[0]
        change = ((current - prev) / prev) * 100
        
        micro = {
            "Market Cap": f"{info.get('marketCap', 0)/1e9:.1f}B",
            "PE Ratio": f"{info.get('trailingPE', 0):.1f}",
            "PEG": f"{info.get('pegRatio', 0):.2f}",
            "EPS": f"{info.get('trailingEps', 0):.2f}",
            "Div Yield": f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "0%",
            "Beta": f"{info.get('beta', 0):.2f}",
            "Profit Margin": f"{info.get('profitMargins', 0)*100:.1f}%",
            "Revenue YoY": f"{info.get('revenueGrowth', 0)*100:.1f}%"
        }
        
        try:
            if not client: raise Exception("No Key")
            prompt = f"Analyse flash {ticker}. Prix {current}. Secteur {info.get('sector')}. Output JSON: {{'verdict': 'BUY/HOLD/SELL', 'score': 75, 'thesis': '1 phrase', 'risk': '1 mot'}}"
            response = client.chat.completions.create(
                model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}]
            )
            ai_data = json.loads(response.choices[0].message.content)
            verdict = ai_data.get('verdict')
            thesis = ai_data.get('thesis')
            score = ai_data.get('score')
            risk = ai_data.get('risk')
            source = "✅ Données Réelles"
        except:
            verdict = "NEUTRE"
            thesis = "Analyse technique seule (IA indisponible)."
            score = 50
            risk = "N/A"
            source = "⚠️ Yahoo (No IA)"

        return {
            "Ticker": ticker, "Prix": current, "Change": change,
            "History": hist, "Sector": info.get('sector', 'N/A'),
            "Micro": micro, "Score": score, "Verdict": verdict,
            "Thesis": thesis, "Risque": risk, "Source": source
        }

    except Exception:
        return generate_rich_mock_data(ticker)

# --- 3. INTERFACE TERMINAL ---

# BANDEAU
col_t1, col_t2, col_t3, col_t4 = st.columns(4)
with col_t1: st.metric("S&P 500", "4,890.23", "+0.45%")
with col_t2: st.metric("NASDAQ", "15,450.10", "+0.80%")
with col_t3: st.metric("EUR/USD", "1.0850", "-0.12%")
with col_t4: st.metric("BTC/USD", "64,230.00", "+2.40%")
st.divider()

# SIDEBAR (Contrôles)
with st.sidebar:
    st.title("🦅 HUNTER V14")
    st.caption("Agency Edition")
    
    input_tickers = st.text_area("Watchlist", "NVDA PLTR AMD")
    tickers = [t.strip() for t in input_tickers.replace(',',' ').split() if t.strip()]
    
    st.markdown("---")
    run_btn = st.button("RUN ANALYSIS 🚀", type="primary", use_container_width=True)
    
    # Placeholder pour le bouton d'export (il apparaîtra après l'analyse)
    export_placeholder = st.empty()

# MAIN CONTENT
if run_btn and tickers:
    report_data = [] # Liste pour stocker les données pour le CSV
    
    for t in tickers:
        data = analyze_stock_pro(t)
        
        # CARD DESIGN
        with st.container(border=True):
            c_head1, c_head2, c_head3 = st.columns([2, 4, 2])
            with c_head1:
                st.markdown(f"## {data['Ticker']}")
                st.caption(data['Sector'])
            with c_head2:
                delta_color = "normal" if data['Change'] > 0 else "inverse"
                st.metric("Prix Actuel", f"{data['Prix']:.2f} $", f"{data['Change']:.2f} %", delta_color=delta_color)
            with c_head3:
                st.metric("AI Score", f"{data['Score']}/100", data['Verdict'])

            st.markdown("#### 🔢 Key Financials")
            m = data['Micro']
            k1, k2, k3, k4 = st.columns(4)
            with k1: st.write(f"**Mkt Cap:** {m.get('Market Cap')}"); st.write(f"**Beta:** {m.get('Beta')}")
            with k2: st.write(f"**PE:** {m.get('PE Ratio')}"); st.write(f"**EPS:** {m.get('EPS')}")
            with k3: st.write(f"**Margin:** {m.get('Profit Margin')}"); st.write(f"**Rev:** {m.get('Revenue YoY')}")
            with k4: st.write(f"**PEG:** {m.get('PEG')}"); st.write(f"**Yield:** {m.get('Div Yield')}")

            st.markdown("---")
            g1, g2 = st.columns([2, 1])
            with g1: st.area_chart(data['History']['Close'], height=200, color="#29b5e8")
            with g2:
                st.info(data['Thesis'])
                st.write(f"**Risque:** {data['Risque']}")
                if "Simulation" in data['Source']: st.caption("⚠️ Simulation Mode")

        # Ajout des données au rapport CSV
        report_data.append({
            "Ticker": t,
            "Price": f"{data['Prix']:.2f}",
            "Change %": f"{data['Change']:.2f}",
            "Verdict": data['Verdict'],
            "Score": data['Score'],
            "Thesis": data['Thesis'],
            "PE Ratio": data['Micro'].get('PE Ratio'),
            "Source": data['Source']
        })

    # --- GÉNÉRATION DU RAPPORT (SIDEBAR) ---
    if report_data:
        df = pd.DataFrame(report_data)
        csv = df.to_csv(index=False).encode('utf-8')
        
        # On injecte le bouton dans la sidebar via le placeholder
        with export_placeholder.container():
            st.success("✅ Analyse Terminée")
            st.download_button(
                label="📥 TÉLÉCHARGER RAPPORT (CSV)",
                data=csv,
                file_name=f"Hunter_Report_{datetime.date.today()}.csv",
                mime="text/csv",
            )
            
            st.markdown("---")
            st.markdown("**📧 Email Briefing:**")
            st.code(f"Analyse terminée sur {len(tickers)} actifs. Tendance globale: {'Haussière' if df['Change %'].astype(float).mean() > 0 else 'Mixte'}. Top pick: {df.loc[df['Score'].idxmax()]['Ticker']}.", language="text")