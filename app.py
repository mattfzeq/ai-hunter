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
import requests

# --- 1. CONFIGURATION TERMINAL ---
st.set_page_config(
    layout="wide", 
    page_title="AI Strategic Hunter v19",
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
    /* Chat Styling */
    .stChatMessage {
        background-color: #1a1a1a;
        border-left: 3px solid #29b5e8;
    }
    /* Reset Button */
    div[data-testid="stButton"] button[kind="secondary"] {
        border-color: #ff4444;
        color: #ff4444;
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

# --- INIT STATE (v19 - PERSISTENCE) ---
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = {}

if 'results' not in st.session_state:
    st.session_state['results'] = None

# --- 2. CONFIGURATION FMP API ---
def get_fmp_api_key():
    """Récupère la clé FMP depuis secrets ou variables d'environnement"""
    try:
        # Tentative 1 : Streamlit Secrets (prioritaire en production)
        return st.secrets.get("FMP_API_KEY")
    except:
        # Tentative 2 : Variable d'environnement (local)
        return os.getenv("FMP_API_KEY")

FMP_API_KEY = get_fmp_api_key()

# --- 3. UTILITAIRES DE SÉCURITÉ ---

def safe_truncate(text, length=15):
    """Tronque une chaîne en gérant le None"""
    if text is None or text == "":
        return "N/A"
    text_str = str(text)
    return text_str[:length] if len(text_str) > length else text_str

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

# --- 4. MOTEUR DE CHAT CONTEXTUEL ---

def build_context_prompt(ticker, data):
    """
    Construit un system prompt enrichi avec toutes les données de l'analyse.
    """
    micro = data['Micro']
    context = f"""Tu es un analyste financier expert spécialisé sur l'action {ticker}.

DONNÉES DE L'ANALYSE EN COURS :
- Ticker: {ticker}
- Secteur: {data.get('Sector', 'N/A')}
- Industrie: {data.get('Industry', 'N/A')}
- Prix Actuel: ${data['Prix']:.2f}
- Variation: {data['Change']:.2f}%
- Score IA: {data['Score']}/100
- Verdict: {data['Verdict']}
- Thèse d'Investissement: {data['Thesis']}
- Risque Principal: {data['Risque']}

MÉTRIQUES FINANCIÈRES :
- Market Cap: {micro.get('Market Cap')}
- PE Ratio: {micro.get('PE Ratio')}
- PEG Ratio: {micro.get('PEG')}
- EPS: {micro.get('EPS')}
- Dividend Yield: {micro.get('Div Yield')}
- Beta: {micro.get('Beta')}
- Profit Margin: {micro.get('Profit Margin')}
- Revenue Growth YoY: {micro.get('Revenue YoY')}

SOURCE DES DONNÉES: {data['Source']}

DIRECTIVES :
- Réponds de manière concise et professionnelle (style Bloomberg Terminal).
- Utilise les données ci-dessus pour répondre aux questions de l'utilisateur.
- Si la question sort du cadre de cette analyse, indique-le poliment.
- Ne jamais inventer de données : base-toi uniquement sur le contexte fourni.
- Si les données sont simulées (Source contains "Simulation"), mentionne-le si pertinent.
"""
    return context

def get_ai_response(ticker, data, user_message, chat_history):
    """
    Génère une réponse de l'IA avec le contexte complet.
    Retourne la réponse ou un message d'erreur.
    """
    try:
        if not client:
            return "❌ Service d'analyse indisponible (clé API OpenAI manquante)."
        
        # Construction du contexte
        system_prompt = build_context_prompt(ticker, data)
        
        # Construction des messages pour l'API
        messages = [{"role": "system", "content": system_prompt}]
        
        # Ajout de l'historique (max 10 derniers messages)
        for msg in chat_history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Ajout du nouveau message utilisateur
        messages.append({"role": "user", "content": user_message})
        
        # Appel API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"❌ Service temporairement indisponible. Erreur: {str(e)[:100]}"

# --- 5. MOTEUR DE DONNÉES ---

def fetch_fmp_data(ticker):
    """
    Récupère les données depuis Financial Modeling Prep API.
    Retourne un dict avec les données ou None en cas d'échec.
    """
    if not FMP_API_KEY:
        return None
    
    try:
        # Profile endpoint
        url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}"
        params = {"apikey": FMP_API_KEY}
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if not data or len(data) == 0:
            return None
        
        profile = data[0]
        
        # Quote endpoint pour le prix actuel
        quote_url = f"https://financialmodelingprep.com/api/v3/quote/{ticker}"
        quote_response = requests.get(quote_url, params=params, timeout=5)
        quote_data = quote_response.json()
        
        current_price = quote_data[0].get('price', 0) if quote_data else profile.get('price', 0)
        change_pct = quote_data[0].get('changesPercentage', 0) if quote_data else 0
        
        return {
            "price": current_price,
            "change": change_pct,
            "marketCap": profile.get('mktCap', 0),
            "pe": profile.get('pe', 0),
            "eps": profile.get('eps', 0),
            "beta": profile.get('beta', 0),
            "sector": profile.get('sector', 'N/A'),
            "industry": profile.get('industry', 'N/A'),
            "description": profile.get('description', ''),
            "ceo": profile.get('ceo', 'N/A'),
            "website": profile.get('website', 'N/A')
        }
        
    except Exception as e:
        return None

def generate_rich_mock_data(ticker):
    """
    Données de simulation riches (Fallback Mode).
    v19 : TOUS les champs nécessaires sont présents.
    """
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
    
    # FIX v19 : Ajout des champs manquants
    return {
        "Ticker": ticker,
        "Prix": prices[-1],
        "Change": (prices[-1] - prices[0]) / prices[0] * 100,
        "History": pd.DataFrame({"Close": prices}),
        "Sector": "Technology (Simulated)",
        "Industry": "Software Infrastructure (Simulated)",  # FIX: Ajout du champ
        "Description": f"Simulation de {ticker} - Données générées pour démonstration.",  # FIX
        "CEO": "Simulated Executive",  # FIX
        "Website": "https://simulation.example.com",  # FIX
        "Micro": micro,
        "Score": random.randint(40, 95),
        "Verdict": "ACHAT (SIMULÉ)",
        "Thesis": f"Simulation : {ticker} présente une opportunité technique intéressante dans un contexte de volatilité maîtrisée.",
        "Risque": "Volatilité API",
        "Source": "⚠️ Simulation"
    }

def analyze_stock_pro(ticker):
    """
    Analyse principale avec Graceful Degradation.
    v19 : Priorité FMP > Yahoo > Mock
    """
    ticker = ticker.strip().upper()
    
    # ANTI-BAN : Throttling aléatoire
    time.sleep(random.uniform(0.5, 1.5))
    
    # TENTATIVE 1 : Financial Modeling Prep (Prioritaire)
    fmp_data = fetch_fmp_data(ticker)
    if fmp_data:
        try:
            current = fmp_data['price']
            change = fmp_data['change']
            
            # Construction des prix historiques (simplifié car FMP nécessite un autre endpoint)
            hist = pd.DataFrame({"Close": [current * random.uniform(0.95, 1.05) for _ in range(50)]})
            
            micro = {
                "Market Cap": f"{fmp_data['marketCap']/1e9:.1f}B" if fmp_data['marketCap'] else "N/A",
                "PE Ratio": f"{fmp_data['pe']:.1f}" if fmp_data['pe'] else "N/A",
                "PEG": "N/A",  # Non disponible dans le profile endpoint
                "EPS": f"{fmp_data['eps']:.2f}" if fmp_data['eps'] else "N/A",
                "Div Yield": "N/A",  # Nécessite un autre endpoint
                "Beta": f"{fmp_data['beta']:.2f}" if fmp_data['beta'] else "N/A",
                "Profit Margin": "N/A",  # Nécessite un autre endpoint
                "Revenue YoY": "N/A"  # Nécessite un autre endpoint
            }
            
            # ANALYSE IA
            try:
                if not client:
                    raise Exception("No Key")
                
                prompt = f"Analyse flash {ticker}. Prix {current}. Secteur {fmp_data['sector']}. Output JSON strict: {{'verdict': 'BUY/HOLD/SELL', 'score': 75, 'thesis': '1 phrase', 'risk': '1 mot'}}"
                
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}]
                )
                
                raw_text = response.choices[0].message.content
                ai_data = extract_json_safe(raw_text)
                
                if not all(k in ai_data for k in ['verdict', 'score', 'thesis', 'risk']):
                    raise Exception("Incomplete JSON")
                
                verdict = ai_data.get('verdict')
                thesis = ai_data.get('thesis')
                score = ai_data.get('score')
                risk = ai_data.get('risk')
                source = "✅ FMP + OpenAI"
                
            except:
                verdict = "NEUTRE"
                thesis = "Analyse technique seule (IA indisponible)."
                score = 50
                risk = "N/A"
                source = "✅ FMP (No IA)"
            
            return {
                "Ticker": ticker,
                "Prix": current,
                "Change": change,
                "History": hist,
                "Sector": fmp_data['sector'],
                "Industry": fmp_data['industry'],
                "Description": safe_truncate(fmp_data['description'], 150),
                "CEO": fmp_data['ceo'],
                "Website": fmp_data['website'],
                "Micro": micro,
                "Score": score,
                "Verdict": verdict,
                "Thesis": thesis,
                "Risque": risk,
                "Source": source
            }
            
        except Exception as e:
            pass  # Fallback vers Yahoo
    
    # TENTATIVE 2 : Yahoo Finance (Fallback)
    try:
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
        
        # ANALYSE IA
        try:
            if not client:
                raise Exception("No Key")
            
            prompt = f"Analyse flash {ticker}. Prix {current}. Secteur {info.get('sector')}. Output JSON strict: {{'verdict': 'BUY/HOLD/SELL', 'score': 75, 'thesis': '1 phrase', 'risk': '1 mot'}}"
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw_text = response.choices[0].message.content
            ai_data = extract_json_safe(raw_text)
            
            if not all(k in ai_data for k in ['verdict', 'score', 'thesis', 'risk']):
                raise Exception("Incomplete JSON")
            
            verdict = ai_data.get('verdict')
            thesis = ai_data.get('thesis')
            score = ai_data.get('score')
            risk = ai_data.get('risk')
            source = "✅ Yahoo + OpenAI"
            
        except:
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
            "Industry": info.get('industry', 'N/A'),
            "Description": safe_truncate(info.get('longBusinessSummary', ''), 150),
            "CEO": "N/A",  # Yahoo ne fournit pas toujours ce champ
            "Website": info.get('website', 'N/A'),
            "Micro": micro,
            "Score": score,
            "Verdict": verdict,
            "Thesis": thesis,
            "Risque": risk,
            "Source": source
        }
        
    except Exception:
        # TENTATIVE 3 : Mock Data (Dernier recours)
        return generate_rich_mock_data(ticker)

