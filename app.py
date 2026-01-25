import requests
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json
from openai import OpenAI

# ============================================================================
# 0. CHARGEMENT DE LA CLÉ API
# ============================================================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================================
# 1. CONFIGURATION & STYLING
# ============================================================================

st.set_page_config(
    page_title="AI Hunter V21 Ultimate",
    page_icon="🦅",
    layout="wide"
)

# CSS Bloomberg Terminal Style
st.markdown("""
<style>
    .stApp {
        background-color: #0a0e27;
        color: #00ff41;
    }
    .main {
        background-color: #0a0e27;
    }
    h1, h2, h3 {
        color: #00ff41;
        font-family: 'Courier New', monospace;
    }
    div[data-testid="stMetricValue"] {
        color: #00ff41 !important;
        font-size: 1.6rem !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #888888 !important;
    }
    .stMetric {
        background-color: #1a1f3a;
        padding: 15px;
        border-radius: 5px;
        border: 1px solid #00ff41;
    }
    .macro-banner {
        background: linear-gradient(90deg, #1a1f3a 0%, #2a2f4a 100%);
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #00ff41;
        margin-bottom: 20px;
        font-family: 'Courier New', monospace;
        color: #00ff41;
    }
    .verdict-buy {
        background-color: #004d00;
        color: #00ff41;
        padding: 15px;
        border-radius: 8px;
        border: 2px solid #00ff41;
        font-size: 20px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 10px;
    }
    .verdict-sell {
        background-color: #4d0000;
        color: #ff4136;
        padding: 15px;
        border-radius: 8px;
        border: 2px solid #ff4136;
        font-size: 20px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 10px;
    }
    .verdict-hold {
        background-color: #4d4d00;
        color: #ffdc00;
        padding: 15px;
        border-radius: 8px;
        border: 2px solid #ffdc00;
        font-size: 20px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 10px;
    }
    .error-box {
        background-color: #4d0000;
        color: #ff4136;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #ff4136;
        margin: 10px 0;
        font-family: 'Courier New', monospace;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# MACRO BANNER
# ============================================================================

def render_macro_banner():
    st.markdown("""
    <div class="macro-banner">
        <strong>📈 MARKET OVERVIEW</strong> | 
        S&P500: 5,850 (+0.45%) | 
        NASDAQ: 18,200 (+0.62%) | 
        BTC: $98,300 (-1.2%) | 
        VIX: 13.5 | 
        10Y YIELD: 4.2%
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# DATA ENGINE (YFINANCE MODE TANK)
# ============================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(ticker):
    """
    Récupère les données avec une stratégie de repli (Fallback).
    Si l'historique est bloqué, on utilise 'fast_info' pour avoir au moins le prix.
    """
    try:
        # Session "Linux" (marche mieux sur les serveurs Cloud)
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })
        
        stock = yf.Ticker(ticker, session=session)
        
        # 1. TENTATIVE PRIX IMMÉDIAT (Fast Info) - Souvent non bloqué
        try:
            current_price = stock.fast_info['last_price']
        except:
            # Si même ça échoue, le ticker est probablement invalide
            st.error(f"❌ Impossible de lire le prix pour {ticker}")
            return None

        # 2. TENTATIVE HISTORIQUE (Pour le graphique et Trend)
        try:
            hist = stock.history(period="6mo")
            if not hist.empty:
                price_6m_ago = hist['Close'].iloc[0]
                price_today = hist['Close'].iloc[-1]
                trend_6m = ((price_today - price_6m_ago) / price_6m_ago) * 100
                has_history = True
            else:
                raise Exception("Empty History")
        except:
            # Si bloqué, on simule des données neutres
            print(f"⚠️ Historique bloqué pour {ticker}")
            hist = pd.DataFrame()
            trend_6m = 0
            has_history = False

        # 3. TENTATIVE INFOS FONDAMENTALES
        try:
            info = stock.info
        except:
            info = {}

        # Mode dégradé intelligent
        market_cap = info.get('marketCap', stock.fast_info.get('market_cap', 0))
        trailing_pe = info.get('trailingPE', 0)
        
        # Construction du résultat
        result = {
            'ticker': ticker,
            'history': hist,
            'has_history': has_history, # Indicateur pour l'interface
            'trend_6m': trend_6m,
            'market_cap': market_cap,
            'trailing_pe': trailing_pe if trailing_pe else 0,
            'beta': info.get('beta', 1.0),
            'profit_margins': info.get('profitMargins', 0),
            'revenue_growth': info.get('revenueGrowth', 0),
            'total_debt': info.get('totalDebt', 0),
            'free_cashflow': info.get('freeCashflow', 0),
            'current_price': current_price,
            'news': []
        }
        
        return result
    
    except Exception as e:
        print(f"Erreur critique fetch_data: {e}")
        return None

# ============================================================================
# AI BRAIN (OPENAI)
# ============================================================================

