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

# --- 2. FONCTIONS ---
@st.cache_data(ttl=3600)
def analyze_stock(ticker):
    try:
        ticker = ticker.strip().upper()
        stock = yf.Ticker(ticker)
        
        try:
            hist = stock.history(period="6mo")
        except:
            hist = pd.DataFrame()

        info = stock.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not current_price and not hist.empty:
            current_price = hist['Close'].iloc[-1]
            
        if not current_price:
            st.warning(f"⚠️ Prix introuvable pour {ticker}")
            return None

        pe = info.get('trailingPE', "N/A")
        peg = info.get('pegRatio', "N/A")
        
        news = stock.news[:2] if stock.news else []
        news_txt = "\n".join([n.get('title','') for n in news])

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

        # --- LE CHANGEMENT EST ICI ---
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # <--- On passe au modèle rapide !
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
        # On affiche l'erreur en rouge pour comprendre
        st.error(f"🚨 ERREUR sur {ticker} : {e}")
        return None

# --- 3. INTERFACE ---
st.title("🤖 AI Strategic Hunter (Mini)")

with st.sidebar:
    st.header("Portefeuille")
    # On laisse NVDA par défaut pour le test
    raw_text = st.text_area("Tickers", "NVDA") 
    tickers = [t.strip() for t in raw_text.replace(',',' ').split() if t.strip()]
    launch = st.button("🚀 Analyser")

if launch and tickers:
    for t in tickers:
        with st.spinner(f"Analyse de {t} ({t})..."):
            data = analyze_stock(t)
            time.sleep(1) # Petite pause de sécurité
            
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
                
                with st.expander(f"Détails {data['Ticker']}"):
                    st.markdown(data['Détails'])