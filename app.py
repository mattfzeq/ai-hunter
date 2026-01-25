import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
import os
import json
import time
import re
from openai import OpenAI
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== CONFIGURATION ====================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

st.set_page_config(page_title="AI Hunter V24 Armored", page_icon="🦅", layout="wide")

# ==================== STYLES CSS ====================
st.markdown("""
<style>
    .stApp { background-color: #0a0e27; color: #00ff41; }
    .main { background-color: #0a0e27; }
    h1, h2, h3, h4, p, label, div { font-family: 'Courier New', monospace; color: #00ff41 !important; }
    div[data-testid="stMetricValue"] { color: #00ff41 !important; font-size: 1.6rem !important; }
    .stMetric { background-color: #1a1f3a; padding: 10px; border: 1px solid #00ff41; border-radius: 5px; }
    .macro-banner {
        background: linear-gradient(90deg, #1a1f3a 0%, #2a2f4a 100%);
        padding: 15px; border: 1px solid #00ff41; border-radius: 8px;
        margin-bottom: 20px; text-align: center;
    }
    .verdict-box { padding: 15px; border-radius: 8px; font-weight: bold; text-align: center; border: 2px solid; }
    .method-status { padding: 8px; margin: 5px 0; border-radius: 5px; font-size: 0.9em; }
</style>
""", unsafe_allow_html=True)

# ==================== SESSION HTTP ROBUSTE ====================

def create_robust_session():
    """
    Crée une session HTTP résistante avec:
    - Headers complets pour éviter la détection bot
    - Retry automatique (3 tentatives)
    - Backoff exponentiel
    """
    session = requests.Session()
    
    # Headers réalistes pour contourner la détection
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
        'DNT': '1',
    })
    
    # Strategy de retry: 3 tentatives avec délai croissant
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,  # 1s, 2s, 4s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

# ==================== MÉTHODE 1: YFINANCE DOWNLOAD ====================

def fetch_via_yf_download(ticker_symbol):
    """
    Méthode 1: yfinance.download (généralement la plus fiable)
    Retourne None en cas d'échec
    """
    try:
        # Téléchargement des données historiques
        df = yf.download(
            ticker_symbol, 
            period="6mo", 
            progress=False,
            timeout=10,
            threads=False  # Évite les problèmes de concurrence
        )
        
        if df.empty:
            return None
        
        # Récupération des infos fondamentales
        session = create_robust_session()
        stock = yf.Ticker(ticker_symbol, session=session)
        
        time.sleep(0.5)  # Anti-rate limiting
        
        try:
            info = stock.info
        except:
            info = {}
        
        # Extraction du prix (gestion multi-index)
        close_col = df['Close']
        if isinstance(close_col, pd.DataFrame):
            close_col = close_col.iloc[:, 0]
        
        price_today = float(close_col.iloc[-1])
        price_6m_ago = float(close_col.iloc[0])
        
        if price_today <= 0:
            return None
        
        trend_6m = ((price_today - price_6m_ago) / price_6m_ago) * 100
        
        return {
            'ticker': ticker_symbol,
            'name': info.get('longName', ticker_symbol),
            'current_price': price_today,
            'history': df,
            'trend_6m': trend_6m,
            'market_cap': info.get('marketCap', 0),
            'trailing_pe': info.get('trailingPE', 0),
            'debt': info.get('totalDebt', 0),
            'revenue_growth': info.get('revenueGrowth', 0),
            'source': 'API YFINANCE (download)'
        }
        
    except Exception as e:
        return None

# ==================== MÉTHODE 2: YFINANCE TICKER.HISTORY ====================

def fetch_via_yf_ticker(ticker_symbol):
    """
    Méthode 2: yfinance.Ticker().history (alternative)
    Parfois fonctionne quand download échoue
    """
    try:
        session = create_robust_session()
        stock = yf.Ticker(ticker_symbol, session=session)
        
        time.sleep(0.5)
        df = stock.history(period="6mo")
        
        if df.empty or df['Close'].iloc[-1] <= 0:
            return None
        
        price_today = float(df['Close'].iloc[-1])
        price_6m_ago = float(df['Close'].iloc[0])
        trend_6m = ((price_today - price_6m_ago) / price_6m_ago) * 100
        
        # Tentative d'obtenir les infos (peut échouer)
        try:
            info = stock.info
            name = info.get('longName', ticker_symbol)
            pe = info.get('trailingPE', 0)
            mcap = info.get('marketCap', 0)
        except:
            name = ticker_symbol
            pe = 0
            mcap = 0
        
        return {
            'ticker': ticker_symbol,
            'name': name,
            'current_price': price_today,
            'history': df,
            'trend_6m': trend_6m,
            'market_cap': mcap,
            'trailing_pe': pe,
            'debt': 0,
            'revenue_growth': 0,
            'source': 'API YFINANCE (Ticker.history)'
        }
        
    except Exception as e:
        return None

