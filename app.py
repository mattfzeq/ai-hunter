import streamlit as st
import os
import time
import yfinance as yf
from openai import OpenAI
import json
import pandas as pd
import random
import datetime

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
client = OpenAI(api_key=api_key) if api_key else None

# --- 2. FONCTIONS DE SECOURS (MOCK DATA) ---
def get_mock_data(ticker):
    """Génère de fausses données réalistes si Yahoo bloque"""
    # Prix aléatoire entre 100 et 500
    base_price = random.uniform(100, 500)
    
    # Création d'une fausse courbe historique (Random Walk)
    dates = pd.date_range(end=datetime.datetime.today(), periods=30)
    prices = [base_price]
    for _ in range(29):
        change = random.uniform(-5, 5) # Variation entre -5 et +5 $
        prices.append(max(prices[-1] + change, 10)) # On évite le prix négatif
    
    hist = pd.Series(prices, index=dates, name="Close")
    
    return {
        "Ticker": ticker,
        "Prix": prices[-1],
        "History": hist,
        "Catégorie": "Simulé (Demo)",
        "Timing": random.randint(40, 90),
        "Verdict": "Analyse Démo (Yahoo Bloqué)",
        "Détails": f"""
        - ⚠️ **Yahoo Finance ne répond pas** (Rate Limit).
        - Données simulées pour la démonstration.
        - Prix fictif : {prices[-1]:.2f} $
        - L'interface reste fonctionnelle pour test.
        """,
        "Source": "⚠️ Mode Démo (Yahoo Sature)"
    }

# --- 3. FONCTION PRINCIPALE ---
@st.cache_data(ttl=3600)
def analyze_stock(ticker):
    ticker = ticker.strip().upper()
    
    # 1. TENTATIVE YAHOO (VRAIES DONNÉES)
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")
        info = stock.info
        
        # Si Yahoo renvoie un dictionnaire vide ou pas de prix -> Erreur
        if hist.empty or not info:
            raise Exception("Données Yahoo vides")
            
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or hist['Close'].iloc[-1]
        
        # Si on arrive ici, Yahoo marche ! On tente OpenAI.
        try:
            if not client: raise Exception("Pas de clé OpenAI")
            
            prompt = f"Action {ticker}, Prix {current_price}. Secteur {info.get('sector')}. Analyse en JSON (category, verdict, details)."
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150
            )
            content = response.choices[0].message.content
            # Extraction JSON simple
            start = content.find('{')
            end = content.rfind('}') + 1
            ai_data = json.loads(content[start:end])
            
            return {
                "Ticker": ticker,
                "Prix": current_price,
                "History": hist['Close'],
                "Catégorie": ai_data.get("category", "Tech"),
                "Timing": 75, # Score par défaut si API simple
                "Verdict": ai_data.get("verdict", "Analyse OK"),
                "Détails": ai_data.get("details", "- Analyse fondamentale OK"),
                "Source": "✅ Données Réelles"
            }
            
        except Exception:
            # Yahoo marche mais pas OpenAI -> Fallback Technique
            return {
                "Ticker": ticker,
                "Prix": current_price,
                "History": hist['Close'],
                "Catégorie": info.get('sector', 'Autre'),
                "Timing": 50,
                "Verdict": "Données Yahoo OK (Sans IA)",
                "Détails": "- OpenAI indisponible\n- Prix réel récupéré",
                "Source": "⚠️ Yahoo Seul (Pas d'IA)"
            }

    except Exception as e:
        # 2. SI TOUT PLANTE -> MODE DÉMO
        # On ne veut pas que le site crashe, on veut montrer l'UI.
        return get_mock_data(ticker)

# --- 4. INTERFACE ---
st.title("🤖 AI Strategic Hunter")
st.caption("Version Portfolio • Auto-Switch Demo Mode")

with st.sidebar:
    st.header("Portefeuille")
    raw_text = st.text_area("Tickers", "NVDA PLTR") 
    tickers = [t.strip() for t in raw_text.replace(',',' ').split() if t.strip()]
    launch = st.button("🚀 Analyser")

if launch and tickers:
    for t in tickers:
        with st.spinner(f"Analyse de {t}..."):
            data = analyze_stock(t)
            time.sleep(0.5) # Petite pause pour l'effet visuel
            
        if data:
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 2, 1])
                with c1:
                    st.metric(label=data['Ticker'], value=f"{data['Prix']:.2f} $")
                    # Badge de couleur selon la source
                    if "Réelles" in data['Source']:
                        st.success(data['Source'])
                    else:
                        st.warning(data['Source'])
                        
                with c2:
                    if data['History'] is not None:
                        st.line_chart(data['History'], height=80)
                with c3:
                    score = data.get('Timing', 50)
                    st.progress(score/100, text=f"Score: {score}/100")
                    st.write(f"**{data['Verdict']}**")
                
                with st.expander(f"Détails {data['Ticker']}"):
                    st.markdown(data['Détails'])