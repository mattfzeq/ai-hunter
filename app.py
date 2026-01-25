import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
import os
import json
from openai import OpenAI
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# ==================== CONFIGURATION ====================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

st.set_page_config(page_title="AI Hunter V24 Armored", page_icon="🦅", layout="wide")

# ==================== STYLES CSS ====================
st.markdown("""
<style>
    .stApp { background-color: #0a0e27; color: #00ff41; }
    .main { background-color: #0a0e27; }
    h1, h2, h3, h4, p, label, div { font-family: 'Courier New', monospace; color: #00ff41 !important; }
    div[data-testid="stMetricValue"] { color: #00ff41 !important; font-size: 1.6rem !important; }
    .stMetric { background-color: #1a1f3a; padding: 10px; border: 1px solid #00ff41; border-radius: 5px; }
    .macro-banner {
        background: linear-gradient(90deg, #1a1f3a 0%, #2a2f4a 100%);
        padding: 15px; border: 1px solid #00ff41; border-radius: 8px;
        margin-bottom: 20px; text-align: center;
    }
    .verdict-box { padding: 15px; border-radius: 8px; font-weight: bold; text-align: center; border: 2px solid; }
</style>
""", unsafe_allow_html=True)

# ==================== MOTEUR DE DONNÉES BLINDÉ ====================

def scrape_yahoo_data(ticker):
    """
    PLAN B: Scrape directement le HTML de Yahoo si l'API est bloquée.
    Utilise BeautifulSoup pour éviter les erreurs de lecture (ex: prix Apple 87k).
    """
    try:
        ua = UserAgent()
        headers = {'User-Agent': ua.random, 'Referer': 'https://www.google.com/'}
        url = f"https://finance.yahoo.com/quote/{ticker}"
        
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200: return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Extraction du PRIX (Balise fin-streamer très fiable)
        price_tag = soup.find('fin-streamer', {'data-field': 'regularMarketPrice'})
        price = float(price_tag['value']) if price_tag else 0.0
        
        # 2. Extraction Variation
        change_tag = soup.find('fin-streamer', {'data-field': 'regularMarketChangePercent'})
        change = float(change_tag['value']) if change_tag else 0.0
        
        # 3. Market Cap (souvent dans une table)
        # On essaie de trouver la table des stats
        stats = {}
        # Cette partie est plus fragile, on met des valeurs par défaut sécurisées
        
        return {
            'ticker': ticker,
            'name': ticker, # Difficile à extraire proprement sans API
            'current_price': price,
            'history': pd.DataFrame(), # Pas d'historique en mode scraping
            'trend_6m': change * 10, # Estimation grossière ou 0
            'market_cap': 0,
            'trailing_pe': 0,
            'debt': 0,
            'revenue_growth': 0,
            'source': 'SCRAPING WEB (Mode Survie)'
        }
    except Exception as e:
        print(f"Erreur Scraping: {e}")
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(ticker_symbol):
    # --- PLAN A : YFINANCE BULK DOWNLOAD (Souvent moins bloqué) ---
    try:
        # On utilise .download au lieu de .Ticker.history
        df = yf.download(ticker_symbol, period="6mo", progress=False)
        
        if df.empty:
            raise Exception("Download vide")

        # Infos fondamentales (Ticker API)
        # On met un User-Agent rotatif pour maximiser les chances
        session = requests.Session()
        session.headers['User-Agent'] = UserAgent().chrome
        stock = yf.Ticker(ticker_symbol, session=session)
        
        try:
            info = stock.info
        except:
            info = {}

        # Calculs
        try:
            # Gestion des multi-index de yfinance récents
            close_col = df['Close']
            if isinstance(close_col, pd.DataFrame):
                close_col = close_col.iloc[:, 0]
                
            price_today = float(close_col.iloc[-1])
            price_6m_ago = float(close_col.iloc[0])
            trend_6m = ((price_today - price_6m_ago) / price_6m_ago) * 100
        except:
            price_today = 0
            trend_6m = 0

        return {
            'ticker': ticker_symbol,
            'name': info.get('longName', ticker_symbol),
            'current_price': price_today,
            'history': df,
            'trend_6m': trend_6m,
            'market_cap': info.get('marketCap', 0),
            'trailing_pe': info.get('trailingPE', 0),
            'debt': info.get('totalDebt', 0),
            'revenue_growth': info.get('revenueGrowth', 0),
            'source': 'API YFINANCE'
        }

    except Exception:
        # --- PLAN B : SCRAPING DE SECOURS ---
        print(f"⚠️ Plan A échoué pour {ticker_symbol}, passage au Plan B (Scraping)")
        return scrape_yahoo_data(ticker_symbol)

