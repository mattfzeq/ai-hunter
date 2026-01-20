import streamlit as st
import os
import time
import yfinance as yf
from openai import OpenAI
import json
import pandas as pd
import random
import datetime
import re

# --- 1. CONFIGURATION TERMINAL ---
st.set_page_config(
    layout="wide", 
    page_title="AI Strategic Hunter v17.1",
    page_icon="🦅",
    initial_sidebar_state="expanded"
)

# --- CSS PRO (Bloomberg Terminal Style) ---
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 5rem;}
    div[data-testid="stMetricValue"] {font-size: 1.4rem !important;}
    .stCard {background-color: #0e1117; border: 1px solid #303030;}
    div[data-testid="stDownloadButton"] button {
        width: 100%;
        border-color: #4CAF50;
        color: #4CAF50;
    }
    .score-bar {
        width: 100%;
        height: 8px;
        border-radius: 4px;
        background-color: #1e1e1e;
        overflow: hidden;
        margin-top: 5px;
    }
    .score-fill {
        height: 100%;
        transition: width 0.3s ease;
    }
    .score-red { background: linear-gradient(90deg, #ff4444, #cc0000); }
    .score-orange { background: linear-gradient(90deg, #ff9933, #ff6600); }
    .score-green { background: linear-gradient(90deg, #00ff88, #00cc66); }
    .stChatMessage {
        background-color: #1a1a1a;
        border-left: 3px solid #29b5e8;
    }
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

# --- INIT API ---
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

# --- INIT STATE ---
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = {}

# CORRECTION DU BUG "BOUTON OUBLIEUX"
if 'analysis_active' not in st.session_state:
    st.session_state['analysis_active'] = False

# --- 2. UTILITAIRES ---

def extract_json_safe(text):
    """Extraction sécurisée du JSON"""
    try:
        return json.loads(text)
    except:
        try:
            match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
            if match: return json.loads(match.group(0))
            else: raise Exception("No JSON")
        except:
            return {}

def render_score_bar(score):
    if score < 50: color = "score-red"
    elif score < 70: color = "score-orange"
    else: color = "score-green"
    return f'<div class="score-bar"><div class="score-fill {color}" style="width: {score}%"></div></div>'

# --- 3. MOTEUR CHAT (RAG) ---

def build_context_prompt(ticker, data):
    micro = data['Micro']
    return f"""Analyste expert sur {ticker}.
CONTEXTE:
- Prix: ${data['Prix']:.2f} ({data['Change']:.2f}%)
- Score: {data['Score']}/100 ({data['Verdict']})
- Thèse: {data['Thesis']}
- Risque: {data['Risque']}
- PE: {micro.get('PE Ratio')} | Marge: {micro.get('Profit Margin')} | Growth: {micro.get('Revenue YoY')}
DIRECTIVES: Réponse courte, style Bloomberg. Base-toi sur ces chiffres."""

def chat_with_analyst(ticker, data, user_message):
    try:
        if not client: return "❌ API Key manquante."
        
        system_prompt = build_context_prompt(ticker, data)
        history = st.session_state['chat_history'].get(ticker, [])
        
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-6:]: # Contexte court
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=300,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Erreur IA: {str(e)[:50]}"

# --- 4. DATA ENGINE (FALLBACK) ---

def generate_rich_mock_data(ticker):
    base = random.uniform(50, 800)
    prices = [base * random.uniform(0.98, 1.02) for _ in range(30)]
    return {
        "Ticker": ticker, "Prix": prices[-1], 
        "Change": (prices[-1]-prices[0])/prices[0]*100,
        "History": pd.DataFrame({"Close": prices}),
        "Sector": "Simulated Tech",
        "Micro": {"Market Cap": "100B", "PE Ratio": "25.4", "Profit Margin": "15%", "Revenue YoY": "+10%"},
        "Score": 75, "Verdict": "BUY (SIM)", "Thesis": "Strong momentum in simulation.", "Risque": "Simulation",
        "Source": "⚠️ Simulation"
    }

@st.cache_data(ttl=600)
def analyze_stock_pro(ticker):
    ticker = ticker.strip().upper()
    try:
        time.sleep(random.uniform(0.5, 1.5)) # Anti-ban léger
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")
        if hist.empty: raise Exception("Yahoo Empty")
        
        info = stock.info
        current = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[0]
        
        micro = {
            "Market Cap": f"{info.get('marketCap', 0)/1e9:.1f}B",
            "PE Ratio": f"{info.get('trailingPE', 0):.1f}",
            "PEG": f"{info.get('pegRatio', 0):.2f}",
            "EPS": f"{info.get('trailingEps', 0):.2f}",
            "Div Yield": f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "0%",
            "Beta": f"{info.get('beta', 0):.2f}",
            "Profit Margin": f"{info.get('profitMargins', 0)*100:.1f}%",
            "Revenue YoY": f"{info.get('revenueGrowth', 0)*100:.1f}%"
        }
        
        # IA Analysis
        try:
            if not client: raise Exception("No Key")
            prompt = f"Analyze {ticker}. Price {current}. Json output: {{'verdict': 'BUY/HOLD/SELL', 'score': 75, 'thesis': 'short sentence', 'risk': '1 word'}}"
            resp = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
            ai_data = extract_json_safe(resp.choices[0].message.content)
            
            return {
                "Ticker": ticker, "Prix": current, "Change": ((current-prev)/prev)*100,
                "History": hist, "Sector": info.get('sector', 'N/A'), "Micro": micro,
                "Score": ai_data.get('score', 50), "Verdict": ai_data.get('verdict', 'NEUTRE'),
                "Thesis": ai_data.get('thesis', 'N/A'), "Risque": ai_data.get('risk', 'N/A'),
                "Source": "✅ Données Réelles"
            }
        except:
            return {**generate_rich_mock_data(ticker), "Source": "⚠️ Yahoo (No IA)"}
            
    except:
        return generate_rich_mock_data(ticker)

# --- 5. INTERFACE ---

col1, col2, col3, col4 = st.columns(4)
col1.metric("S&P 500", "4890", "+0.45%")
col2.metric("NASDAQ", "15450", "+0.80%")
col3.metric("EUR/USD", "1.08", "-0.12%")
col4.metric("BTC", "64230", "+2.40%")
st.divider()

with st.sidebar:
    st.title("🦅 HUNTER V17.1")
    st.caption("Stable + Chat Fix")
    
    input_tickers = st.text_area("Watchlist", "NVDA PLTR")
    raw_tickers = [t.strip().upper() for t in input_tickers.replace(',',' ').split() if t.strip()]
    tickers = list(dict.fromkeys(raw_tickers)) # Dédoublonnage
    
    st.markdown("---")
    
    # CORRECTION : Le bouton active une variable de session persistante
    if st.button("RUN ANALYSIS 🚀", type="primary", use_container_width=True):
        st.session_state['analysis_active'] = True

    export_placeholder = st.empty()

# CORRECTION : On vérifie la variable persistante, pas juste le bouton
if st.session_state['analysis_active'] and tickers:
    report_data = []
    
    for t in tickers:
        data = analyze_stock_pro(t)
        
        with st.container(border=True):
            # Header & Metrics
            c1, c2, c3 = st.columns([2, 4, 2])
            c1.markdown(f"## {data['Ticker']}"); c1.caption(data['Sector'])
            c2.metric("Prix", f"{data['Prix']:.2f} $", f"{data['Change']:.2f} %", delta_color="normal" if data['Change']>0 else "inverse")
            c3.metric("Score", f"{data['Score']}/100", data['Verdict'])
            c3.markdown(render_score_bar(data['Score']), unsafe_allow_html=True)
            
            # Financials Grid
            st.markdown("#### 🔢 Financials")
            m = data['Micro']
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("Mkt Cap", m.get('Market Cap'), border=True)
            f2.metric("PE Ratio", m.get('PE Ratio'), border=True)
            f3.metric("Margin", m.get('Profit Margin'), border=True)
            f4.metric("Beta", m.get('Beta'), border=True)
            
            # Chart & Thesis
            st.markdown("---")
            g1, g2 = st.columns([2, 1])
            g1.area_chart(data['History']['Close'], height=200, color="#29b5e8")
            with g2:
                st.info(data['Thesis'])
                st.write(f"**Risque:** {data['Risque']}")
                if "Simulation" in data['Source']: st.caption("⚠️ Simulation")

            # --- CHAT STABLE ---
            with st.expander(f"💬 Discuter avec l'Analyste [{data['Ticker']}]"):
                # Init history
                if data['Ticker'] not in st.session_state['chat_history']:
                    st.session_state['chat_history'][data['Ticker']] = []
                
                # A. Affichage Historique
                for msg in st.session_state['chat_history'][data['Ticker']]:
                    st.chat_message(msg["role"]).write(msg["content"])
                
                # B. Input & Traitement
                if prompt := st.chat_input("Posez une question...", key=f"chat_{data['Ticker']}"):
                    # Affiche User
                    st.chat_message("user").write(prompt)
                    st.session_state['chat_history'][data['Ticker']].append({"role": "user", "content": prompt})
                    
                    # Génère et Affiche AI
                    with st.chat_message("assistant"):
                        with st.spinner("Analyse..."):
                            response = chat_with_analyst(data['Ticker'], data, prompt)
                            st.write(response)
                            st.session_state['chat_history'][data['Ticker']].append({"role": "assistant", "content": response})

        # Data for Export
        report_data.append({"Ticker": t, "Price": data['Prix'], "Score": data['Score'], "Verdict": data['Verdict']})

    # Export Button
    if report_data:
        df = pd.DataFrame(report_data)
        csv = df.to_csv(index=False).encode('utf-8')
        with export_placeholder.container():
            st.success("✅ Terminée")
            st.download_button("📥 CSV Report", csv, "report.csv", "text/csv")