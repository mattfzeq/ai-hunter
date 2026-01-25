import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import re
from openai import OpenAI
from curl_cffi import requests as cf # La nouvelle arme secrète
import yfinance as yf

# ============================================================================
# 0. CONFIG & CHARGEMENT
# ============================================================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

st.set_page_config(page_title="AI Hunter V22 Stealth", page_icon="🦅", layout="wide")

# CSS Bloomberg Style
st.markdown("""
<style>
    .stApp { background-color: #0a0e27; color: #00ff41; }
    .main { background-color: #0a0e27; }
    h1, h2, h3 { color: #00ff41; font-family: 'Courier New', monospace; }
    div[data-testid="stMetricValue"] { color: #00ff41 !important; font-size: 1.6rem !important; }
    div[data-testid="stMetricLabel"] { color: #888888 !important; }
    .stMetric { background-color: #1a1f3a; padding: 15px; border-radius: 5px; border: 1px solid #00ff41; }
    .macro-banner {
        background: linear-gradient(90deg, #1a1f3a 0%, #2a2f4a 100%);
        padding: 15px; border-radius: 8px; border: 1px solid #00ff41;
        margin-bottom: 20px; font-family: 'Courier New', monospace; color: #00ff41;
    }
    .verdict-box {
        padding: 15px; border-radius: 8px; font-size: 20px; font-weight: bold;
        text-align: center; margin-bottom: 10px; border: 2px solid;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# DATA ENGINE: STEALTH MODE (CURL_CFFI)
# ============================================================================

def get_data_stealth(ticker):
    """
    Utilise curl_cffi pour imiter un vrai navigateur Chrome (TLS Fingerprint)
    et scraper les données brutes si l'API officielle est bloquée.
    """
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}"
        
        # L'imitation parfaite d'un navigateur
        session = cf.Session(impersonate="chrome110")
        response = session.get(url, timeout=10)
        
        if response.status_code != 200:
            return None
            
        html = response.text
        
        # Extraction Regex (Brute mais efficace quand l'API est bloquée)
        # On cherche le prix dans le HTML
        price_match = re.search(r'"regularMarketPrice":{"raw":([\d.]+)', html)
        price = float(price_match.group(1)) if price_match else 0.0
        
        if price == 0.0:
            # Fallback: cherche une autre structure courante
            price_match = re.search(r'fin-streamer.+?data-field="regularMarketPrice".+?value="([\d.]+)"', html)
            price = float(price_match.group(1)) if price_match else 0.0

        # Extraction Market Cap
        mcap_match = re.search(r'"marketCap":{"raw":([\d.]+)', html)
        mcap = float(mcap_match.group(1)) if mcap_match else 0.0
        
        # Extraction PE
        pe_match = re.search(r'"trailingPE":{"raw":([\d.]+)', html)
        pe = float(pe_match.group(1)) if pe_match else 0.0
        
        # Extraction Beta
        beta_match = re.search(r'"beta":{"raw":([\d.]+)', html)
        beta = float(beta_match.group(1)) if beta_match else 1.0

        # Extraction Dette (Total Debt)
        debt_match = re.search(r'"totalDebt":{"raw":([\d.]+)', html)
        debt = float(debt_match.group(1)) if debt_match else 0.0

        # Si on a au moins le prix, c'est une victoire
        if price > 0:
            return {
                'ticker': ticker,
                'current_price': price,
                'market_cap': mcap,
                'trailing_pe': pe,
                'beta': beta,
                'total_debt': debt,
                'free_cashflow': 0, # Difficile à scraper en regex simple
                'revenue_growth': 0,
                'trend_6m': 0, # Pas d'historique en mode stealth simple
                'history': pd.DataFrame(),
                'has_history': False,
                'source': 'STEALTH_MODE (REAL DATA)'
            }
        return None

    except Exception as e:
        print(f"Stealth Error: {e}")
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(ticker):
    # 1. TENTATIVE VIA YFINANCE (API)
    try:
        stock = yf.Ticker(ticker)
        # On essaie de récupérer le prix rapidement
        price = stock.fast_info.last_price
        
        # Si on arrive ici, l'IP n'est pas totalement bannie
        hist = stock.history(period="6mo")
        trend_6m = 0
        if not hist.empty:
            start = hist['Close'].iloc[0]
            end = hist['Close'].iloc[-1]
            trend_6m = ((end - start) / start) * 100
        
        info = stock.info
        return {
            'ticker': ticker,
            'current_price': price,
            'market_cap': info.get('marketCap', 0),
            'trailing_pe': info.get('trailingPE', 0),
            'beta': info.get('beta', 1.0),
            'total_debt': info.get('totalDebt', 0),
            'free_cashflow': info.get('freeCashflow', 0),
            'revenue_growth': info.get('revenueGrowth', 0),
            'trend_6m': trend_6m,
            'history': hist,
            'has_history': not hist.empty,
            'source': 'API_STANDARD'
        }
    except:
        # 2. ECHEC API -> PASSAGE EN MODE FURTIF (CURL_CFFI)
        print(f"⚠️ API Bloquée pour {ticker}. Activation Stealth Mode.")
        stealth_data = get_data_stealth(ticker)
        if stealth_data:
            return stealth_data
        
        return None

# ============================================================================
# AI BRAIN
# ============================================================================

def analyze_with_ai(persona, stock_data):
    try:
        api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
        if not api_key: return {'verdict': 'ERROR', 'score': 0, 'thesis': 'Clé manquante', 'risk': 'HIGH'}
        
        client = OpenAI(api_key=api_key)
        
        logic_matrix = """
        RÈGLE IMPÉRATIVE DE COHÉRENCE :
        - Score < 45 -> SELL
        - Score 46-65 -> HOLD
        - Score > 66 -> BUY
        """
        
        prompt = f"Tu es {persona}. Analyse ce titre (Données réelles). {logic_matrix} Réponds en JSON."
        
        # Préparation des données pour le prompt
        debt_str = f"${stock_data['total_debt']/1e9:.1f}B" if stock_data['total_debt'] else "N/A"
        pe_str = f"{stock_data['trailing_pe']:.1f}" if stock_data['trailing_pe'] else "N/A"
        
        user_message = f"""
        TICKER: {stock_data['ticker']}
        PRIX: ${stock_data['current_price']:.2f}
        PE: {pe_str}
        DETTE: {debt_str}
        BETA: {stock_data['beta']}
        SOURCE: {stock_data['source']} (Si Stealth, données fondamentales réduites)
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_message}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {'verdict': 'ERROR', 'score': 0, 'thesis': str(e), 'risk': 'HIGH'}

