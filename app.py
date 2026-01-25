import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
import os
import json
from openai import OpenAI
from datetime import datetime, timedelta

# ==================== CONFIGURATION ====================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

st.set_page_config(
    page_title="AI Hunter V23 Fusion",
    page_icon="🦅",
    layout="wide"
)

# ==================== STYLES CSS (BLOOMBERG DARK) ====================
st.markdown("""
<style>
    .stApp { background-color: #0a0e27; color: #00ff41; }
    .main { background-color: #0a0e27; }
    h1, h2, h3, h4, p, label, div { font-family: 'Courier New', monospace; color: #00ff41 !important; }
    div[data-testid="stMetricValue"] { color: #00ff41 !important; font-size: 1.6rem !important; }
    div[data-testid="stMetricLabel"] { color: #888888 !important; }
    .stMetric { background-color: #1a1f3a; padding: 10px; border-radius: 5px; border: 1px solid #00ff41; }
    .stButton > button { background-color: #1a1f3a; color: #00ff41; border: 2px solid #00ff41; font-weight: bold; }
    .stButton > button:hover { background-color: #00ff41; color: #0a0e27; }
    .macro-banner {
        background: linear-gradient(90deg, #1a1f3a 0%, #2a2f4a 100%);
        padding: 15px; border-radius: 8px; border: 1px solid #00ff41;
        margin-bottom: 20px; text-align: center;
    }
    .verdict-box {
        padding: 15px; border-radius: 8px; font-size: 18px; font-weight: bold;
        text-align: center; margin-bottom: 10px; border: 2px solid;
    }
</style>
""", unsafe_allow_html=True)

# ==================== MOTEUR DE DONNÉES (HYBRIDE) ====================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(ticker_symbol):
    try:
        # Headers "Magiques" pour passer pour un utilisateur Google
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.google.com/',
            'Accept-Language': 'en-US,en;q=0.9',
        })

        stock = yf.Ticker(ticker_symbol, session=session)
        
        # 1. Historique (Graphique)
        hist = stock.history(period="6mo")
        
        if hist.empty:
            return None # Si pas d'historique, on considère que ça a échoué proprement
            
        # 2. Infos Fondamentales (Avec sécurité anti-crash)
        try:
            info = stock.info
        except:
            info = {}

        # Calculs sécurisés
        price_today = hist['Close'].iloc[-1]
        price_6m_ago = hist['Close'].iloc[0]
        trend_6m = ((price_today - price_6m_ago) / price_6m_ago) * 100
        
        # Valeurs par défaut si Yahoo bloque les infos détaillées
        data = {
            'ticker': ticker_symbol,
            'name': info.get('longName', ticker_symbol),
            'current_price': price_today,
            'history': hist,
            'trend_6m': trend_6m,
            'market_cap': info.get('marketCap', 0),
            'trailing_pe': info.get('trailingPE', 0),
            'beta': info.get('beta', 1.0),
            'debt': info.get('totalDebt', 0),
            'cashflow': info.get('freeCashflow', 0),
            'revenue_growth': info.get('revenueGrowth', 0),
            'profit_margins': info.get('profitMargins', 0)
        }
        return data

    except Exception as e:
        print(f"Erreur Fetch: {e}")
        return None

