import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import time
import plotly.graph_objects as go

# ==================== CONFIGURATION ====================
st.set_page_config(
    page_title="AI Hunter V21 - Bloomberg Style",
    page_icon="📈",
    layout="wide"
)

# ==================== STYLES CSS BLOOMBERG ====================
st.markdown("""
<style>
    /* Fond Bloomberg Dark */
    .stApp {
        background-color: #0a0e27;
        color: #00ff41;
    }
    
    /* Titres */
    h1, h2, h3 {
        color: #00ff41 !important;
        font-family: 'Courier New', monospace;
        font-weight: bold;
    }
    
    /* Textes */
    p, div, span, label {
        color: #00ff41 !important;
    }
    
    /* Inputs */
    .stTextInput > div > div > input {
        background-color: #1a1f3a;
        color: #00ff41;
        border: 1px solid #00ff41;
    }
    
    /* Boutons */
    .stButton > button {
        background-color: #1a1f3a;
        color: #00ff41;
        border: 2px solid #00ff41;
        font-weight: bold;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        background-color: #00ff41;
        color: #0a0e27;
    }
    
    /* Selectbox */
    .stSelectbox > div > div {
        background-color: #1a1f3a;
        color: #00ff41;
        border: 1px solid #00ff41;
    }
    
    /* Métriques */
    .stMetric {
        background-color: #1a1f3a;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #00ff41;
    }
    
    /* Bandeau Macro */
    .macro-banner {
        background-color: #1a1f3a;
        padding: 15px;
        border-radius: 8px;
        border: 2px solid #00ff41;
        margin-bottom: 20px;
        text-align: center;
    }
    
    /* Alert Box */
    .alert-box {
        background-color: #1a1f3a;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #00ff41;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ==================== FONCTION STEALTH POUR YFINANCE ====================
def fetch_stock_data(ticker_symbol):
    """
    Récupère les données Yahoo Finance avec mécanisme Stealth anti-blocage.
    AUCUNE DONNÉE FICTIVE - Échec propre si blocage persistant.
    """
    # Configuration Session avec Headers complets (simule un vrai navigateur)
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.google.com/search?q=yahoo+finance',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    
    max_retries = 3
    retry_delay = 2  # secondes
    
    for attempt in range(max_retries):
        try:
            # Initialisation du Ticker avec session custom
            ticker = yf.Ticker(ticker_symbol, session=session)
            
            # Récupération de l'historique (6 mois)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
            history = ticker.history(start=start_date, end=end_date)
            
            if history.empty:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return None, f"❌ Aucune donnée trouvée pour {ticker_symbol} après {max_retries} tentatives"
            
            # Tentative de récupération des infos (peut échouer même si history fonctionne)
            try:
                info = ticker.info
                # Vérification que info contient des données utiles
                if not info or len(info) < 5:
                    raise ValueError("Info vide ou incomplète")
            except Exception as info_error:
                # Si info échoue, on calcule manuellement certaines métriques
                info = {
                    'symbol': ticker_symbol,
                    'longName': ticker_symbol,
                    'currentPrice': history['Close'].iloc[-1] if not history.empty else None,
                    'previousClose': history['Close'].iloc[-2] if len(history) > 1 else None,
                }
                st.warning(f"⚠️ Métriques détaillées non disponibles pour {ticker_symbol}. Affichage des données de prix uniquement.")
            
            # Extraction du prix actuel (priorité : currentPrice > dernier Close)
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            if not current_price and not history.empty:
                current_price = float(history['Close'].iloc[-1])
            
            if not current_price:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return None, f"❌ Impossible de récupérer le prix pour {ticker_symbol}"
            
            # Construction du dictionnaire de données
            stock_data = {
                'symbol': ticker_symbol,
                'name': info.get('longName', ticker_symbol),
                'current_price': current_price,
                'previous_close': info.get('previousClose', info.get('regularMarketPreviousClose', current_price)),
                'pe_ratio': info.get('trailingPE', 'N/A'),
                'forward_pe': info.get('forwardPE', 'N/A'),
                'market_cap': info.get('marketCap', 'N/A'),
                'dividend_yield': info.get('dividendYield', 0),
                'debt_to_equity': info.get('debtToEquity', 'N/A'),
                'free_cashflow': info.get('freeCashflow', 'N/A'),
                'operating_cashflow': info.get('operatingCashflow', 'N/A'),
                'revenue_growth': info.get('revenueGrowth', 'N/A'),
                'earnings_growth': info.get('earningsGrowth', 'N/A'),
                'profit_margin': info.get('profitMargins', 'N/A'),
                'roe': info.get('returnOnEquity', 'N/A'),
                'beta': info.get('beta', 'N/A'),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh', 'N/A'),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow', 'N/A'),
                'history': history
            }
            
            return stock_data, None
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                return None, f"❌ Erreur lors de la récupération de {ticker_symbol}: {str(e)}"
    
    return None, f"❌ Échec après {max_retries} tentatives pour {ticker_symbol}"

# ==================== PERSONAS AI ====================
AI_PERSONAS = {
    "Warren (Value Investing)": {
        "prompt": """Tu es Warren Buffett. Analyse cette action selon les principes du Value Investing:
        - Cherche une marge de sécurité (prix < valeur intrinsèque)
        - Évalue la qualité du management et les avantages concurrentiels
        - Privilégie les entreprises avec des flux de trésorerie stables
        - Méfie-toi de la dette excessive
        Donne un avis BUY/HOLD/SELL avec justification détaillée.""",
        "icon": "🎩"
    },
    "Cathie (Growth Disruption)": {
        "prompt": """Tu es Cathie Wood (ARK Invest). Analyse cette action avec l'angle Innovation/Disruption:
        - Identifie le potentiel de croissance exponentielle
        - Évalue les technologies disruptives et l'innovation
        - Accepte la volatilité si le potentiel long-terme est massif
        - Focus sur les mégatrends (IA, génomique, blockchain, etc.)
        Donne un avis BUY/HOLD/SELL avec vision futuriste.""",
        "icon": "🚀"
    },
    "Jim (Technical Analysis)": {
        "prompt": """Tu es Jim Cramer. Analyse cette action avec un mix fondamental + technique:
        - Identifie les patterns graphiques (support/résistance)
        - Évalue le momentum et les volumes
        - Considère le contexte macro-économique
        - Sois incisif et direct dans tes recommandations
        Donne un avis BUY/HOLD/SELL avec ton style énergique.""",
        "icon": "📊"
    }
}

# ==================== FONCTION CALCUL SCORE DE COHÉRENCE ====================
def calculate_coherence_score(data):
    """Calcule un score de cohérence basé sur les métriques financières (0-100)"""
    score = 50  # Score de base
    
    # PE Ratio (idéal entre 10-25)
    pe = data.get('pe_ratio')
    if pe != 'N/A' and pe is not None:
        if 10 <= pe <= 25:
            score += 10
        elif pe > 40:
            score -= 15
    
    # Dette/Equity (bon si < 1.0)
    debt = data.get('debt_to_equity')
    if debt != 'N/A' and debt is not None:
        if debt < 1.0:
            score += 10
        elif debt > 2.0:
            score -= 10
    
    # Free Cashflow (positif = bon)
    fcf = data.get('free_cashflow')
    if fcf != 'N/A' and fcf is not None and fcf > 0:
        score += 10
    elif fcf != 'N/A' and fcf is not None and fcf < 0:
        score -= 15
    
    # Profit Margin (bon si > 10%)
    margin = data.get('profit_margin')
    if margin != 'N/A' and margin is not None:
        if margin > 0.15:
            score += 10
        elif margin < 0.05:
            score -= 10
    
    # ROE (bon si > 15%)
    roe = data.get('roe')
    if roe != 'N/A' and roe is not None:
        if roe > 0.15:
            score += 10
        elif roe < 0.05:
            score -= 5
    
    # Croissance revenus
    rev_growth = data.get('revenue_growth')
    if rev_growth != 'N/A' and rev_growth is not None:
        if rev_growth > 0.15:
            score += 10
        elif rev_growth < 0:
            score -= 10
    
    return max(0, min(100, score))

# ==================== FONCTION VERDICT ====================
def get_verdict(score):
    """Retourne le verdict selon le score de cohérence"""
    if score >= 70:
        return "🟢 STRONG BUY", "#00ff00"
    elif score >= 55:
        return "🟢 BUY", "#00ff41"
    elif score >= 45:
        return "🟡 HOLD", "#ffff00"
    elif score >= 30:
        return "🔴 SELL", "#ff6600"
    else:
        return "🔴 STRONG SELL", "#ff0000"

# ==================== BANDEAU MACRO ====================
def display_macro_banner():
    """Affiche un bandeau avec les indicateurs macro (S&P500, VIX, Taux 10Y)"""
    try:
        # Récupération des indices avec la méthode Stealth
        sp500_data, _ = fetch_stock_data("^GSPC")
        vix_data, _ = fetch_stock_data("^VIX")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if sp500_data:
                sp_price = sp500_data['current_price']
                sp_prev = sp500_data['previous_close']
                sp_change = ((sp_price - sp_prev) / sp_prev * 100) if sp_prev else 0
                st.markdown(f"""
                <div class='macro-banner'>
                    <h4>📈 S&P 500</h4>
                    <p style='font-size: 24px; font-weight: bold;'>{sp_price:.2f}</p>
                    <p style='color: {"#00ff00" if sp_change >= 0 else "#ff0000"};'>
                        {sp_change:+.2f}%
                    </p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("<div class='macro-banner'><h4>📈 S&P 500</h4><p>N/A</p></div>", unsafe_allow_html=True)
        
        with col2:
            if vix_data:
                vix_price = vix_data['current_price']
                st.markdown(f"""
                <div class='macro-banner'>
                    <h4>⚡ VIX (Fear Index)</h4>
                    <p style='font-size: 24px; font-weight: bold;'>{vix_price:.2f}</p>
                    <p style='color: {"#ff0000" if vix_price > 20 else "#00ff00"};'>
                        {"High Volatility" if vix_price > 20 else "Low Volatility"}
                    </p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("<div class='macro-banner'><h4>⚡ VIX</h4><p>N/A</p></div>", unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class='macro-banner'>
                <h4>📅 Market Status</h4>
                <p style='font-size: 18px;'>{datetime.now().strftime('%Y-%m-%d')}</p>
                <p>{datetime.now().strftime('%H:%M:%S')} UTC</p>
            </div>
            """, unsafe_allow_html=True)
            
    except Exception as e:
        st.warning(f"⚠️ Bandeau macro temporairement indisponible: {str(e)}")

# ==================== GRAPHIQUE PLOTLY ====================
def create_price_chart(history, ticker_symbol):
    """Crée un graphique Plotly style Bloomberg avec chandelier et volume"""
    fig = go.Figure()
    
    # Chandelier
    fig.add_trace(go.Candlestick(
        x=history.index,
        open=history['Open'],
        high=history['High'],
        low=history['Low'],
        close=history['Close'],
        name='Price',
        increasing_line_color='#00ff41',
        decreasing_line_color='#ff0000'
    ))
    
    # Volume (axe secondaire)
    fig.add_trace(go.Bar(
        x=history.index,
        y=history['Volume'],
        name='Volume',
        marker_color='rgba(0, 255, 65, 0.3)',
        yaxis='y2'
    ))
    
    # Mise en page Bloomberg Style
    fig.update_layout(
        title=f'{ticker_symbol} - 6 Months Performance',
        yaxis_title='Price (USD)',
        yaxis2=dict(
            title='Volume',
            overlaying='y',
            side='right',
            showgrid=False
        ),
        xaxis_rangeslider_visible=False,
        template='plotly_dark',
        paper_bgcolor='#0a0e27',
        plot_bgcolor='#1a1f3a',
        font=dict(color='#00ff41', family='Courier New'),
        hovermode='x unified',
        height=500
    )
    
    return fig

# ==================== INTERFACE PRINCIPALE ====================
def main():
    # Header
    st.markdown("<h1 style='text-align: center; font-size: 48px;'>📈 AI HUNTER V21</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 18px;'>Bloomberg Terminal Style - Multi-Persona AI Stock Analysis</p>", unsafe_allow_html=True)
    
    # Bandeau Macro
    display_macro_banner()
    
    st.markdown("---")
    
    # Zone de saisie
    col1, col2 = st.columns([2, 1])
    
    with col1:
        ticker_input = st.text_input(
            "🔍 Enter Ticker Symbol (e.g., AAPL, TSLA, GOOGL)",
            value="AAPL",
            key="ticker"
        ).upper()
    
    with col2:
        selected_persona = st.selectbox(
            "🤖 Select AI Persona",
            list(AI_PERSONAS.keys()),
            key="persona"
        )
    
    analyze_button = st.button("🚀 ANALYZE STOCK", type="primary", use_container_width=True)
    
    # Analyse
    if analyze_button and ticker_input:
        with st.spinner(f"🔄 Fetching data for {ticker_input}... (Stealth Mode Active)"):
            stock_data, error = fetch_stock_data(ticker_input)
            
            if error:
                st.error(error)
                st.markdown("""
                <div class='alert-box'>
                    <h4>❌ Échec de récupération</h4>
                    <p>Raisons possibles:</p>
                    <ul>
                        <li>Ticker invalide ou inexistant</li>
                        <li>Blocage IP Yahoo Finance persistant (essayez plus tard)</li>
                        <li>Marché fermé (certaines données peuvent être indisponibles)</li>
                    </ul>
                    <p><b>Note:</b> Aucune donnée fictive ne sera affichée.</p>
                </div>
                """, unsafe_allow_html=True)
                return
            
            # Affichage des données réelles
            st.success(f"✅ Données récupérées avec succès pour {stock_data['name']}")
            
            # Prix et changement
            current_price = stock_data['current_price']
            previous_close = stock_data['previous_close']
            price_change = current_price - previous_close
            price_change_pct = (price_change / previous_close * 100) if previous_close else 0
            
            # En-tête prix
            st.markdown(f"""
            <div style='background-color: #1a1f3a; padding: 20px; border-radius: 10px; border: 2px solid #00ff41; margin-bottom: 20px;'>
                <h2 style='margin: 0;'>{stock_data['symbol']} - {stock_data['name']}</h2>
                <h1 style='font-size: 48px; margin: 10px 0;'>${current_price:.2f}</h1>
                <p style='font-size: 24px; color: {"#00ff00" if price_change >= 0 else "#ff0000"}; margin: 0;'>
                    {price_change:+.2f} ({price_change_pct:+.2f}%)
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Graphique
            st.plotly_chart(create_price_chart(stock_data['history'], ticker_input), use_container_width=True)
            
            # Métriques Financières
            st.markdown("### 📊 Métriques Financières")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                pe = stock_data['pe_ratio']
                st.metric("P/E Ratio", f"{pe:.2f}" if pe != 'N/A' and pe is not None else "N/A")
                
                market_cap = stock_data['market_cap']
                if market_cap != 'N/A' and market_cap is not None:
                    market_cap_b = market_cap / 1e9
                    st.metric("Market Cap", f"${market_cap_b:.2f}B")
                else:
                    st.metric("Market Cap", "N/A")
            
            with col2:
                debt = stock_data['debt_to_equity']
                st.metric("Debt/Equity", f"{debt:.2f}" if debt != 'N/A' and debt is not None else "N/A")
                
                div_yield = stock_data['dividend_yield']
                if div_yield and div_yield != 'N/A':
                    st.metric("Dividend Yield", f"{div_yield*100:.2f}%")
                else:
                    st.metric("Dividend Yield", "N/A")
            
            with col3:
                fcf = stock_data['free_cashflow']
                if fcf != 'N/A' and fcf is not None:
                    fcf_m = fcf / 1e6
                    st.metric("Free Cashflow", f"${fcf_m:.2f}M")
                else:
                    st.metric("Free Cashflow", "N/A")
                
                margin = stock_data['profit_margin']
                if margin != 'N/A' and margin is not None:
                    st.metric("Profit Margin", f"{margin*100:.2f}%")
                else:
                    st.metric("Profit Margin", "N/A")
            
            with col4:
                roe = stock_data['roe']
                if roe != 'N/A' and roe is not None:
                    st.metric("ROE", f"{roe*100:.2f}%")
                else:
                    st.metric("ROE", "N/A")
                
                beta = stock_data['beta']
                st.metric("Beta", f"{beta:.2f}" if beta != 'N/A' and beta is not None else "N/A")
            
            # Score de Cohérence
            st.markdown("---")
            coherence_score = calculate_coherence_score(stock_data)
            verdict, color = get_verdict(coherence_score)
            
            st.markdown(f"""
            <div style='background-color: #1a1f3a; padding: 20px; border-radius: 10px; border: 3px solid {color}; text-align: center;'>
                <h3>🎯 Score de Cohérence Financière</h3>
                <h1 style='font-size: 64px; color: {color}; margin: 10px 0;'>{coherence_score}/100</h1>
                <h2 style='color: {color};'>{verdict}</h2>
            </div>
            """, unsafe_allow_html=True)
            
            # Analyse AI (Section Persona)
            st.markdown("---")
            st.markdown(f"### {AI_PERSONAS[selected_persona]['icon']} Analyse par {selected_persona}")
            
            persona_prompt = AI_PERSONAS[selected_persona]['prompt']
            
            # Construction du contexte pour l'AI
            ai_context = f"""
            Ticker: {stock_data['symbol']}
            Nom: {stock_data['name']}
            Prix actuel: ${current_price:.2f}
            Variation: {price_change_pct:+.2f}%
            
            Métriques:
            - P/E Ratio: {stock_data['pe_ratio']}
            - Market Cap: {stock_data['market_cap']}
            - Debt/Equity: {stock_data['debt_to_equity']}
            - Free Cashflow: {stock_data['free_cashflow']}
            - Profit Margin: {stock_data['profit_margin']}
            - ROE: {stock_data['roe']}
            - Revenue Growth: {stock_data['revenue_growth']}
            
            Score de Cohérence: {coherence_score}/100
            Verdict Algorithmique: {verdict}
            
            {persona_prompt}
            """
            
            st.markdown(f"""
            <div class='alert-box'>
                <p><b>🤖 Analyse AI {selected_persona}:</b></p>
                <p><i>Note: Pour une analyse AI complète, intégrez Claude API ou GPT-4 via Streamlit Secrets.</i></p>
                <p>Contexte transmis:</p>
                <pre style='background-color: #0a0e27; padding: 10px; border-radius: 5px; overflow-x: auto;'>{ai_context}</pre>
            </div>
            """, unsafe_allow_html=True)
            
            # Export CSV
            st.markdown("---")
            if st.button("📥 Export Data to CSV", use_container_width=True):
                export_data = {
                    'Ticker': [stock_data['symbol']],
                    'Name': [stock_data['name']],
                    'Current Price': [current_price],
                    'Change %': [price_change_pct],
                    'P/E Ratio': [stock_data['pe_ratio']],
                    'Market Cap': [stock_data['market_cap']],
                    'Debt/Equity': [stock_data['debt_to_equity']],
                    'Free Cashflow': [stock_data['free_cashflow']],
                    'Profit Margin': [stock_data['profit_margin']],
                    'ROE': [stock_data['roe']],
                    'Coherence Score': [coherence_score],
                    'Verdict': [verdict],
                    'Analysis Date': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                }
                
                df_export = pd.DataFrame(export_data)
                csv = df_export.to_csv(index=False)
                
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv,
                    file_name=f"{ticker_input}_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; padding: 20px; color: #00ff41; opacity: 0.7;'>
        <p>AI Hunter V21 - Bloomberg Terminal Style</p>
        <p>Powered by Stealth Yahoo Finance Integration | No Fake Data Policy</p>
        <p>⚠️ This is not financial advice. Always do your own research.</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()