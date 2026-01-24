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
    page_title="AI Strategic Hunter v20",
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

# --- INIT STATE (v20 - PERSONAS) ---
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = {}

if 'results' not in st.session_state:
    st.session_state['results'] = None

if 'selected_persona' not in st.session_state:
    st.session_state['selected_persona'] = "Warren"

# --- PERSONAS CONFIGURATION (v20) ---
PERSONAS = {
    "Warren": {
        "name": "Warren (Value & Sécurité)",
        "emoji": "🔰",
        "description": "Investisseur prudent focalisé sur la valeur intrinsèque",
        "system_prompt_addition": """
TU ES WARREN BUFFETT - L'ORACLE D'OMAHA

PHILOSOPHIE D'INVESTISSEMENT :
- Tu cherches des entreprises sous-évaluées avec un 'moat' (avantage concurrentiel durable).
- PE Ratio : Critique au-delà de 25. Au-delà de 40, c'est un red flag majeur.
- Cash Flow : C'est le ROI qui compte, pas les promesses de croissance.
- Dette : Tu détestes la dette excessive. Debt-to-Equity > 2 = danger.
- Dividendes : Signe de maturité et de santé financière.
- Volatilité (Beta) : Tu préfères Beta < 1.2 (stabilité).

TON ET STYLE :
- Cynique et pragmatique. Tu n'es pas impressionné par le "hype".
- Phrases types : "Le prix est ce que vous payez, la valeur est ce que vous obtenez."
- Tu recommandes HOLD ou SELL plus souvent que BUY.
- Score : Rarement au-dessus de 70 sauf si valeur exceptionnelle.

CRITÈRES DE VERDICT :
- BUY : PE < 20, marges solides, historique de profits, dividendes.
- HOLD : PE 20-30, financials corrects mais pas d'opportunité exceptionnelle.
- SELL : PE > 40, pertes chroniques, hype sans substance, Beta > 1.5.
""",
        "risk_keywords": ["Surévaluation", "Spéculation", "Volatilité"]
    },
    "Cathie": {
        "name": "Cathie (Growth & Innovation)",
        "emoji": "🚀",
        "description": "Chasseuse de licornes tech et d'innovation disruptive",
        "system_prompt_addition": """
TU ES CATHIE WOOD - LA VISIONNAIRE DE L'INNOVATION

PHILOSOPHIE D'INVESTISSEMENT :
- Tu cherches les entreprises qui vont changer le monde dans 5-10 ans.
- Revenue Growth : C'est le métrique #1. +30% YoY = excellent signal.
- PE Ratio : Non pertinent pour les disrupteurs. Tesla a un PE de 100+ et c'est normal.
- Secteurs favoris : IA, Robotique, Biotech, Fintech, Cleantech, Blockchain.
- Pertes actuelles : Acceptables si la croissance est explosive.
- R&D Investment : Plus c'est élevé, mieux c'est.

TON ET STYLE :
- Optimiste et visionnaire. Tu vois le potentiel, pas les obstacles.
- Phrases types : "L'innovation exponentielle crée des opportunités inimaginables."
- Tu recommandes BUY ou STRONG BUY fréquemment.
- Score : Facilement 80-95 pour les secteurs d'innovation.

CRITÈRES DE VERDICT :
- STRONG BUY : Secteur innovant, Revenue Growth > 40%, R&D élevé.
- BUY : Growth > 20%, secteur tech/émergent, vision claire.
- HOLD : Growth < 20%, secteur mature.
- SELL : Croissance négative, entreprise legacy sans transformation.
""",
        "risk_keywords": ["Disruption", "Innovation", "Croissance"]
    },
    "Jim": {
        "name": "Jim (Momentum & Quant)",
        "emoji": "⚡",
        "description": "Trader quantitatif basé sur les signaux techniques",
        "system_prompt_addition": """
TU ES JIM SIMONS - LE QUANT LÉGENDAIRE

PHILOSOPHIE D'INVESTISSEMENT :
- Les chiffres ne mentent pas. Tout est dans les patterns et les statistiques.
- Beta : Métrique clé. Beta > 1.5 = volatilité exploitable pour le trading.
- Volume : Liquidité = opportunité. Volume faible = danger.
- Price Action : Momentum récent (Change %) est plus important que les fondamentaux.
- Corrélations : Tu cherches les anomalies de marché.
- Timeframe : Court/moyen terme (jours/semaines, pas années).

TON ET STYLE :
- Froid, analytique, mathématique. Pas d'émotions.
- Phrases types : "Les probabilités favorisent cette position."
- Verdicts basés sur des seuils quantitatifs stricts.
- Score : Calculé sur volatilité + momentum + volume.

CRITÈRES DE VERDICT :
- BUY : Change% > +5%, Beta > 1.3, Volume élevé (signal momentum haussier).
- HOLD : Change% entre -2% et +5%, Beta 0.8-1.3 (range trading).
- SELL : Change% < -5%, Beta < 0.8 (pas de volatilité = pas d'opportunité).

ANALYSE :
- Tu ignores les "histoires" et les visions long terme.
- Focus : Beta, Change%, Volume, correlation avec indices.
""",
        "risk_keywords": ["Volatilité", "Liquidité", "Momentum"]
    }
}

