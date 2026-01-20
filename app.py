import streamlit as st
import os
import time
import requests  # Nouvelle librairie pour l'API
from openai import OpenAI
import json
import pandas as pd
import random
import datetime
import re

# --- 1. CONFIGURATION TERMINAL ---
st.set_page_config(
    layout="wide", 
    page_title="AI Strategic Hunter v18 (Pro)",
    page_icon="🦅",
    initial_sidebar_state="expanded"
)

# --- CSS PRO ---
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 5rem;}
    div[data-testid="stMetricValue"] {font-size: 1.4rem !important;}
    .stCard {background-color: #0e1117; border: 1px solid #303030;}
    div[data-testid="stDownloadButton"] button {
        width: 100%; border-color: #4CAF50; color: #4CAF50;
    }
    .score-bar { width: 100%; height: 8px; border-radius: 4px; background-color: #1e1e1e; overflow: hidden; margin-top: 5px; }
    .score-fill { height: 100%; transition: width 0.3s ease; }
    .score-red { background: linear-gradient(90deg, #ff4444, #cc0000); }
    .score-orange { background: linear-gradient(90deg, #ff9933, #ff6600); }
    .score-green { background: linear-gradient(90deg, #00ff88, #00cc66); }
    .stChatMessage { background-color: #1a1a1a; border-left: 3px solid #29b5e8; }
</style>
""", unsafe_allow_html=True)

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# --- SÉCURITÉ ---
if "password_correct" not in st.session_state:
    st.session_state.password_correct = False

def check_password():
    if st.session_state.password_correct: return True
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.subheader("🔒 Terminal Access")
        pwd = st.text_input("Password", type="password")
        if st.button("Connect"):
            if pwd == os.getenv("APP_PASSWORD", "admin123"):
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Access Denied")
    return False

if not check_password(): st.stop()

# --- CLÉS API ---
openai_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_key) if openai_key else None

# ⚠️ REMPLACEZ CECI PAR VOTRE CLÉ FMP OU METTEZ-LA DANS .ENV
fmp_key = os.getenv("qekt69FL5hOYhieKn1KBDA0TUQZdAjAW", "DEMO") # Mettez votre clé ici si pas de .env

# --- INIT STATE ---
if 'chat_history' not in st.session_state: st.session_state['chat_history'] = {}
if 'analysis_active' not in st.session_state: st.session_state['analysis_active'] = False

# --- 2. UTILITAIRES ---

def extract_json_safe(text):
    try: return json.loads(text)
    except:
        try:
            match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
            if match: return json.loads(match.group(0))
            else: return {}
        except: return {}

def render_score_bar(score):
    if score < 50: color = "score-red"
    elif score < 70: color = "score-orange"
    else: color = "score-green"
    return f'<div class="score-bar"><div class="score-fill {color}" style="width: {score}%"></div></div>'

def format_large_number(num):
    if not num: return "N/A"
    if num >= 1e9: return f"{num/1e9:.2f}B"
    if num >= 1e6: return f"{num/1e6:.2f}M"
    return f"{num:.2f}"

# --- 3. MOTEUR FMP (DATA RÉELLE) ---

def get_fmp_data(ticker):
    """Récupère les données VRAIES depuis Financial Modeling Prep"""
    if fmp_key == "DEMO" and ticker != "AAPL":
        return None # La clé DEMO ne marche que pour AAPL souvent
    
    try:
        # 1. Profil (Prix, Beta, Secteur, Description)
        url_profile = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={fmp_key}"
        profile = requests.get(url_profile).json()
        
        if not profile: return None # Ticker invalide
        p = profile[0]

        # 2. Ratios Clés (PE, Marges) - Optionnel si quota limité, profil a déjà bcp
        # On utilise les données du profil pour économiser les requêtes
        
        # 3. Historique (pour le graph)
        url_hist = f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}?timeseries=30&apikey={fmp_key}"
        hist_data = requests.get(url_hist).json()
        
        prices = []
        if 'historical' in hist_data:
            # FMP donne du plus récent au plus vieux, on inverse
            hist_list = hist_data['historical'][::-1]
            prices = [day['close'] for day in hist_list]
        
        return {
            "profile": p,
            "history": prices
        }
    except Exception as e:
        print(f"Erreur FMP: {e}")
        return None

# --- 4. MOTEUR ANALYSE ---

def analyze_stock_real(ticker):
    ticker = ticker.strip().upper()
    
    # A. TENTATIVE API PRO (FMP)
    fmp_data = get_fmp_data(ticker)
    
    if fmp_data:
        p = fmp_data['profile']
        prices = fmp_data['history']
        
        # Calcul variation
        current_price = p.get('price', 0)
        # Variation du jour (si dispo) ou calculée
        change_pct = p.get('changes', 0)
        
        # Construction Micro Data RÉELLE
        micro = {
            "Market Cap": format_large_number(p.get('mktCap')),
            "PE Ratio": f"{p.get('lastDiv', 0):.2f}" if p.get('lastDiv') else "N/A", # FMP Profile donne parfois dividend pas PE direct, on adapte
            "Beta": f"{p.get('beta', 0):.2f}",
            "Volume": format_large_number(p.get('volAvg')),
            "Sector": p.get('sector', 'N/A'),
            "Industry": p.get('industry', 'N/A'),
            "CEO": p.get('ceo', 'N/A'),
            "Website": p.get('website', 'N/A'),
            "Description": p.get('description', '')
        }

        # B. ANALYSE IA SUR DONNÉES RÉELLES
        try:
            if not client: raise Exception("No OpenAI Key")
            
            # Prompt enrichi avec la description officielle de la boîte
            prompt = f"""
            Analyse EXPERTE de {ticker}.
            Données Officielles:
            - Prix: {current_price} ({change_pct}%)
            - Secteur: {micro['Sector']}
            - Activité: {micro['Description'][:200]}...
            
            Tâche: Json output strict: {{'verdict': 'ACHAT/NEUTRE/VENTE', 'score': 75, 'thesis': '1 phrase percutante', 'risk': '1 mot'}}
            """
            resp = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
            ai_data = extract_json_safe(resp.choices[0].message.content)
            
            return {
                "Ticker": ticker, "Prix": current_price, "Change": change_pct,
                "History": pd.DataFrame({"Close": prices}) if prices else None,
                "Sector": micro['Sector'], "Micro": micro,
                "Score": ai_data.get('score', 50), "Verdict": ai_data.get('verdict', 'NEUTRE'),
                "Thesis": ai_data.get('thesis', 'Analyse fondamentale basée sur les données FMP.'),
                "Risque": ai_data.get('risk', 'Marché'),
                "Source": "🌟 Données FMP (Pro)"
            }
        except:
            # Si IA échoue mais FMP marche
            return {
                "Ticker": ticker, "Prix": current_price, "Change": change_pct,
                "History": pd.DataFrame({"Close": prices}) if prices else None,
                "Sector": micro['Sector'], "Micro": micro,
                "Score": 50, "Verdict": "DONNÉES SEULES", "Thesis": "IA non disponible.", "Risque": "N/A",
                "Source": "✅ FMP (Sans IA)"
            }

    # C. FALLBACK SIMULATION (Si clé invalide ou quota dépassé)
    else:
        return generate_rich_mock_data(ticker)

def generate_rich_mock_data(ticker):
    """Fallback si l'API Pro échoue"""
    base = random.uniform(50, 800)
    prices = [base * random.uniform(0.98, 1.02) for _ in range(30)]
    return {
        "Ticker": ticker, "Prix": prices[-1], 
        "Change": (prices[-1]-prices[0])/prices[0]*100,
        "History": pd.DataFrame({"Close": prices}),
        "Sector": "Technology (Simulated)",
        "Micro": {"Market Cap": "Simulated", "PE Ratio": "25.0", "Beta": "1.2", "Volume": "10M"},
        "Score": 75, "Verdict": "BUY (SIM)", "Thesis": "Simulation (Vérifiez votre clé API FMP).", "Risque": "Simulation",
        "Source": "⚠️ Simulation (Clé API Manquante)"
    }

# --- 5. CHAT ENGINE ---
def chat_with_analyst(ticker, data, user_message):
    try:
        if not client: return "❌ OpenAI Key manquante."
        context = f"Action: {ticker}. Prix: {data['Prix']}. Thèse: {data['Thesis']}. Description: {data['Micro'].get('Description', 'N/A')}"
        
        history = st.session_state['chat_history'].get(ticker, [])
        messages = [{"role": "system", "content": f"Tu es un expert financier. Contexte: {context}"}]
        for msg in history[-6:]: messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        
        response = client.chat.completions.create(model="gpt-3.5-turbo", messages=messages)
        return response.choices[0].message.content
    except Exception as e: return f"Erreur: {e}"

# --- 6. INTERFACE ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("API Status", "En Ligne" if fmp_key != "DEMO" else "Mode Démo", border=True)

with st.sidebar:
    st.title("🦅 HUNTER V18")
    st.caption("Pro API Edition")
    if fmp_key == "DEMO": st.warning("⚠️ Clé FMP manquante. Utilisez .env")
    
    input_tickers = st.text_area("Watchlist", "AAPL MSFT GOOGL") # AAPL marche souvent sans clé
    raw_tickers = [t.strip().upper() for t in input_tickers.replace(',',' ').split() if t.strip()]
    tickers = list(dict.fromkeys(raw_tickers))
    
    if st.button("RUN ANALYSIS 🚀", type="primary", use_container_width=True):
        st.session_state['analysis_active'] = True

if st.session_state['analysis_active'] and tickers:
    for t in tickers:
        data = analyze_stock_real(t)
        
        with st.container(border=True):
            # Header
            c1, c2, c3 = st.columns([2, 4, 2])
            c1.markdown(f"## {data['Ticker']}"); c1.caption(data['Sector'])
            c2.metric("Prix", f"{data['Prix']:.2f} $", f"{data['Change']:.2f} %", delta_color="normal" if data['Change']>0 else "inverse")
            c3.metric("Score", f"{data['Score']}/100", data['Verdict'])
            c3.markdown(render_score_bar(data['Score']), unsafe_allow_html=True)
            
            # Financials
            st.markdown("#### 📊 Données Fondamentales")
            m = data['Micro']
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("Mkt Cap", m.get('Market Cap'), border=True)
            f2.metric("Beta", m.get('Beta'), border=True)
            f3.metric("Vol. Moy", m.get('Volume'), border=True)
            f4.metric("Industrie", m.get('Industry')[:15]+"...", help=m.get('Industry'), border=True)
            
            # Description (Nouvelle Feature API Pro !)
            with st.expander("🏢 Profil Société"):
                st.write(m.get('Description'))
                st.caption(f"CEO: {m.get('CEO')} | Site: {m.get('Website')}")

            # Chart
            st.markdown("---")
            if data['History'] is not None and not data['History'].empty:
                st.area_chart(data['History']['Close'], height=200, color="#29b5e8")
            
            # Thesis
            st.info(data['Thesis'])
            if "Simulation" in data['Source']: st.caption("⚠️ " + data['Source'])
            else: st.caption("🌟 Données Certifiées FMP")

            # Chat
            with st.expander(f"💬 Chat Analyste [{data['Ticker']}]"):
                if data['Ticker'] not in st.session_state['chat_history']: st.session_state['chat_history'][data['Ticker']] = []
                for msg in st.session_state['chat_history'][data['Ticker']]: st.chat_message(msg["role"]).write(msg["content"])
                
                if prompt := st.chat_input("Question...", key=f"chat_{data['Ticker']}"):
                    st.chat_message("user").write(prompt)
                    st.session_state['chat_history'][data['Ticker']].append({"role": "user", "content": prompt})
                    with st.chat_message("assistant"):
                        with st.spinner("..."):
                            resp = chat_with_analyst(data['Ticker'], data, prompt)
                            st.write(resp)
                            st.session_state['chat_history'][data['Ticker']].append({"role": "assistant", "content": resp})