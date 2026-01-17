import streamlit as st
import os
import yfinance as yf
from openai import OpenAI
import json
import pandas as pd
from io import BytesIO

# --- 1. CONFIGURATION & SÉCURITÉ ---
st.set_page_config(layout="wide", page_title="AI Strategic Hunter")

# Gestion des secrets (Fonctionne en Local .env ET en Ligne)
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# --- 🔒 PROTECTION DU SITE (Anti-Faillite) ---
def check_password():
    """Demande un mot de passe avant d'afficher l'app."""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    st.markdown("### 🔒 Accès Restreint")
    pwd = st.text_input("Mot de passe d'accès :", type="password")
    
    # DÉFINISSEZ VOTRE MOT DE PASSE ICI (ex: "admin123")
    if st.button("Valider"):
        if pwd == os.getenv("APP_PASSWORD", "admin123"): # Par défaut "admin123" si pas configuré
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Mauvais mot de passe.")
    return False

if not check_password():
    st.stop() # Arrête tout si pas connecté

# --- INIT API ---
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Clé API manquante dans les secrets.")
    st.stop()

client = OpenAI(api_key=api_key)

# --- 2. FONCTIONS ---
@st.cache_data(ttl=3600)
def analyze_stock(ticker):
    try:
        ticker = ticker.strip().upper()
        stock = yf.Ticker(ticker)
        
        # Historique pour le graphique
        try:
            hist = stock.history(period="6mo")
        except:
            hist = pd.DataFrame()

        info = stock.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or (hist['Close'].iloc[-1] if not hist.empty else 0)
        
        if not current_price: return None

        # Data
        pe = info.get('trailingPE', "N/A")
        peg = info.get('pegRatio', "N/A")
        
        # News
        news = stock.news[:2] if stock.news else []
        news_txt = "\n".join([n.get('title','') for n in news])

        # Prompt
        prompt = f"""
        Analyse {ticker} (${current_price}).
        PE: {pe}, PEG: {peg}.
        News: {news_txt}
        Desc: {info.get('longBusinessSummary','')[:500]}
        
        Tâche:
        1. Catégorie (Infra, Robots, Agents, Legacy, Autre).
        2. Score Timing (0-100).
        3. Verdict (1 phrase courte).
        4. Analyse (3 points clés bullet points).
        
        JSON strict:
        {{
            "category": "String",
            "timing_score": Int,
            "verdict": "String",
            "analysis_points": "String (avec tirets)"
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
            "History": hist['Close'] if not hist.empty else None, # On garde la courbe !
            "Catégorie": data.get("category"),
            "Timing": data.get("timing_score"),
            "Verdict": data.get("verdict"),
            "Détails": data.get("analysis_points")
        }
    except Exception:
        return None

# --- 3. INTERFACE ---
st.title("🤖 AI Strategic Hunter")
st.caption("Protected Access • Powered by GPT-4o & Yahoo Finance")

with st.sidebar:
    st.header("Portefeuille")
    raw_text = st.text_area("Tickers (ex: NVDA TSLA)", "NVDA PLTR")
    tickers = [t.strip() for t in raw_text.replace(',',' ').split() if t.strip()]
    launch = st.button("🚀 Analyser", type="primary")

if launch and tickers:
    for t in tickers:
        with st.spinner(f"Analyse de {t}..."):
            data = analyze_stock(t)
            
        if data:
            # --- DESIGN CARTE ---
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 2, 1])
                
                with c1:
                    st.metric(label=data['Ticker'], value=f"{data['Prix']:.2f} $")
                    st.badge(data['Catégorie'])
                
                with c2:
                    # Le Graphique Sparkline !
                    if data['History'] is not None:
                        st.line_chart(data['History'], height=80)
                
                with c3:
                    color = "normal"
                    if data['Timing'] > 80: color = "off" # Vert (astuce d'affichage)
                    st.progress(data['Timing']/100, text=f"Timing: {data['Timing']}/100")
                    st.write(f"**{data['Verdict']}**")
                
                # Le détail dépliable
                with st.expander(f"🧐 Voir l'analyse détaillée de {data['Ticker']}"):
                    st.markdown(data['Détails'])