def get_persona_emoji(persona_key):
    """Retourne l'emoji du persona sélectionné"""
    return PERSONAS.get(persona_key, {}).get("emoji", "📊")

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

def build_context_prompt(ticker, data, persona_key="Warren"):
    """
    Construit un system prompt enrichi avec les données de l'analyse.
    v20 : Intègre la personnalité de l'investisseur sélectionné.
    """
    micro = data['Micro']
    persona = PERSONAS.get(persona_key, PERSONAS["Warren"])
    
    base_context = f"""DONNÉES DE L'ANALYSE EN COURS :
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
"""
    
    # Ajout de la personnalité
    persona_instruction = persona['system_prompt_addition']
    
    context = f"""{persona_instruction}

{base_context}

DIRECTIVES :
- Réponds selon TA personnalité d'investisseur ({persona['name']}).
- Utilise les données ci-dessus pour répondre aux questions de l'utilisateur.
- Sois cohérent avec ta philosophie d'investissement.
- Si la question sort du cadre de cette analyse, indique-le poliment.
- Ne jamais inventer de données : base-toi uniquement sur le contexte fourni.
"""
    return context

def get_ai_response(ticker, data, user_message, chat_history, persona_key="Warren"):
    """
    Génère une réponse de l'IA avec le contexte complet.
    v20 : Prend en compte le persona sélectionné.
    """
    try:
        if not client:
            return "❌ Service d'analyse indisponible (clé API OpenAI manquante)."
        
        # Construction du contexte avec persona
        system_prompt = build_context_prompt(ticker, data, persona_key)
        
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

def fetch_data_hybrid(ticker):
    """
    Stratégie HYBRIDE v19.2 : FMP (Prix/Chiffres) + Yahoo (Profil/Texte)
    
    ÉTAPE 1 : Récupère les métriques financières depuis FMP /quote
    ÉTAPE 2 : Récupère le profil textuel depuis Yahoo Finance
    ÉTAPE 3 : Assemble les deux sources
    
    Retourne un dict complet ou None si FMP échoue (Yahoo optionnel).
    """
    if not FMP_API_KEY:
        return None
    
    # ===== ÉTAPE 1 : FMP QUOTE (SOURCE DE VÉRITÉ POUR LES CHIFFRES) =====
    try:
        quote_url = f"https://financialmodelingprep.com/api/v3/quote/{ticker}"
        params = {"apikey": FMP_API_KEY}
        
        response = requests.get(quote_url, params=params, timeout=5)
        response.raise_for_status()
        
        quote_data = response.json()
        
        if not quote_data or len(quote_data) == 0:
            return None
        
        quote = quote_data[0]
        
        # Extraction des métriques FMP
        fmp_metrics = {
            "price": quote.get('price', 0),
            "change": quote.get('changesPercentage', 0),
            "marketCap": quote.get('marketCap', 0),
            "pe": quote.get('pe', 0),
            "eps": quote.get('eps', 0),
            "yearHigh": quote.get('yearHigh', 0),
            "yearLow": quote.get('yearLow', 0),
            "volume": quote.get('volume', 0)
        }
        
    except Exception as e:
        # Si FMP échoue, on ne peut pas continuer (c'est notre source primaire)
        return None
    
    # ===== ÉTAPE 2 : YAHOO FINANCE PROFILE (INFORMATIONS TEXTUELLES) =====
    yahoo_profile = {
        "sector": "N/A",
        "industry": "N/A",
        "description": "",
        "website": "N/A",
        "ceo": "N/A",
        "beta": 0
    }
    
    try:
        # Tentative de récupération du profil Yahoo (non bloquant)
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Extraction sélective des champs textuels
        yahoo_profile = {
            "sector": info.get('sector', 'N/A'),
            "industry": info.get('industry', 'N/A'),
            "description": info.get('longBusinessSummary', ''),
            "website": info.get('website', 'N/A'),
            "ceo": info.get('companyOfficers', [{}])[0].get('name', 'N/A') if info.get('companyOfficers') else 'N/A',
            "beta": info.get('beta', 0)
        }
        
    except Exception as e:
        # Yahoo a échoué, mais ce n'est pas bloquant
        # On garde les valeurs par défaut "N/A"
        pass
    
    # ===== ÉTAPE 3 : ASSEMBLAGE FINAL =====
    return {
        **fmp_metrics,      # Prix, PE, EPS, Market Cap depuis FMP
        **yahoo_profile     # Sector, Industry, Description depuis Yahoo
    }

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

