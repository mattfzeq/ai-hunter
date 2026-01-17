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

# --- SÉCURITÉ ---
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
        
        # Récupération Historique
        try:
            hist = stock.history(period="6mo")
        except:
            hist = pd.DataFrame()

        info = stock.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        
        # Secours si le prix n'est pas dans 'info'
        if not current_price and not hist.empty:
            current_price = hist['Close'].iloc[-1]
            
        if not current_price:
            st.warning(f"⚠️ Prix introuvable pour {ticker}")
            return None

        # Infos financières
        pe = info.get('trailingPE', "N/A")
        
        # News (On limite à 1 pour économiser)
        news = stock.news[:1] if stock.news else []
        news_txt = news[0].get('title','') if news else "Pas de news récente"

        # Prompt optimisé pour GPT-3.5
        prompt = f"""
        Analyse l'action {ticker} (${current_price}). PE Ratio: {pe}.
        Dernière news: {news_txt}
        Business: {info.get('longBusinessSummary','')[:300]}
        
        Agis comme un analyste financier senior.
        
        Réponds UNIQUEMENT en JSON avec ce format exact :
        {{
            "category": "Catégorie (IA Infra, Robotique, Software, Legacy, Autre)",
            "timing_score": 50 (Score entre 0 et 100),
            "verdict": "Avis court (Haussier/Baissier/Neutre)",
            "analysis_points": "3 points clés résumés avec des tirets"
        }}
        """

        # --- LE CHANGEMENT MAGIQUE EST ICI ---
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # <--- Le modèle fiable
            messages=[{"role": "user", "content": prompt}],
            # GPT-3.5 a parfois du mal avec le mode JSON strict, on le guide via le prompt
        )
        
        # Nettoyage de la réponse (au cas où GPT-3.5 bavarde un peu autour du JSON)
        content = response.choices[0].message.content
        # On cherche le début et la fin du JSON
        start = content.find('{')
        end = content.rfind('}') + 1
        if start != -1 and end != -1:
            json_str = content[start:end]
            data = json.loads(json_str)
        else:
            # Fallback si le JSON échoue
            data = {
                "category": "Inconnu",
                "timing_score": 50,
                "verdict": "Erreur format",
                "analysis_points": content[:100]
            }
        
        return {
            "Ticker": ticker,
            "Prix": current_price,
            "History": hist['Close'] if not hist.empty else None,
            "Catégorie": data.get("category", "Autre"),
            "Timing": data.get("timing_score", 50),
            "Verdict": data.get("verdict", "N/A"),
            "Détails": data.get("analysis_points", "Pas de détails")
        }

    except Exception as e:
        st.error(f"Erreur sur {ticker}: {e}")
        return None

# --- 3. INTERFACE ---
st.title("🤖 AI Strategic Hunter")
st.caption("Version Stable • Powered by GPT-3.5 Turbo")

with st.sidebar:
    st.header("Portefeuille")
    raw_text = st.text_area("Tickers", "NVDA PLTR") 
    tickers = [t.strip() for t in raw_text.replace(',',' ').split() if t.strip()]
    launch = st.button("🚀 Analyser")

if launch and tickers:
    for t in tickers:
        with st.spinner(f"Analyse de {t}..."):
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
                    score = int(data.get('Timing', 50))
                    st.progress(score/100, text=f"Timing: {score}/100")
                    st.write(f"**{data['Verdict']}**")
                
                with st.expander(f"Détails {data['Ticker']}"):
                    st.markdown(data['Détails'])