# ==================== MÉTHODE 3: SCRAPING YAHOO ====================

def fetch_via_scraping(ticker_symbol):
    """
    Méthode 3: Scraping direct du HTML Yahoo Finance
    3 techniques de fallback pour extraire le prix
    """
    try:
        session = create_robust_session()
        url = f"https://finance.yahoo.com/quote/{ticker_symbol}"
        
        time.sleep(1)  # Important: éviter le rate limiting
        response = session.get(url, timeout=10)
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        price = None
        change = 0
        
        # === TECHNIQUE 1: Balise fin-streamer (principale) ===
        price_tag = soup.find('fin-streamer', {'data-field': 'regularMarketPrice'})
        if price_tag and price_tag.get('value'):
            try:
                price = float(price_tag['value'])
            except:
                pass
        
        # === TECHNIQUE 2: Fallback sur data-symbol ===
        if not price:
            price_tag = soup.find('fin-streamer', {'data-symbol': ticker_symbol})
            if price_tag and price_tag.get('value'):
                try:
                    price = float(price_tag['value'])
                except:
                    pass
        
        # === TECHNIQUE 3: Regex dans le JSON embarqué ===
        if not price:
            # Yahoo inclut souvent les données dans un script JSON
            pattern = r'"regularMarketPrice":\s*\{\s*"raw"\s*:\s*([\d.]+)'
            match = re.search(pattern, response.text)
            if match:
                try:
                    price = float(match.group(1))
                except:
                    pass
        
        # Vérification finale
        if not price or price <= 0:
            return None
        
        # Variation (optionnel)
        change_tag = soup.find('fin-streamer', {'data-field': 'regularMarketChangePercent'})
        if change_tag and change_tag.get('value'):
            try:
                change = float(change_tag['value'])
            except:
                change = 0
        
        return {
            'ticker': ticker_symbol,
            'name': ticker_symbol,  # Nom difficile à extraire en scraping
            'current_price': price,
            'history': pd.DataFrame(),  # Pas d'historique en scraping
            'trend_6m': change * 10,  # Estimation approximative
            'market_cap': 0,
            'trailing_pe': 0,
            'debt': 0,
            'revenue_growth': 0,
            'source': 'SCRAPING WEB (Mode Survie)'
        }
        
    except Exception as e:
        return None

# ==================== MÉTHODE 4: ALPHA VANTAGE (BACKUP) ====================

def fetch_via_alphavantage(ticker_symbol):
    """
    Méthode 4: API Alpha Vantage (gratuit, 5 req/min)
    Nécessite une clé API gratuite: https://www.alphavantage.co/support/#api-key
    """
    api_key = os.getenv("ALPHA_VANTAGE_KEY") or st.secrets.get("ALPHA_VANTAGE_KEY", None)
    
    if not api_key:
        return None
    
    try:
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker_symbol}&apikey={api_key}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        quote = data.get('Global Quote', {})
        
        if not quote:
            return None
        
        price = float(quote.get('05. price', 0))
        
        if price <= 0:
            return None
        
        # Extraction du change percent
        change_str = quote.get('10. change percent', '0%').replace('%', '')
        try:
            change_pct = float(change_str)
        except:
            change_pct = 0
        
        return {
            'ticker': ticker_symbol,
            'name': ticker_symbol,
            'current_price': price,
            'history': pd.DataFrame(),
            'trend_6m': change_pct,
            'market_cap': 0,
            'trailing_pe': 0,
            'debt': 0,
            'revenue_growth': 0,
            'source': 'ALPHA VANTAGE API'
        }
        
    except Exception as e:
        return None

# ==================== ORCHESTRATEUR PRINCIPAL ====================

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_stock_data(ticker_symbol):
    """
    Orchestrateur intelligent avec 4 méthodes de fallback
    Retourne les données ou None
    """
    methods = [
        ("📊 YFinance Download", fetch_via_yf_download),
        ("📈 YFinance Ticker", fetch_via_yf_ticker),
        ("🌐 Web Scraping", fetch_via_scraping),
        ("🔑 Alpha Vantage", fetch_via_alphavantage),
    ]
    
    for i, (method_name, method_func) in enumerate(methods, 1):
        st.info(f"Tentative {i}/{len(methods)}: {method_name}...")
        
        result = method_func(ticker_symbol)
        
        if result and result.get('current_price', 0) > 0:
            st.success(f"✅ {method_name} - Succès!")
            return result
        else:
            st.warning(f"⚠️ {method_name} - Échec")
    
    # Toutes les méthodes ont échoué
    return None