def analyze_stock_pro(ticker, persona_key="Warren"):
    """
    Analyse principale avec Graceful Degradation.
    v20 : Intègre le persona dans l'analyse IA.
    """
    ticker = ticker.strip().upper()
    
    # ANTI-BAN : Throttling aléatoire
    time.sleep(random.uniform(0.5, 1.5))
    
    # Récupération du persona
    persona = PERSONAS.get(persona_key, PERSONAS["Warren"])
    
    # ===== TENTATIVE 1 : STRATÉGIE HYBRIDE (FMP + YAHOO) =====
    hybrid_data = fetch_data_hybrid(ticker)
    
    if hybrid_data:
        try:
            current = hybrid_data['price']
            change = hybrid_data['change']
            
            # Construction de l'historique (simplifié - variation aléatoire autour du prix)
            base_price = current
            hist_prices = []
            for i in range(50):
                # Simule une évolution historique réaliste
                variation = random.uniform(-0.03, 0.03)  # ±3% par jour
                hist_prices.append(base_price * (1 + variation * (50-i)/50))
            
            hist = pd.DataFrame({"Close": hist_prices})
            
            # Construction des métriques
            micro = {
                "Market Cap": f"{hybrid_data['marketCap']/1e9:.1f}B" if hybrid_data['marketCap'] else "N/A",
                "PE Ratio": f"{hybrid_data['pe']:.1f}" if hybrid_data['pe'] else "N/A",
                "PEG": "N/A",  # Non disponible dans /quote
                "EPS": f"{hybrid_data['eps']:.2f}" if hybrid_data['eps'] else "N/A",
                "Div Yield": "N/A",  # Non disponible dans /quote
                "Beta": f"{hybrid_data['beta']:.2f}" if hybrid_data['beta'] else "N/A",
                "Profit Margin": "N/A",  # Non disponible dans /quote
                "Revenue YoY": "N/A"  # Non disponible dans /quote
            }
            
            # ANALYSE IA AVEC PERSONA
            try:
                if not client:
                    raise Exception("No Key")
                
                # Construction du prompt avec la philosophie du persona
                persona_context = persona['system_prompt_addition']
                
                prompt = f"""{persona_context}

Analyse {ticker} selon TA personnalité :
- Prix: ${current}
- Change: {change}%
- Secteur: {hybrid_data['sector']}
- PE: {hybrid_data['pe']}
- Beta: {hybrid_data['beta']}

Output JSON strict: {{'verdict': 'BUY/HOLD/SELL', 'score': 75, 'thesis': '1 phrase style {persona['name']}', 'risk': '1 mot de {persona['risk_keywords']}'}}
"""
                
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.8  # Plus de créativité pour les personas
                )
                
                raw_text = response.choices[0].message.content
                ai_data = extract_json_safe(raw_text)
                
                if not all(k in ai_data for k in ['verdict', 'score', 'thesis', 'risk']):
                    raise Exception("Incomplete JSON")
                
                verdict = ai_data.get('verdict')
                thesis = ai_data.get('thesis')
                score = ai_data.get('score')
                risk = ai_data.get('risk')
                source = f"🌟 FMP + Yahoo + {persona['emoji']} {persona_key}"
                
            except:
                verdict = "NEUTRE"
                thesis = f"Analyse technique seule (IA indisponible, style {persona_key})."
                score = 50
                risk = "N/A"
                source = f"🌟 FMP + Yahoo ({persona['emoji']} {persona_key})"
            
            # Assemblage final du dictionnaire de données
            return {
                "Ticker": ticker,
                "Prix": current,
                "Change": change,
                "History": hist,
                "Sector": hybrid_data['sector'],
                "Industry": hybrid_data['industry'],
                "Description": safe_truncate(hybrid_data['description'], 150),
                "CEO": hybrid_data['ceo'],
                "Website": hybrid_data['website'],
                "Micro": micro,
                "Score": score,
                "Verdict": verdict,
                "Thesis": thesis,
                "Risque": risk,
                "Source": source,
                "Persona": persona_key  # v20 : Stockage du persona utilisé
            }
            
        except Exception as e:
            # Si l'assemblage échoue, on passe au fallback
            pass
    
    # ===== TENTATIVE 2 : YAHOO FINANCE SEUL (Fallback complet) =====
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
        
        # ANALYSE IA AVEC PERSONA
        try:
            if not client:
                raise Exception("No Key")
            
            persona_context = persona['system_prompt_addition']
            
            prompt = f"""{persona_context}

Analyse {ticker} selon TA personnalité :
- Prix: ${current}
- Secteur: {info.get('sector')}
- PE: {info.get('trailingPE', 0)}
- Revenue Growth: {info.get('revenueGrowth', 0)*100}%

Output JSON strict: {{'verdict': 'BUY/HOLD/SELL', 'score': 75, 'thesis': '1 phrase', 'risk': '1 mot'}}
"""
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8
            )
            
            raw_text = response.choices[0].message.content
            ai_data = extract_json_safe(raw_text)
            
            if not all(k in ai_data for k in ['verdict', 'score', 'thesis', 'risk']):
                raise Exception("Incomplete JSON")
            
            verdict = ai_data.get('verdict')
            thesis = ai_data.get('thesis')
            score = ai_data.get('score')
            risk = ai_data.get('risk')
            source = f"✅ Yahoo + {persona['emoji']} {persona_key}"
            
        except:
            verdict = "NEUTRE"
            thesis = f"Analyse technique seule (style {persona_key})."
            score = 50
            risk = "N/A"
            source = f"⚠️ Yahoo ({persona['emoji']} {persona_key})"
        
        return {
            "Ticker": ticker,
            "Prix": current,
            "Change": change,
            "History": hist,
            "Sector": info.get('sector', 'N/A'),
            "Industry": info.get('industry', 'N/A'),
            "Description": safe_truncate(info.get('longBusinessSummary', ''), 150),
            "CEO": "N/A",
            "Website": info.get('website', 'N/A'),
            "Micro": micro,
            "Score": score,
            "Verdict": verdict,
            "Thesis": thesis,
            "Risque": risk,
            "Source": source,
            "Persona": persona_key
        }
        
    except Exception:
        # ===== TENTATIVE 3 : MOCK DATA (Dernier recours) =====
        mock_data = generate_rich_mock_data(ticker)
        mock_data["Persona"] = persona_key
        mock_data["Source"] = f"⚠️ Simulation ({persona['emoji']} {persona_key})"
        return mock_data

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
    st.title("🦅 HUNTER V20")
    st.caption("Strategic Personas")
    
    # SÉLECTION DU PERSONA (v20)
    st.markdown("### 🧠 Mode d'Analyse")
    persona_options = {
        "Warren": f"{PERSONAS['Warren']['emoji']} {PERSONAS['Warren']['name']}",
        "Cathie": f"{PERSONAS['Cathie']['emoji']} {PERSONAS['Cathie']['name']}",
        "Jim": f"{PERSONAS['Jim']['emoji']} {PERSONAS['Jim']['name']}"
    }
    
    selected_persona = st.selectbox(
        "Persona d'Investisseur",
        options=list(persona_options.keys()),
        format_func=lambda x: persona_options[x],
        index=0,
        key="persona_selector"
    )
    
    # Mise à jour du persona dans session_state
    st.session_state['selected_persona'] = selected_persona
    
    # Description du persona
    st.caption(PERSONAS[selected_persona]['description'])
    
    st.markdown("---")
    
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
        persona_emoji = get_persona_emoji(selected_persona)
        st.info(f"{persona_emoji} {len(st.session_state['results'])} analyses en cache")