# ============================================================================
# UI MAIN
# ============================================================================

def main():
    st.title("🦅 AI HUNTER V22 STEALTH")
    st.markdown("*Moteur Hybride : yFinance + curl_cffi (Anti-Blocage)*")
    
    # Macro Banner
    st.markdown('<div class="macro-banner">📈 MARKET | S&P500: +0.4% | BTC: $98k | VIX: 13.5</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1: ticker = st.text_input("Ticker", "NVDA").upper().strip()
    with col2: btn = st.button("🚀 ANALYZE", type="primary", use_container_width=True)
    
    if btn and ticker:
        with st.spinner(f"Infiltration des données pour {ticker}..."):
            data = fetch_stock_data(ticker)
            
        if not data:
            st.error("❌ Échec total. Yahoo a blindé ses portes, même pour le mode furtif.")
            return

        # Affichage des résultats
        st.markdown("---")
        st.subheader(f"{ticker} : ${data['current_price']:.2f}")
        
        if data['source'] == 'STEALTH_MODE (REAL DATA)':
            st.warning("⚠️ Mode Furtif Activé : Données réelles extraites, mais graphique historique non disponible.")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("PE Ratio", f"{data['trailing_pe']:.1f}" if data['trailing_pe'] else "N/A")
        c2.metric("Dette", f"${data['total_debt']/1e9:.1f}B" if data['total_debt'] else "N/A")
        c3.metric("Beta", f"{data['beta']:.2f}")
        c4.metric("Source", data['source'])

        if data['has_history']:
            st.area_chart(data['history']['Close'], color="#00ff41")
            
        # AI Analysis
        st.markdown("---")
        cols = st.columns(3)
        for i, p in enumerate(["Warren", "Cathie", "Jim"]):
            with cols[i]:
                st.subheader(p)
                res = analyze_with_ai(p, data)
                
                # Couleur Verdict
                color = "#00ff41" if "BUY" in res['verdict'] else "#ff4136" if "SELL" in res['verdict'] else "#ffdc00"
                st.markdown(f'<div class="verdict-box" style="color:{color}; border-color:{color}">{res["verdict"]} ({res["score"]})</div>', unsafe_allow_html=True)
                st.info(res['thesis'])

if __name__ == "__main__":
    main()