# --- 6. INTERFACE TERMINAL ---

# BANDEAU MACRO
col_t1, col_t2, col_t3, col_t4 = st.columns(4)
with col_t1: st.metric("S&P 500", "4,890.23", "+0.45%")
with col_t2: st.metric("NASDAQ", "15,450.10", "+0.80%")
with col_t3: st.metric("EUR/USD", "1.0850", "-0.12%")
with col_t4: st.metric("BTC/USD", "64,230.00", "+2.40%")
st.divider()

# SIDEBAR (Contrôles)
with st.sidebar:
    st.title("🦅 HUNTER V19")
    st.caption("Professional Infrastructure")
    
    input_tickers = st.text_area("Watchlist", "NVDA PLTR AMD")
    
    # DÉDOUBLONNAGE STRICT : Préserve l'ordre + Normalisation
    raw_tickers = [t.strip().upper() for t in input_tickers.replace(',',' ').split() if t.strip()]
    tickers = list(dict.fromkeys(raw_tickers))
    
    st.markdown("---")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        run_btn = st.button("🚀 RUN", type="primary", use_container_width=True)
    with col_btn2:
        reset_btn = st.button("🔄 RESET", type="secondary", use_container_width=True)
    
    # RESET HANDLER
    if reset_btn:
        st.session_state['results'] = None
        st.session_state['chat_history'] = {}
        st.success("Cache effacé !")
        st.rerun()
    
    # Placeholder pour le bouton d'export
    export_placeholder = st.empty()
    
    # Indicateur de statut
    if st.session_state['results']:
        st.markdown("---")
        st.info(f"📊 {len(st.session_state['results'])} analyses en cache")