# ==================== CERVEAU IA ====================
def analyze_with_ai(persona, data):
    try:
        api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
        if not api_key: return {'verdict': 'ERROR', 'score': 0, 'thesis': 'Clé API manquante', 'risk': 'HIGH'}
        
        client = OpenAI(api_key=api_key)
        logic = "Score < 45 = SELL, 46-65 = HOLD, > 66 = BUY."
        prompts = {
            "Warren": f"Warren Buffett. Value. {logic}",
            "Cathie": f"Cathie Wood. Growth. {logic}",
            "Jim": f"Jim Cramer. Momentum. {logic}"
        }
        
        # Message adapté selon la source
        source_msg = "(Données limitées - Mode Survie)" if "SCRAPING" in data['source'] else "(Données Complètes)"
        
        user_msg = f"""
        ANALYSE: {data['ticker']} {source_msg}
        Prix: ${data['current_price']:.2f}
        Trend 6M: {data.get('trend_6m', 0):.1f}%
        PE: {data.get('trailing_pe', 'N/A')}
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompts.get(persona, "") + " Réponds JSON: {verdict, score, thesis, risk}"},
                {"role": "user", "content": user_msg}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {'verdict': 'ERROR', 'score': 0, 'thesis': "Erreur IA", 'risk': 'HIGH'}

# ==================== MAIN UI ====================
def main():
    st.title("🦅 AI HUNTER V24 ARMORED")
    st.markdown("*Multi-Layer Data Engine*")
    st.markdown('<div class="macro-banner">📈 MARKET | S&P500: +0.4% | BTC: $98k | VIX: 13.5</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1: ticker = st.text_input("Ticker", "NVDA").upper().strip()
    with col2: btn = st.button("🚀 ANALYZE", type="primary", use_container_width=True)
    
    if btn and ticker:
        with st.spinner(f"🔍 Extraction ({ticker})..."):
            data = fetch_stock_data(ticker)
        
        if not data or data['current_price'] == 0:
            st.error(f"❌ Impossible de lire les données de {ticker}.")
            st.warning("Yahoo Finance bloque agressivement le Cloud aujourd'hui.")
            return

        # Header
        st.markdown(f"## {data['ticker']} - {data['name']}")
        st.markdown(f"# ${data['current_price']:.2f}")
        if "SCRAPING" in data['source']:
            st.warning("⚠️ Mode Survie : Graphique historique bloqué, mais Prix en temps réel récupéré.")
        else:
            st.success(f"✅ Source : {data['source']}")

        # Chart (Si dispo)
        if not data['history'].empty:
            fig = go.Figure(data=[go.Candlestick(
                x=data['history'].index,
                open=data['history']['Open'], high=data['history']['High'],
                low=data['history']['Low'], close=data['history']['Close'],
                increasing_line_color='#00ff41', decreasing_line_color='#ff0000'
            )])
            fig.update_layout(paper_bgcolor='#1a1f3a', plot_bgcolor='#1a1f3a', font={'color':'#00ff41'}, height=400, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

        # Métriques
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("PE Ratio", f"{data.get('trailing_pe', 0):.1f}")
        c2.metric("Market Cap", f"${data.get('market_cap', 0)/1e9:.1f}B")
        c3.metric("Dette", f"${data.get('debt', 0)/1e9:.1f}B")
        c4.metric("Trend 6M", f"{data.get('trend_6m', 0):.1f}%")

        # AI
        st.markdown("---")
        cols = st.columns(3)
        for i, p in enumerate(["Warren", "Cathie", "Jim"]):
            with cols[i]:
                res = analyze_with_ai(p, data)
                color = "#00ff41" if "BUY" in str(res.get('verdict')) else "#ff4136"
                st.markdown(f'<div class="verdict-box" style="color:{color}; border-color:{color}">{res.get("verdict", "N/A")} ({res.get("score", 0)})</div>', unsafe_allow_html=True)
                st.info(res.get('thesis', 'N/A'))

if __name__ == "__main__":
    main()