# ==================== CERVEAU IA (OPENAI) ====================
def analyze_with_ai(persona, data):
    try:
        api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
        if not api_key: return {'verdict': 'ERROR', 'score': 0, 'thesis': 'Clé API manquante', 'risk': 'HIGH'}
        
        client = OpenAI(api_key=api_key)
        
        logic = "RÈGLE: Score < 45 = SELL, 46-65 = HOLD, > 66 = BUY."
        
        prompts = {
            "Warren": f"Tu es Warren Buffett. Value Investing. {logic}",
            "Cathie": f"Tu es Cathie Wood. Innovation Growth. {logic}",
            "Jim": f"Tu es Jim Cramer. Momentum Trading. {logic}"
        }
        
        # Formatage sécurisé des chiffres pour l'IA
        debt_str = f"${data['debt']/1e9:.1f}B" if data['debt'] else "N/A"
        pe_str = f"{data['trailing_pe']:.1f}" if data['trailing_pe'] else "N/A"
        growth_str = f"{data['revenue_growth']*100:.1f}%" if data['revenue_growth'] else "N/A"
        
        user_msg = f"""
        ANALYSE: {data['ticker']} (${data['current_price']:.2f})
        Trend 6M: {data['trend_6m']:.1f}%
        PE: {pe_str} | Dette: {debt_str} | Rev Growth: {growth_str}
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
    
    except Exception as e:
        return {'verdict': 'ERROR', 'score': 0, 'thesis': f"Erreur IA: {str(e)}", 'risk': 'HIGH'}

# ==================== GRAPHIQUE PLOTLY ====================
def create_chart(data):
    fig = go.Figure()
    # Chandelier
    fig.add_trace(go.Candlestick(
        x=data['history'].index,
        open=data['history']['Open'], high=data['history']['High'],
        low=data['history']['Low'], close=data['history']['Close'],
        name='Prix', increasing_line_color='#00ff41', decreasing_line_color='#ff0000'
    ))
    # Layout Bloomberg
    fig.update_layout(
        paper_bgcolor='#1a1f3a', plot_bgcolor='#1a1f3a',
        font=dict(color='#00ff41', family='Courier New'),
        height=400, margin=dict(l=20, r=20, t=30, b=20),
        xaxis_rangeslider_visible=False
    )
    return fig

# ==================== MAIN UI ====================
def main():
    st.title("🦅 AI HUNTER V23 FUSION")
    st.markdown("*Design Plotly + Moteur Hybride + GPT Logic*")
    
    # Macro Banner
    st.markdown('<div class="macro-banner">📈 MARKET | S&P500: +0.4% | BTC: $98k | VIX: 13.5</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1: ticker = st.text_input("Ticker", "NVDA").upper().strip()
    with col2: btn = st.button("🚀 ANALYZE", type="primary", use_container_width=True)
    
    if btn and ticker:
        with st.spinner(f"🔍 Analyse de {ticker}..."):
            data = fetch_stock_data(ticker)
        
        if not data:
            st.error(f"❌ Impossible de récupérer {ticker}. Yahoo Finance bloque l'accès Cloud temporairement.")
            st.info("💡 Astuce : Réessayez dans 5 minutes ou testez un autre ticker.")
            return

        # Header Prix
        st.markdown(f"## {data['ticker']} - {data['name']}")
        st.markdown(f"# ${data['current_price']:.2f} <span style='font-size:24px; color:{'#00ff41' if data['trend_6m']>0 else '#ff0000'}'>({data['trend_6m']:+.1f}%)</span>", unsafe_allow_html=True)
        
        # Graphique Plotly
        st.plotly_chart(create_chart(data), use_container_width=True)
        
        # Métriques
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("PE Ratio", f"{data['trailing_pe']:.1f}" if data['trailing_pe'] else "N/A")
        c2.metric("Market Cap", f"${data['market_cap']/1e9:.1f}B" if data['market_cap'] else "N/A")
        c3.metric("Dette Total", f"${data['debt']/1e9:.1f}B" if data['debt'] else "N/A")
        c4.metric("Rev Growth", f"{data['revenue_growth']*100:.1f}%" if data['revenue_growth'] else "N/A")
        
        # AI Analysis
        st.markdown("---")
        st.subheader("🤖 AI Council")
        cols = st.columns(3)
        for i, p in enumerate(["Warren", "Cathie", "Jim"]):
            with cols[i]:
                res = analyze_with_ai(p, data)
                # Affichage Verdict
                verdict = res.get('verdict', 'N/A')
                score = res.get('score', 0)
                color = "#00ff41" if "BUY" in str(verdict) else "#ff4136" if "SELL" in str(verdict) else "#ffdc00"
                
                st.markdown(f'<div class="verdict-box" style="color:{color}; border-color:{color}">{verdict} ({score}/100)</div>', unsafe_allow_html=True)
                st.info(res.get('thesis', 'Pas d\'analyse disponible'))

if __name__ == "__main__":
    main()