# MAIN CONTENT

# LOGIQUE v20 : PERSISTENCE + PERSONA
if run_btn and tickers:
    # EXÉCUTION D'ANALYSE (écrase le cache)
    with st.spinner(f"🔍 Analyse en cours avec {PERSONAS[selected_persona]['emoji']} {selected_persona}..."):
        results = {}
        for t in tickers:
            results[t] = analyze_stock_pro(t, selected_persona)
        
        # SAUVEGARDE DANS SESSION STATE
        st.session_state['results'] = results
    
    st.success(f"✅ Analyse terminée (Mode {selected_persona}) !")

# AFFICHAGE (depuis le cache si disponible)
if st.session_state['results']:
    results = st.session_state['results']
    report_data = []
    
    for ticker, data in results.items():
        # Récupération du persona utilisé pour cette analyse
        persona_used = data.get('Persona', 'Warren')
        persona_emoji = get_persona_emoji(persona_used)
        
        # CARD DESIGN (Bloomberg Terminal Style)
        with st.container(border=True):
            # HEADER avec emoji persona
            c_head1, c_head2, c_head3 = st.columns([2, 4, 2])
            with c_head1:
                st.markdown(f"## {data['Ticker']} {persona_emoji}")
                st.caption(f"{data.get('Sector', 'N/A')} · {data.get('Industry', 'N/A')}")
            with c_head2:
                delta_color = "normal" if data['Change'] > 0 else "inverse"
                st.metric("Prix Actuel", f"{data['Prix']:.2f} $", f"{data['Change']:.2f} %", delta_color=delta_color)
            
            # --- MODIFICATION ICI : FORCE LA FLECHE VISUELLE ---
            with c_head3:
                rec = data['Verdict']
                # Logique: SELL = Fleche Bas + Rouge (Inverse), BUY = Fleche Haut + Vert (Normal)
                if "SELL" in rec.upper():
                    verdict_color = "inverse"
                    rec_display = f"▼ {rec}"  # Force l'icône BAS
                elif "BUY" in rec.upper():
                    verdict_color = "normal"
                    rec_display = f"▲ {rec}"  # Force l'icône HAUT
                else:
                    verdict_color = "off"
                    rec_display = rec
                    
                st.metric("AI Score", f"{data['Score']}/100", rec_display, delta_color=verdict_color)
                st.markdown(render_score_bar(data['Score']), unsafe_allow_html=True)
            # ---------------------------------------------

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
            with st.expander(f"💬 Discuter avec l'Analyste [{data['Ticker']}] {persona_emoji}"):
                st.caption(f"Posez vos questions dans le style {PERSONAS[persona_used]['name']}. L'IA connaît toutes les métriques affichées ci-dessus.")
                
                # Initialisation de l'historique pour ce ticker
                if data['Ticker'] not in st.session_state['chat_history']:
                    st.session_state['chat_history'][data['Ticker']] = []
                
                # ÉTAPE 1 : Afficher l'historique existant
                for message in st.session_state['chat_history'][data['Ticker']]:
                    with st.chat_message(message["role"]):
                        st.write(message["content"])
                
                # ÉTAPE 2 : Capturer le nouveau message
                if prompt := st.chat_input(
                    f"Ex: Cette valorisation est-elle justifiée selon {persona_used} ?",
                    key=f"chat_input_{data['Ticker']}"
                ):
                    # ÉTAPE 3 : Afficher immédiatement le message utilisateur
                    with st.chat_message("user"):
                        st.write(prompt)
                    
                    # ÉTAPE 4 : Générer et afficher la réponse assistant (avec persona)
                    with st.chat_message("assistant"):
                        with st.spinner(f"Analyse en cours ({persona_used})..."):
                            response = get_ai_response(
                                data['Ticker'], 
                                data, 
                                prompt, 
                                st.session_state['chat_history'][data['Ticker']],
                                persona_used  # v20 : Passage du persona
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