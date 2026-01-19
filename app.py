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
    page_title="AI Strategic Hunter v15",
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
    /* Score Bar Custom Styles */
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

# --- 2. UTILITAIRES DE SÉCURITÉ ---

def extract_json_safe(text):
    """
    Extraction sécurisée du JSON depuis la réponse OpenAI.
    Gère les cas où l'IA ajoute du texte avant/après le JSON.
    """
    try:
        # Tentative 1 : Parse direct
        return json.loads(text)
    except:
        try:
            # Tentative 2 : Extraction par regex du premier objet JSON trouvé
            match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
            if match:
                json_str = match.group(0)
                return json.loads(json_str)
            else:
                raise Exception("No JSON found")
        except:
            # Tentative 3 : Recherche manuelle des accolades
            try:
                start = text.index('{')
                end = text.rindex('}') + 1
                return json.loads(text[start:end])
            except:
                # Échec total -> Retourne un objet vide pour déclencher le fallback
                return {}

def render_score_bar(score):
    """
    Génère une barre de progression HTML colorée selon le score.
    Rouge < 50, Orange < 70, Vert >= 70
    """
    if score < 50:
        color_class = "score-red"
    elif score < 70:
        color_class = "score-orange"
    else:
        color_class = "score-green"
    
    html = f"""
    <div class="score-bar">
        <div class="score-fill {color_class}" style="width: {score}%"></div>
    </div>
    """
    return html

# --- 3. MOTEUR DE DONNÉES ---

def generate_rich_mock_data(ticker):
    """Données de simulation riches (Fallback Mode)"""
    base = random.uniform(50, 800)
    prices = [base]
    for _ in range(50): 
        prices.append(prices[-1] * random.uniform(0.98, 1.02))
    
    micro = {
        "Market Cap": f"{random.uniform(50, 2000):.1f}B",
        "PE Ratio": f"{random.uniform(15, 80):.1f}",
        "PEG": f"{random.uniform(0.8, 3.0):.2f}",
        "EPS": f"{random.uniform(2, 15):.2f}",
        "Div Yield": f"{random.uniform(0, 4):.2f}%",
        "Beta": f"{random.uniform(0.8, 2.5):.2f}",
        "Profit Margin": f"{random.uniform(10, 40):.1f}%",
        "Revenue YoY": f"+{random.uniform(5, 50):.1f}%"
    }
    
    return {
        "Ticker": ticker,
        "Prix": prices[-1],
        "Change": (prices[-1] - prices[0]) / prices[0] * 100,
        "History": pd.DataFrame({"Close": prices}),
        "Sector": "Technology (Simulated)",
        "Micro": micro,
        "Score": random.randint(40, 95),
        "Verdict": "ACHAT (SIMULÉ)",
        "Thesis": f"Simulation : {ticker} présente une opportunité technique intéressante dans un contexte de volatilité maîtrisée.",
        "Risque": "Volatilité API",
        "Source": "⚠️ Simulation"
    }

@st.cache_data(ttl=600)
def analyze_stock_pro(ticker):
    """
    Analyse principale avec Graceful Degradation.
    v15 : Ajout du throttling Yahoo et parsing JSON sécurisé.
    """
    ticker = ticker.strip().upper()
    
    try:
        # ANTI-BAN : Throttling aléatoire (1-2 secondes)
        time.sleep(random.uniform(1.0, 2.0))
        
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")
        info = stock.info
        
        if hist.empty: 
            raise Exception("Yahoo Empty")
        
        current = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[0]
        change = ((current - prev) / prev) * 100
        
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
        
        # ANALYSE IA (avec parsing JSON sécurisé)
        try:
            if not client: 
                raise Exception("No Key")
            
            prompt = f"Analyse flash {ticker}. Prix {current}. Secteur {info.get('sector')}. Output JSON strict: {{'verdict': 'BUY/HOLD/SELL', 'score': 75, 'thesis': '1 phrase', 'risk': '1 mot'}}"
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo", 
                messages=[{"role": "user", "content": prompt}]
            )
            
            # PARSING SÉCURISÉ v15
            raw_text = response.choices[0].message.content
            ai_data = extract_json_safe(raw_text)
            
            # Validation des clés essentielles
            if not all(k in ai_data for k in ['verdict', 'score', 'thesis', 'risk']):
                raise Exception("Incomplete JSON")
            
            verdict = ai_data.get('verdict')
            thesis = ai_data.get('thesis')
            score = ai_data.get('score')
            risk = ai_data.get('risk')
            source = "✅ Données Réelles"
            
        except Exception as e:
            # FALLBACK IA (pas de crash)
            verdict = "NEUTRE"
            thesis = "Analyse technique seule (IA indisponible)."
            score = 50
            risk = "N/A"
            source = "⚠️ Yahoo (No IA)"

        return {
            "Ticker": ticker, 
            "Prix": current, 
            "Change": change,
            "History": hist, 
            "Sector": info.get('sector', 'N/A'),
            "Micro": micro, 
            "Score": score, 
            "Verdict": verdict,
            "Thesis": thesis, 
            "Risque": risk, 
            "Source": source
        }

    except Exception:
        # FALLBACK TOTAL (Mode Simulation)
        return generate_rich_mock_data(ticker)

