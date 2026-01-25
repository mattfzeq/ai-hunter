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
# DATA ENGINE (YFINANCE) - VERSION CORRIGÉE
# ============================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(ticker):
    """
    Récupère les données via yfinance avec gestion d'erreur améliorée
    """
    try:
        # Session avec User-Agent pour éviter le blocage Yahoo
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        # Créer l'objet Ticker
        stock = yf.Ticker(ticker, session=session)
        
        # Récupérer l'historique sur 6 mois
        hist = stock.history(period="6mo")
        
        # Vérifier si l'historique est vide
        if hist.empty:
            st.error(f"❌ Aucune donnée historique trouvée pour {ticker}")
            return None
        
        # Vérifier qu'on a au moins quelques jours de données
        if len(hist) < 5:
            st.warning(f"⚠️ Données limitées pour {ticker} ({len(hist)} jours)")
            return None
        
        # Calculer la tendance 6 mois
        price_6m_ago = hist['Close'].iloc[0]
        price_today = hist['Close'].iloc[-1]
        trend_6m = ((price_today - price_6m_ago) / price_6m_ago) * 100
        
        # Récupérer les infos fondamentales
        info = stock.info
        
        # Vérifier que info n'est pas vide
        if not info or len(info) < 5:
            st.warning(f"⚠️ Informations limitées pour {ticker}")
        
        # Construire le dictionnaire de résultats avec valeurs par défaut
        result = {
            'ticker': ticker,
            'history': hist,
            'trend_6m': trend_6m,
            'market_cap': info.get('marketCap', 0),
            'trailing_pe': info.get('trailingPE', info.get('forwardPE', None)),
            'beta': info.get('beta', 1.0),
            'profit_margins': info.get('profitMargins', 0),
            'revenue_growth': info.get('revenueGrowth', 0),
            'total_debt': info.get('totalDebt', 0),
            'free_cashflow': info.get('freeCashflow', 0),
            'current_price': price_today
        }
        
        # Récupérer les news si disponibles
        try:
            news_items = stock.news if hasattr(stock, 'news') else []
            result['news'] = [n.get('title', 'N/A') for n in news_items[:3]] if news_items else []
        except:
            result['news'] = []
        
        return result
    
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Erreur HTTP {e.response.status_code}: Yahoo Finance a bloqué la requête")
        st.info("💡 Essayez un autre ticker ou attendez quelques minutes")
        return None
    except requests.exceptions.ConnectionError:
        st.error("❌ Erreur de connexion - Vérifiez votre connexion Internet")
        return None
    except Exception as e:
        st.error(f"❌ Erreur inattendue: {str(e)}")
        st.code(f"Type d'erreur: {type(e).__name__}")
        return None

# ============================================================================
# AI BRAIN (OPENAI) - AVEC LOGIQUE STRICTE
# ============================================================================

def analyze_with_ai(persona, stock_data):
    try:
        api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
        if not api_key: 
            return {
                'verdict': 'ERROR', 
                'score': 0, 
                'thesis': 'Clé API OpenAI manquante. Ajoutez OPENAI_API_KEY dans .env ou Streamlit secrets.', 
                'risk': 'HIGH'
            }
        
        client = OpenAI(api_key=api_key)
        
        # --- DEFINITION DES PERSONAS AVEC REGLES DE SCORE ---
        logic_matrix = """
        RÈGLE IMPÉRATIVE DE COHÉRENCE (Tu DOIS respecter ça) :
        - Si Score entre 0 et 45 -> Verdict DOIT être 'SELL'.
        - Si Score entre 46 et 65 -> Verdict DOIT être 'HOLD'.
        - Si Score entre 66 et 100 -> Verdict DOIT être 'BUY'.
        Ne donne jamais un verdict 'SELL' avec un score de 60. Sois logique.
        """

        if persona == "Warren":
            system_prompt = f"""Tu es Warren Buffett. Prudence absolue.
            Tu détestes la dette élevée et les PE > 30. Tu aimes le Cash Flow positif.
            {logic_matrix}
            Réponds en JSON : {{"verdict": "BUY/HOLD/SELL", "score": 0-100, "thesis": "...", "risk": "LOW/MEDIUM/HIGH"}}"""
        
        elif persona == "Cathie":
            system_prompt = f"""Tu es Cathie Wood. Tu aimes l'innovation et la croissance.
            Tu ignores la dette si la croissance des revenus est forte (>20%).
            {logic_matrix}
            Réponds en JSON : {{"verdict": "BUY/HOLD/SELL", "score": 0-100, "thesis": "...", "risk": "LOW/MEDIUM/HIGH"}}"""
        
        else:  # Jim
            system_prompt = f"""Tu es Jim Cramer. Tu joues la tendance (Momentum).
            Si Trend 6M est positif et Beta élevé -> Tu achètes.
            {logic_matrix}
            Réponds en JSON : {{"verdict": "BUY/HOLD/SELL", "score": 0-100, "thesis": "...", "risk": "LOW/MEDIUM/HIGH"}}"""
        
        # Données envoyées à l'IA
        rev_growth = f"{stock_data['revenue_growth']*100:.1f}%" if stock_data['revenue_growth'] else 'N/A'
        
        user_message = f"""
        ANALYSE : {stock_data['ticker']}
        Prix: ${stock_data['current_price']:.2f}
        Trend 6M: {stock_data['trend_6m']:.2f}%
        PE: {stock_data['trailing_pe'] if stock_data['trailing_pe'] else 'N/A'}
        Dette: ${stock_data['total_debt']/1e9:.2f}B (CRITIQUE)
        CashFlow: ${stock_data['free_cashflow']/1e9:.2f}B
        Rev Growth: {rev_growth}
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
        
        result = json.loads(response.choices[0].message.content)
        return result
    
    except Exception as e:
        return {
            'verdict': 'ERROR', 
            'score': 0, 
            'thesis': f"Erreur AI: {str(e)}", 
            'risk': 'HIGH'
        }

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
        
        # Afficher un message de diagnostic
        with st.spinner(f"🔍 Récupération des données pour {ticker}..."):
            data = fetch_stock_data(ticker)
        
        # Meilleur diagnostic si échec
        if not data:
            st.markdown(f"""
            <div class="error-box">
                <strong>❌ Impossible de récupérer les données pour {ticker}</strong><br><br>
                Causes possibles:<br>
                • Le ticker n'existe pas ou est mal orthographié<br>
                • Yahoo Finance bloque les requêtes (essayez dans quelques minutes)<br>
                • Le ticker nécessite un suffixe de marché (ex: TICKER.PA pour Paris)<br><br>
                💡 Essayez: AAPL, MSFT, GOOGL, TSLA, AMZN
            </div>
            """, unsafe_allow_html=True)
            return
        
        # Metrics UI
        st.markdown("---")
        st.subheader(f"📈 {ticker} - ${data['current_price']:.2f}")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Trend 6M", f"{data['trend_6m']:.1f}%", delta_color="normal" if data['trend_6m']>0 else "inverse")
        c2.metric("Market Cap", f"${data['market_cap']/1e9:.1f}B")
        c3.metric("PE Ratio", f"{data['trailing_pe']:.1f}" if data['trailing_pe'] else "N/A")
        c4.metric("Dette", f"${data['total_debt']/1e9:.1f}B" if data['total_debt'] else "N/A")
        c5.metric("Free CashFlow", f"${data['free_cashflow']/1e9:.1f}B" if data['free_cashflow'] else "N/A")
        
        # Chart
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