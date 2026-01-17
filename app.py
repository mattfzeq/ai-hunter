import streamlit as st
import os
import time
import yfinance as yf
from openai import OpenAI
import json
import pandas as pd

# --- 1. CONFIGURATION ---
st.set_page_config(layout="wide", page_title="AI Strategic Hunter")

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    st.markdown("### 🔒 Accès Restreint")
    pwd = st.text_input("Mot de passe d'accès :", type="password")
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
    st.error("🚨 Clé API manquante !")
    st.stop()

client = OpenAI(api_key=api_key)

# --- 2. FONCTION INTELLIGENTE (AVEC RETRY) ---
def get_analysis_safe(prompt, max_retries=3):
    """Force le passage si OpenAI bloque (Erreur 429)"""
    for i in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # On force le modèle rapide
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            if "Rate limit" in str(e) or "429" in str(e):
                wait_time = (i + 1) * 5 # Attendre 5s, puis 10s...
                st.warning(f"⚠️ OpenAI sature. Nouvelle tentative dans {wait_time}s...")
                time.sleep(wait_time)
            else:
                st.error(f"Erreur technique : {e}")
                return None
    st.error("🚨 Abandon après 3 tentatives. Le serveur OpenAI est trop chargé.")
    return None

@st.cache_data(ttl=3600)
def analyze_stock(ticker):
    try:
        ticker = ticker.strip().upper()
        stock = yf.Ticker(ticker)
        
        # Historique
        try:
            hist = stock.history(period="6mo")
        except:
            hist = pd.DataFrame()

        info = stock.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not current_price and not hist.empty:
            current_price = hist['Close'].iloc[-1]
            
        if not current_price:
            st.warning(f"Prix introuvable pour {ticker}")
            return None

        # Infos allégées pour économiser des tokens
        pe = info.get('trailingPE', "N/A")
        
        news = stock.news[:1] if stock.news else [] # Une seule news pour aller vite
        news_txt = news[0].get('title','') if news else "Pas de news récente"

        # Prompt court
        prompt = f"""
        Stock: {ticker} (${current_price}). PE: {pe}.
        News: {news_txt}
        Business: {info.get('longBusinessSummary','')[:200]}
        
        Analyze for an investor. Return JSON:
        {{
            "category": "String (Infrastructure, Robots, Software, Legacy, Other)",
            "timing_score": Int (0-100),
            "verdict": "String (Bullish/Bearish/Neutral)",
            "analysis_points": "String (3 short bullet points)"
        }}
        """

        # Appel sécurisé
        return {
            "Ticker": ticker,
            "Prix": current_price,
            "History": hist['Close'] if not hist.empty else None,
            **get_analysis_safe(prompt) # On fusionne le résultat JSON
        }

    except Exception as e:
        return None

# --- 3. INTERFACE ---
st.title("🤖 AI Strategic Hunter (Retry Mode)")

with st.sidebar:
    st.header("Portefeuille")
    raw_text = st.text_area("Tickers", "NVDA") 
    tickers = [t.strip() for t in raw_text.replace(',',' ').split() if t.strip()]
    launch = st.button("🚀 Analyser")

if launch and tickers:
    for t in tickers:
        with st.spinner(f"Analyse de {t}..."):
            data = analyze_stock(t)
            
        if data and data.get("Verdict"): # Vérifie qu'on a bien reçu des données
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
                
                with st.expander("Détails"):
                    st.markdown(data.get('Détails', 'Pas de détails'))
        else:
            st.error(f"Impossible d'analyser {t} (Erreur API ou Données)")