# MAIN CONTENT

# LOGIQUE v19 : PERSISTENCE
if run_btn and tickers:
    # EXÉCUTION D'ANALYSE (écrase le cache)
    with st.spinner("🔍 Analyse en cours..."):
        results = {}
        for t in tickers:
            results[t] = analyze_stock_pro(t)
        
        # SAUVEGARDE DANS SESSION STATE
        st.session_state['results'] = results
    
    st.success("✅ Analyse terminée !")

# AFFICHAGE (depuis le cache si disponible)
if st.session_state['results']:
    results = st.session_state['results']
    report_data = []
    
    for ticker, data in results.items():
        # CARD DESIGN (Bloomberg Terminal Style)
        with st.container(border=True):
            # HEADER
            c_head1, c_head2, c_head3 = st.columns([2, 4, 2])
            with c_head1:
                st.markdown(f"## {data['Ticker']}")
                st.caption(f"{data.get('Sector', 'N/A')} · {data.get('Industry', 'N/A')}")
            with c_head2:
                delta_color = "normal" if data['Change'] > 0 else "inverse"
                st.metric("Prix Actuel", f"{data['Prix']:.2f} $", f"{data['Change']:.2f} %", delta_color=delta_color)
            with c_head3:
                st.metric("AI Score", f"{data['Score']}/100", data['Verdict'])
                st.markdown(render_score_bar(data['Score']), unsafe_allow_html=True)

            st.markdown("#### 🔢 Key Financials")
            m = data['Micro']
            
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
                
                # Infos supplémentaires (v19)
                if data.get('CEO') and data['CEO'] != 'N/A':
                    st.caption(f"CEO: {data['CEO']}")
                if data.get('Website') and data['Website'] != 'N/A':
                    st.caption(f"🌐 {data['Website']}")

            # --- MODULE DE CHAT CONTEXTUEL ---
            with st.expander(f"💬 Discuter avec l'Analyste [{data['Ticker']}]"):
                st.caption("Posez vos questions sur cette analyse. L'IA connaît toutes les métriques affichées ci-dessus.")
                
                # Initialisation de l'historique pour ce ticker
                if data['Ticker'] not in st.session_state['chat_history']:
                    st.session_state['chat_history'][data['Ticker']] = []
                
                # ÉTAPE 1 : Afficher l'historique existant
                for message in st.session_state['chat_history'][data['Ticker']]:
                    with st.chat_message(message["role"]):
                        st.write(message["content"])
                
                # ÉTAPE 2 : Capturer le nouveau message
                if prompt := st.chat_input(
                    f"Ex: Pourquoi le PE est si élevé pour {data['Ticker']} ?",
                    key=f"chat_input_{data['Ticker']}"
                ):
                    # ÉTAPE 3 : Afficher immédiatement le message utilisateur
                    with st.chat_message("user"):
                        st.write(prompt)
                    
                    # ÉTAPE 4 : Générer et afficher la réponse assistant
                    with st.chat_message("assistant"):
                        with st.spinner("Analyse en cours..."):
                            response = get_ai_response(
                                data['Ticker'], 
                                data, 
                                prompt, 
                                st.session_state['chat_history'][data['Ticker']]
                            )
                        st.write(response)
                    
                    # ÉTAPE 5 : Sauvegarder dans session_state
                    st.session_state['chat_history'][data['Ticker']].append({
                        "role": "user",
                        "content": prompt
                    })
                    st.session_state['chat_history'][data['Ticker']].append({
                        "role": "assistant",
                        "content": response
                    })

        # Ajout des données au rapport CSV
        report_data.append({
            "Ticker": ticker,
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
            st.success("✅ Données en cache")
            st.download_button(
                label="📥 TÉLÉCHARGER RAPPORT (CSV)",
                data=csv,
                file_name=f"Hunter_Report_{datetime.date.today()}.csv",
                mime="text/csv",
            )
            
            st.markdown("---")
            st.markdown("**📧 Email Briefing:**")
            avg_change = df['Change %'].astype(float).mean()
            top_ticker = df.loc[df['Score'].idxmax()]['Ticker']
            st.code(f"Analyse: {len(report_data)} actifs. Tendance: {'Haussière' if avg_change > 0 else 'Mixte'}. Top pick: {top_ticker}.", language="text")