# ==================== CERVEAU IA ====================

def analyze_with_ai(persona, data):
    """
    Analyse IA via OpenAI GPT
    Retourne: {verdict, score, thesis, risk}
    """
    try:
        api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", None)
        
        if not api_key:
            return {
                'verdict': 'ERROR',
                'score': 0,
                'thesis': 'Clé OpenAI manquante (OPENAI_API_KEY)',
                'risk': 'HIGH'
            }
        
        client = OpenAI(api_key=api_key)
        
        # Instructions selon le persona
        logic = "Score < 45 = SELL, 46-65 = HOLD, > 66 = BUY."
        prompts = {
            "Warren": f"Tu es Warren Buffett. Analyse value investing. {logic}",
            "Cathie": f"Tu es Cathie Wood. Focus croissance disruptive. {logic}",
            "Jim": f"Tu es Jim Cramer. Analyse momentum court terme. {logic}"
        }
        
        # Message adapté selon la source de données
        source_quality = "(Données limitées)" if "SCRAPING" in data['source'] or "ALPHA" in data['source'] else "(Données complètes)"
        
        user_message = f"""
        ANALYSE: {data['ticker']} {source_quality}
        Prix actuel: ${data['current_price']:.2f}
        Tendance 6 mois: {data.get('trend_6m', 0):.1f}%
        PE Ratio: {data.get('trailing_pe', 'N/A')}
        Market Cap: ${data.get('market_cap', 0)/1e9:.1f}B
        
        Donne ton verdict en JSON strict: {{"verdict": "BUY/HOLD/SELL", "score": 0-100, "thesis": "explication courte", "risk": "LOW/MEDIUM/HIGH"}}
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompts.get(persona, prompts["Warren"])},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
        
    except Exception as e:
        return {
            'verdict': 'ERROR',
            'score': 0,
            'thesis': f"Erreur IA: {str(e)[:50]}",
            'risk': 'HIGH'
        }

# ==================== INTERFACE UTILISATEUR ====================

def main():
    st.title("🦅 AI HUNTER V24 ARMORED")
    st.markdown("*Multi-Layer Data Engine - Enhanced Edition*")
    
    # Banner macro
    st.markdown(
        '<div class="macro-banner">📈 MARKET | S&P500: +0.4% | BTC: $98k | VIX: 13.5</div>',
        unsafe_allow_html=True
    )
    
    # Input ticker
    col1, col2 = st.columns([3, 1])
    with col1:
        ticker = st.text_input("Ticker Symbol", "NVDA", help="Ex: AAPL, TSLA, MSFT").upper().strip()
    with col2:
        btn = st.button("🚀 ANALYZE", type="primary", use_container_width=True)
    
    # Aide configuration
    with st.expander("⚙️ Configuration (optionnel)"):
        st.markdown("""
        **Pour débloquer toutes les fonctionnalités:**
        
        1. **OpenAI** (analyse IA): Ajoutez `OPENAI_API_KEY` dans vos secrets Streamlit
        2. **Alpha Vantage** (backup data): Créez une clé gratuite sur [alphavantage.co](https://www.alphavantage.co/support/#api-key) 
           et ajoutez `ALPHA_VANTAGE_KEY`
        
        Sans ces clés, l'app fonctionne en mode dégradé (pas d'IA, 3 méthodes sur 4).
        """)
    
    if not btn:
        st.info("👆 Entrez un ticker et cliquez sur ANALYZE")
        return
    
    if not ticker:
        st.error("⚠️ Veuillez entrer un ticker valide")
        return
    
    # === RÉCUPÉRATION DES DONNÉES ===
    with st.spinner(f"🔍 Extraction multi-sources pour {ticker}..."):
        data = fetch_stock_data(ticker)
    
    # Vérification échec total
    if not data or data.get('current_price', 0) <= 0:
        st.error(f"❌ Impossible de récupérer les données de {ticker}")
        st.markdown("""
        **Causes possibles:**
        - Ticker invalide
        - Yahoo Finance bloque les requêtes cloud
        - Toutes les sources de données sont indisponibles
        
        **Solutions:**
        - Vérifiez le ticker (ex: AAPL, MSFT, GOOGL)
        - Configurez Alpha Vantage (voir ⚙️ Configuration)
        - Réessayez dans quelques minutes
        """)
        return
    
    # === AFFICHAGE DES RÉSULTATS ===
    
    # Header
    st.markdown(f"## {data['ticker']} - {data['name']}")
    st.markdown(f"# ${data['current_price']:.2f}")
    
    # Source badge
    source_color = "#00ff41" if "YFINANCE" in data['source'] else "#ffa500"
    st.markdown(
        f"<div style='color:{source_color}; padding:5px; border:1px solid {source_color}; border-radius:5px; display:inline-block;'>📡 Source: {data['source']}</div>",
        unsafe_allow_html=True
    )
    
    # Warning si mode dégradé
    if "SCRAPING" in data['source'] or data['history'].empty:
        st.warning("⚠️ Mode dégradé: Graphique historique non disponible, mais prix en temps réel OK")
    
    st.markdown("---")
    
    # === GRAPHIQUE (si disponible) ===
    if not data['history'].empty:
        try:
            df_hist = data['history']
            
            # Gestion des colonnes multi-index
            if isinstance(df_hist.columns, pd.MultiIndex):
                df_hist.columns = df_hist.columns.get_level_values(0)
            
            fig = go.Figure(data=[go.Candlestick(
                x=df_hist.index,
                open=df_hist['Open'],
                high=df_hist['High'],
                low=df_hist['Low'],
                close=df_hist['Close'],
                increasing_line_color='#00ff41',
                decreasing_line_color='#ff0000'
            )])
            
            fig.update_layout(
                paper_bgcolor='#1a1f3a',
                plot_bgcolor='#1a1f3a',
                font={'color': '#00ff41'},
                height=400,
                xaxis_rangeslider_visible=False,
                title=f"{ticker} - 6 Mois",
                xaxis_title="Date",
                yaxis_title="Prix ($)"
            )
            
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"Impossible d'afficher le graphique: {str(e)}")
    
    # === MÉTRIQUES FONDAMENTALES ===
    st.markdown("### 📊 Métriques")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        pe = data.get('trailing_pe', 0)
        pe_display = f"{pe:.1f}" if pe and pe > 0 else "N/A"
        c1.metric("PE Ratio", pe_display)
    
    with c2:
        mcap = data.get('market_cap', 0)
        mcap_display = f"${mcap/1e9:.1f}B" if mcap > 0 else "N/A"
        c2.metric("Market Cap", mcap_display)
    
    with c3:
        debt = data.get('debt', 0)
        debt_display = f"${debt/1e9:.1f}B" if debt > 0 else "N/A"
        c3.metric("Dette", debt_display)
    
    with c4:
        trend = data.get('trend_6m', 0)
        c4.metric("Trend 6M", f"{trend:.1f}%", delta=f"{trend:.1f}%")
    
    # === ANALYSE IA ===
    st.markdown("---")
    st.markdown("### 🤖 Analyse IA Multi-Persona")
    
    # Vérification clé OpenAI
    api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", None)
    
    if not api_key:
        st.warning("⚠️ Clé OpenAI manquante - Analyse IA désactivée")
        st.info("Ajoutez `OPENAI_API_KEY` dans les secrets Streamlit pour activer l'analyse IA")
    else:
        cols = st.columns(3)
        personas = ["Warren", "Cathie", "Jim"]
        
        for i, persona in enumerate(personas):
            with cols[i]:
                with st.spinner(f"🧠 {persona}..."):
                    analysis = analyze_with_ai(persona, data)
                
                verdict = analysis.get('verdict', 'N/A')
                score = analysis.get('score', 0)
                thesis = analysis.get('thesis', 'Analyse indisponible')
                risk = analysis.get('risk', 'UNKNOWN')
                
                # Couleur selon verdict
                if "BUY" in str(verdict):
                    color = "#00ff41"
                elif "SELL" in str(verdict):
                    color = "#ff4136"
                else:
                    color = "#ffa500"
                
                # Affichage
                st.markdown(
                    f'<div class="verdict-box" style="color:{color}; border-color:{color}">'
                    f'{verdict} ({score}/100)'
                    f'</div>',
                    unsafe_allow_html=True
                )
                
                st.markdown(f"**{persona} Buffett/Wood/Cramer:**")
                st.info(thesis)
                st.caption(f"Risque: {risk}")
    
    # Footer
    st.markdown("---")
    st.caption("🦅 AI Hunter V24 Armored - Enhanced Multi-Source Edition")

# ==================== POINT D'ENTRÉE ====================

if __name__ == "__main__":
    main()