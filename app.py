import streamlit as st
import os
import time
import yfinance as yf
from openai import OpenAI
import json
import pandas as pd
import random

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

# --- 2. FONCTIONS ---
@st.cache_data(ttl=3600)
def analyze_stock(ticker):
    # Initialisation des variables
    ticker = ticker.strip().upper()
    stock = yf.Ticker(ticker)
    
    # --- A. RÉCUPÉRATION DONNÉES (Yahoo) ---
    try:
        hist = stock.history(period="6mo")
        info = stock.info
        
        # Prix actuel
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not current_price and not hist.empty:
            current_price = hist['Close'].iloc[-1]
            
        if not current_price:
            return {"Error": f"Prix introuvable pour {ticker}"}

        # Calcul simple de tendance (Maths pures)
        start_price = hist['Close'].iloc[0] if not hist.empty else current_price
        variation = ((current_price - start_price) / start_price) * 100
        is_bullish = variation > 0

    except Exception as e:
        return {"Error": f"Erreur Yahoo: {e}"}

    # --- B. TENTATIVE IA (Prompt Ultra-Léger) ---
    ai_data = None
    ai_error = None
    
    if client:
        try:
            # Prompt minimaliste pour économiser les tokens
            prompt = f"""
            Action: {ticker}. Secteur: {info.get('sector','Tech')}.
            Analyse JSON stricte:
            {{
                "category": "Catégorie (1 mot)",
                "verdict": "Verdict (1 phrase)",
                "details": "3 points clés"
            }}
            """
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150 # On coupe la parole si c'est trop long
            )
            content = response.choices[0].message.content
            # Extraction JSON artisanale
            if "{" in content and "}" in content:
                json_str = content[content.find('{'):content.rfind('}')+1]
                ai_data = json.loads(json_str)
                
        except Exception as e:
            ai_error = str(e) # On note l'erreur mais on ne plante pas !

    # --- C. CONSTRUCTION DU RÉSULTAT (Hybride) ---
    
    # Si l'IA a marché, on prend ses données
    if ai_data:
        category = ai_data.get("category", "Tech")
        verdict = ai_data.get("verdict", "Analyse IA complétée")
        details = ai_data.get("details", "- Analyse fondamentale OK")
        timing = 85 if is_bullish else 30
        source = "✅ Analyse IA (GPT-3.5)"
        
    # SINON : On génère une analyse technique automatique (Mode Secours)
    else:
        category = info.get('sector', 'Technologie')
        trend_str = "Haussière" if is_bullish else "Baissière"
        verdict = f"Tendance {trend_str} de {variation:.1f}% sur 6 mois."
        details = f"""
        - ⚠️ Mode Secours (Quota OpenAI dépassé ou Erreur)
        - Prix actuel : {current_price:.2f} $
        - Performance 6 mois : {variation:.2f} %
        - L'analyse fondamentale IA est temporairement indisponible.
        """
        timing = int(min(max(50 + variation, 0), 100)) # Score basé sur la perf
        source = "⚠️ Analyse Technique (Mode Secours)"

    return {
        "Ticker": ticker,
        "Prix": current_price,
        "History": hist['Close'] if not hist.empty else None,
        "Catégorie": category,
        "Timing": timing,
        "Verdict": verdict,
        "Détails": details,
        "Source": source
    }

# --- 3. INTERFACE ---
st.title("🤖 AI Strategic Hunter")
st.caption("Version Indestructible • Fallback Auto")

with st.sidebar:
    st.header("Portefeuille")
    raw_text = st.text_area("Tickers", "NVDA") 
    tickers = [t.strip() for t in raw_text.replace(',',' ').split() if t.strip()]
    launch = st.button("🚀 Analyser")

if launch and tickers:
    for t in tickers:
        with st.spinner(f"Analyse de {t}..."):
            data = analyze_stock(t)
            time.sleep(0.5)
            
        if data and "Error" not in data:
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 2, 1])
                with c1:
                    st.metric(label=data['Ticker'], value=f"{data['Prix']:.2f} $")
                    st.caption(data['Source']) # Affiche si c'est GPT ou Secours
                with c2:
                    if data['History'] is not None:
                        st.line_chart(data['History'], height=80)
                with c3:
                    score = data.get('Timing', 50)
                    color = "off" if score > 70 else "normal"
                    st.progress(score/100, text=f"Score: {score}/100")
                    st.write(f"**{data['Verdict']}**")
                
                with st.expander(f"Détails {data['Ticker']}"):
                    st.markdown(data['Détails'])
        elif data:
             st.error(data["Error"])