def analyze_with_ai(persona, stock_data):
    try:
        api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
        if not api_key: 
            return {'verdict': 'ERROR', 'score': 0, 'thesis': 'Clé API manquante', 'risk': 'HIGH'}
        
        client = OpenAI(api_key=api_key)
        
        logic_matrix = """
        RÈGLE IMPÉRATIVE DE COHÉRENCE :
        - Si Score entre 0 et 45 -> Verdict DOIT être 'SELL'.
        - Si Score entre 46 et 65 -> Verdict DOIT être 'HOLD'.
        - Si Score entre 66 et 100 -> Verdict DOIT être 'BUY'.
        Ne donne jamais un verdict 'SELL' avec un score de 60. Sois logique.
        """

        if persona == "Warren":
            system_prompt = f"Tu es Warren Buffett. {logic_matrix} Réponds en JSON."
        elif persona == "Cathie":
            system_prompt = f"Tu es Cathie Wood. {logic_matrix} Réponds en JSON."
        else:
            system_prompt = f"Tu es Jim Cramer. {logic_matrix} Réponds en JSON."
        
        # Données formatées
        rev_growth_val = stock_data['revenue_growth']
        rev_growth_str = f"{rev_growth_val*100:.1f}%" if rev_growth_val else "N/A"
        
        # Mention spéciale si données partielles
        warning_msg = "(Données partielles - Yahoo Limit)" if not stock_data['has_history'] else ""

        user_message = f"""
        ANALYSE : {stock_data['ticker']} {warning_msg}
        Prix: ${stock_data['current_price']:.2f}
        Trend 6M: {stock_data['trend_6m']:.2f}%
        PE: {stock_data['trailing_pe']}
        Dette: ${stock_data['total_debt']/1e9:.2f}B
        CashFlow: ${stock_data['free_cashflow']/1e9:.2f}B
        Rev Growth: {rev_growth_str}
        Beta: {stock_data['beta']}
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0,
            seed=42,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    
    except Exception as e:
        return {'verdict': 'ERROR', 'score': 0, 'thesis': f"Erreur AI: {str(e)}", 'risk': 'HIGH'}

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_verdict_card(verdict, score):
    if "SELL" in verdict.upper():
        st.markdown(f'<div class="verdict-sell">🔴 {verdict} ({score}/100)</div>', unsafe_allow_html=True)
    elif "BUY" in verdict.upper():
        st.markdown(f'<div class="verdict-buy">🟢 {verdict} ({score}/100)</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="verdict-hold">🟡 {verdict} ({score}/100)</div>', unsafe_allow_html=True)
    
    color = "#00ff41" if score >= 66 else "#ffdc00" if score >= 46 else "#ff4136"
    st.markdown(f"""
    <div style="background-color: #1a1f3a; border-radius: 10px; padding: 5px; margin-top: 5px;">
        <div style="background-color: {color}; width: {score}%; height: 8px; border-radius: 8px;"></div>
    </div>""", unsafe_allow_html=True)

def generate_csv_report(ticker, analyses):
    rows = []
    for persona, result in analyses.items():
        rows.append({
            'Ticker': ticker, 'Persona': persona, 
            'Verdict': result['verdict'], 'Score': result['score'], 
            'Thesis': result['thesis']
        })
    return pd.DataFrame(rows).to_csv(index=False).encode('utf-8')

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    st.title("🎯 AI HUNTER V21 ULTIMATE")
    st.markdown("*Powered by yfinance + GPT-3.5-Turbo (Logic Enforced)*")
    render_macro_banner()
    
    col1, col2 = st.columns([3, 1])
    with col1: ticker_input = st.text_input("🔍 Ticker", value="NVDA")
    with col2: analyze_btn = st.button("🚀 ANALYZE", type="primary", use_container_width=True)
    
    if analyze_btn and ticker_input:
        ticker = ticker_input.strip().upper()
        
        with st.spinner(f"🔍 Récupération des données pour {ticker}..."):
            data = fetch_stock_data(ticker)
        
        if not data:
            st.markdown(f"""
            <div class="error-box">
                <strong>❌ Ticker {ticker} introuvable (ou bloqué)</strong><br>
                Yahoo Finance bloque l'accès depuis le Cloud. Réessayez plus tard.
            </div>
            """, unsafe_allow_html=True)
            return
        
        # Metrics UI
        st.markdown("---")
        st.subheader(f"📈 {ticker} - ${data['current_price']:.2f}")
        
        # Avertissement si mode dégradé
        if not data['has_history']:
            st.warning("⚠️ Graphique bloqué par Yahoo - Analyse basée sur le prix actuel uniquement.")

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Trend 6M", f"{data['trend_6m']:.1f}%", delta_color="normal" if data['trend_6m']>0 else "inverse")
        c2.metric("Market Cap", f"${data['market_cap']/1e9:.1f}B")
        c3.metric("PE Ratio", f"{data['trailing_pe']:.1f}" if data['trailing_pe'] else "N/A")
        c4.metric("Dette", f"${data['total_debt']/1e9:.1f}B" if data['total_debt'] else "N/A")
        c5.metric("Free CashFlow", f"${data['free_cashflow']/1e9:.1f}B" if data['free_cashflow'] else "N/A")
        
        # Chart (Seulement si dispo)
        if data['has_history'] and not data['history'].empty:
            st.area_chart(data['history']['Close'], color="#00ff41")
        
        # AI Analysis
        st.markdown("---")
        st.header("🤖 AI ANALYSIS")
        personas = ["Warren", "Cathie", "Jim"]
        analyses = {}
        
        with st.spinner("🧠 Reasoning..."):
            cols = st.columns(3)
            for i, p in enumerate(personas):
                with cols[i]:
                    st.subheader(f"💼 {p}")
                    res = analyze_with_ai(p, data)
                    analyses[p] = res
                    render_verdict_card(res['verdict'], res['score'])
                    st.info(res['thesis'])
                    st.caption(f"Risk: {res['risk']}")
        
        # Export
        st.markdown("---")
        st.download_button("📥 Download Report", generate_csv_report(ticker, analyses), "report.csv", "text/csv")

if __name__ == "__main__":
    main()