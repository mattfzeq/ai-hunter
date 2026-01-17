import streamlit as st
import os
import time  # <--- Le ralentisseur pour éviter le blocage OpenAI
import yfinance as yf
from openai import OpenAI
import json
import pandas as pd

# --- 1. CONFIGURATION & SÉCURITÉ ---
st.set_page_config(layout="wide", page_title="AI Strategic Hunter")

# Gestion des secrets (Local et Cloud)
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

def check_password():
    """Demande un mot de passe avant d'afficher l'app."""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    st.markdown("### 🔒 Accès Restreint")
    pwd = st.text_input("Mot de passe d'accès :", type="password")
    
    # Récupère le mdp du fichier .env ou des Secrets Streamlit (sinon "admin123")
    env_pwd = os.getenv("APP_PASSWORD", "admin123")
    
    if st.button("Valider"):
        if pwd == env_pwd:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Mauvais mot de passe.")
    return False

if not check_password():
    st.stop()

# --- INIT API ---
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("🚨 Clé API manquante ! Vérifiez les Secrets Streamlit.")
    st.stop()

client = OpenAI(api_key=api_key)

# --- 2. FONCTIONS ---
@st.cache_data(ttl=3600)
def analyze_stock(ticker):
    try:
        ticker = ticker.strip().upper()
        stock = yf.Ticker(ticker)
        
        # Historique (pour le graph)
        try:
            hist = stock.history(period="6mo")
        except:
            hist = pd.DataFrame()

        info = stock.info
        
        # Récupération du prix (plusieurs tentatives)
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not current_price and not hist.empty:
            current_price = hist['Close'].iloc[-1]
            
        if not current_price:
            st.warning(f"⚠️ Prix introuvable pour {ticker}")
            return None

        # Données
        pe = info.get('trailingPE', "N/A")
        peg = info.get('pegRatio', "N/A")
        
        # News
        news = stock.news[:2] if stock.news else []
        news_txt = "\n".join([n.get('title','') for n in news])

        # Prompt GPT
        prompt = f"""
        Analyse {ticker} (${current_price}).
        PE: {pe}, PEG: {peg}.
        News: {news_txt}
        Desc: {info.get('longBusinessSummary','')[:500]}
        
        Tâche:
        1. Catégorie (Infra, Robots, Agents, Legacy, Autre).
        2. Score Timing (0-100).
        3. Verdict (1 phrase courte).
        4. Analyse (3 points clés avec tirets).
        
        JSON strict:
        {{
            "category": "String",
            "timing_score": Int,
            "verdict": "String",
            "analysis_points": "String"
        }}
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        
        return {
            "Ticker": ticker,
            "Prix": current_price,
            "History": hist['Close'] if not hist.empty else None,
            "Catégorie": data.get("category"),
            "Timing": data.get("timing_score"),
            "Verdict": data.get("verdict"),
            "Détails": data.get("analysis_points")
        }

    except Exception as e:
        st.error(f"🚨 ERREUR sur {ticker} : {e}")
        return None

# --- 3. INTERFACE ---
st.title("🤖 AI Strategic Hunter")
st.caption("Protected Access • Powered by GPT-4o")

with st.sidebar:
    st.header("Portefeuille")
    raw_text = st.text_area("Tickers (ex: NVDA TSLA)", "NVDA PLTR")
    st.caption("💡 Astuce : Validez avec Ctrl+Entrée avant de lancer.")
    
    tickers = [t.strip() for t in raw_text.replace(',',' ').split() if t.strip()]
    launch = st.button("🚀 Analyser", type="primary")

if launch and tickers:
    for t in tickers:
        with st.spinner(f"Analyse de {t} en cours..."):
            data = analyze_stock(t)
            
            # --- LE FREIN À MAIN (Anti-Erreur 429) ---
            time.sleep(2)  # Pause de 2 secondes entre chaque appel
            
        if data:
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 2, 1])
                with c1:
                    st.metric(label=data['Ticker'], value=f"{data['Prix']:.2f} $")
                    st.badge(data['Catégorie'])
                with c2:
                    if data['History'] is not None:
                        st.line_chart(data['History'], height=80)
                with c3:
                    score = data.get('Timing', 0)
                    st.progress(score/100, text=f"Timing: {score}/100")
                    st.write(f"**{data['Verdict']}**")
                
                with st.expander(f"🧐 Voir l'analyse de {data['Ticker']}"):
                    st.markdown(data['Détails'])