# --- 4. INTERFACE TERMINAL ---

# BANDEAU MACRO
col_t1, col_t2, col_t3, col_t4 = st.columns(4)
with col_t1: st.metric("S&P 500", "4,890.23", "+0.45%")
with col_t2: st.metric("NASDAQ", "15,450.10", "+0.80%")
with col_t3: st.metric("EUR/USD", "1.0850", "-0.12%")
with col_t4: st.metric("BTC/USD", "64,230.00", "+2.40%")
st.divider()

# SIDEBAR (Contrôles)
with st.sidebar:
    st.title("🦅 HUNTER V15")
    st.caption("Hardened Edition")
    
    input_tickers = st.text_area("Watchlist", "NVDA PLTR AMD")
    tickers = [t.strip() for t in input_tickers.replace(',',' ').split() if t.strip()]
    
    st.markdown("---")
    run_btn = st.button("RUN ANALYSIS 🚀", type="primary", use_container_width=True)
    
    # Placeholder pour le bouton d'export
    export_placeholder = st.empty()

# MAIN CONTENT
if run_btn and tickers:
    report_data = []
    
    for t in tickers:
        data = analyze_stock_pro(t)
        
        # CARD DESIGN (Bloomberg Terminal Style)
        with st.container(border=True):
            # HEADER
            c_head1, c_head2, c_head3 = st.columns([2, 4, 2])
            with c_head1:
                st.markdown(f"## {data['Ticker']}")
                st.caption(data['Sector'])
            with c_head2:
                delta_color = "normal" if data['Change'] > 0 else "inverse"
                st.metric("Prix Actuel", f"{data['Prix']:.2f} $", f"{data['Change']:.2f} %", delta_color=delta_color)
            with c_head3:
                st.metric("AI Score", f"{data['Score']}/100", data['Verdict'])
                st.markdown(render_score_bar(data['Score']), unsafe_allow_html=True)

            st.markdown("#### 🔢 Key Financials")
            m = data['Micro']
            
            # REFONTE UI : Metrics compactes au lieu de st.write
            k1, k2, k3, k4 = st.columns(4)
            with k1: 
                st.metric("Market Cap", m.get('Market Cap'), border=True)
                st.metric("Beta", m.get('Beta'), border=True)
            with k2: 
                st.metric("PE Ratio", m.get('PE Ratio'), border=True)
                st.metric("EPS", m.get('EPS'), border=True)
            with k3: 
                st.metric("Profit Margin", m.get('Profit Margin'), border=True)
                st.metric("Revenue YoY", m.get('Revenue YoY'), border=True)
            with k4: 
                st.metric("PEG Ratio", m.get('PEG'), border=True)
                st.metric("Div Yield", m.get('Div Yield'), border=True)

            st.markdown("---")
            g1, g2 = st.columns([2, 1])
            with g1: 
                st.area_chart(data['History']['Close'], height=200, color="#29b5e8")
            with g2:
                st.info(data['Thesis'])
                st.write(f"**Risque:** {data['Risque']}")
                if "Simulation" in data['Source']: 
                    st.caption("⚠️ Simulation Mode")

        # Ajout des données au rapport CSV
        report_data.append({
            "Ticker": t,
            "Price": f"{data['Prix']:.2f}",
            "Change %": f"{data['Change']:.2f}",
            "Verdict": data['Verdict'],
            "Score": data['Score'],
            "Thesis": data['Thesis'],
            "PE Ratio": data['Micro'].get('PE Ratio'),
            "Source": data['Source']
        })

    # --- GÉNÉRATION DU RAPPORT (SIDEBAR) ---
    if report_data:
        df = pd.DataFrame(report_data)
        csv = df.to_csv(index=False).encode('utf-8')
        
        with export_placeholder.container():
            st.success("✅ Analyse Terminée")
            st.download_button(
                label="📥 TÉLÉCHARGER RAPPORT (CSV)",
                data=csv,
                file_name=f"Hunter_Report_{datetime.date.today()}.csv",
                mime="text/csv",
            )
            
            st.markdown("---")
            st.markdown("**📧 Email Briefing:**")
            st.code(f"Analyse terminée sur {len(tickers)} actifs. Tendance globale: {'Haussière' if df['Change %'].astype(float).mean() > 0 else 'Mixte'}. Top pick: {df.loc[df['Score'].idxmax()]['Ticker']}.", language="text")