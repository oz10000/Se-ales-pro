# streamlit_app.py
# Dashboard profesional para Golden Capital Engine Ω

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import sys
import time
from datetime import datetime
from config import RESULTS_DIR

# Configurar la página
st.set_page_config(page_title="Golden Capital Engine Ω - Binance Futures", layout="wide")
st.title("🏛️ GOLDEN CAPITAL ENGINE Ω — BINANCE FUTURES QUANT ENGINE")

# =============================================================================
# FUNCIÓN PARA EJECUTAR EL PIPELINE DESDE STREAMLIT
# =============================================================================

def run_pipeline():
    """Ejecuta el pipeline completo dentro de Streamlit."""
    with st.spinner("🔄 Escaneando Binance Futures... esto puede tomar varios minutos."):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        try:
            from main import full_pipeline
            
            status_text.text("📡 Conectando a Binance...")
            progress_bar.progress(10)
            
            results = full_pipeline()
            
            progress_bar.progress(100)
            status_text.text("✅ Pipeline completado con éxito!")
            
            st.session_state.results = results
            st.session_state.data_loaded = True
            st.session_state.timestamp = datetime.now().isoformat()
            
            load_results_from_files()
            return True
        except Exception as e:
            st.error(f"❌ Error al ejecutar el pipeline: {e}")
            st.exception(e)
            return False

def load_results_from_files():
    """Carga los resultados desde los archivos JSON generados."""
    ranking_path = os.path.join(RESULTS_DIR, 'ranking.json')
    backtest_path = os.path.join(RESULTS_DIR, 'backtest_2years.json')
    
    if os.path.exists(ranking_path):
        with open(ranking_path, 'r') as f:
            st.session_state.ranking = json.load(f)
    else:
        st.session_state.ranking = {}
    
    if os.path.exists(backtest_path):
        with open(backtest_path, 'r') as f:
            st.session_state.backtest = json.load(f)
    else:
        st.session_state.backtest = {}

# =============================================================================
# INICIALIZACIÓN DE SESIÓN
# =============================================================================

if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
    st.session_state.ranking = {}
    st.session_state.backtest = {}
    st.session_state.results = None
    st.session_state.timestamp = None

# Intentar cargar archivos existentes al inicio
if not st.session_state.data_loaded:
    load_results_from_files()
    if st.session_state.ranking or st.session_state.backtest:
        st.session_state.data_loaded = True
        st.session_state.timestamp = datetime.now().isoformat()

# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.header("⚙️ Acciones")
    
    if st.button("🔄 Escanear Binance Futures", type="primary", use_container_width=True):
        with st.spinner("Iniciando escaneo..."):
            success = run_pipeline()
            if success:
                st.success("✅ Datos actualizados correctamente")
                st.rerun()
    
    st.markdown("---")
    
    st.header("📊 Estado del sistema")
    st.write(f"Ranking: {'✅' if st.session_state.ranking else '❌'}")
    st.write(f"Backtest: {'✅' if st.session_state.backtest else '❌'}")
    if st.session_state.timestamp:
        st.write(f"Última actualización: {st.session_state.timestamp[:19]}")
    else:
        st.write("Última actualización: -")

# =============================================================================
# PÁGINA PRINCIPAL
# =============================================================================

if st.session_state.data_loaded and (st.session_state.ranking or st.session_state.backtest):
    ranking = st.session_state.ranking
    backtest = st.session_state.backtest
    
    tabs = st.tabs([
        "📊 Dashboard",
        "🏆 TOP 10 LONG",
        "🏆 TOP 10 SHORT",
        "📈 Backtest 2 años",
        "🔬 DAPS 4",
        "📋 Informe",
    ])
    
    # TAB 0: DASHBOARD
    with tabs[0]:
        if ranking:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Activos analizados", ranking.get('total_analyzed', 0))
            col2.metric("TOP LONG", len(ranking.get('long', [])))
            col3.metric("TOP SHORT", len(ranking.get('short', [])))
            col4.metric("Timestamp", ranking.get('timestamp', '')[:19])
            
            st.success("✅ Sistema operativo. Datos cargados correctamente.")
            
            # TOP 5 LONG
            st.subheader("🏅 TOP 5 LONG - Próximas oportunidades")
            top5_long = ranking.get('long', [])[:5]
            if top5_long:
                df_long = pd.DataFrame(top5_long)
                df_long['Aprobado'] = df_long['approved'].apply(lambda x: '✅' if x else '❌')
                st.dataframe(df_long[['symbol', 'score', 'adx', 'ker', 'regime', 'Aprobado', 'entry', 'tp', 'sl', 'leverage', 'hours_to_entry']])
            
            # TOP 5 SHORT
            st.subheader("🏅 TOP 5 SHORT - Próximas oportunidades")
            top5_short = ranking.get('short', [])[:5]
            if top5_short:
                df_short = pd.DataFrame(top5_short)
                df_short['Aprobado'] = df_short['approved'].apply(lambda x: '✅' if x else '❌')
                st.dataframe(df_short[['symbol', 'score', 'adx', 'ker', 'regime', 'Aprobado', 'entry', 'tp', 'sl', 'leverage', 'hours_to_entry']])
            
            # Explicación si no hay aprobados
            approved_long = [x for x in ranking.get('long', []) if x.get('approved', False)]
            approved_short = [x for x in ranking.get('short', []) if x.get('approved', False)]
            if not approved_long and not approved_short:
                st.warning("⚠️ No hay señales que cumplan todos los criterios. Se muestran los mejores candidatos.")
                st.info("Para ver más señales, ajusta los umbrales en config.py (MIN_SCORE, ADX_THRESHOLD, KER_THRESHOLD).")
        else:
            st.info("No hay datos de ranking disponibles.")
    
    # TAB 1: TOP 10 LONG
    with tabs[1]:
        if ranking and ranking.get('long'):
            df_long = pd.DataFrame(ranking['long'])
            df_long['Aprobado'] = df_long['approved'].apply(lambda x: '✅' if x else '❌')
            st.dataframe(df_long[['symbol', 'score', 'adx', 'ker', 'regime', 'Aprobado', 'entry', 'tp', 'sl', 'leverage', 'hours_to_entry']])
            fig = px.bar(df_long, x='symbol', y='score', color='approved', title='Scores TOP 10 LONG')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos LONG disponibles.")
    
    # TAB 2: TOP 10 SHORT
    with tabs[2]:
        if ranking and ranking.get('short'):
            df_short = pd.DataFrame(ranking['short'])
            df_short['Aprobado'] = df_short['approved'].apply(lambda x: '✅' if x else '❌')
            st.dataframe(df_short[['symbol', 'score', 'adx', 'ker', 'regime', 'Aprobado', 'entry', 'tp', 'sl', 'leverage', 'hours_to_entry']])
            fig = px.bar(df_short, x='symbol', y='score', color='approved', title='Scores TOP 10 SHORT')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos SHORT disponibles.")
    
    # TAB 3: BACKTEST (sin cambios)
    with tabs[3]:
        if backtest:
            selected = st.selectbox("Seleccionar activo", list(backtest.keys()))
            if selected:
                data = backtest[selected]
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Win Rate", f"{data.get('win_rate', 0):.1%}")
                col2.metric("Profit Factor", f"{data.get('profit_factor', 0):.2f}")
                col3.metric("Sharpe", f"{data.get('sharpe', 0):.2f}")
                col4.metric("Drawdown", f"{data.get('max_drawdown', 0):.1f}%")
                eq = data.get('equity_curve', [])
                if eq:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(y=eq, mode='lines', name='Equity'))
                    fig.update_layout(title='Curva de capital', xaxis_title='Trade', yaxis_title='Capital (USDT)')
                    st.plotly_chart(fig, use_container_width=True)
                trades = data.get('trades', [])
                if trades:
                    df_t = pd.DataFrame(trades[-20:])
                    st.dataframe(df_t[['entry_time', 'direction', 'entry', 'exit', 'pnl_pct', 'exit_reason']])
        else:
            st.info("No hay datos de backtesting disponibles.")
    
    # TAB 4: DAPS 4
    with tabs[4]:
        st.subheader("🔬 Laboratorio DAPS 4")
        st.markdown("""
        **DAPS Iteración 1: Análisis de pérdidas** - Clasifica pérdidas por tipo
        **DAPS Iteración 2: Optimización de salida** - TP/SL/Trailing por activo
        **DAPS Iteración 3: Optimización de entrada** - Score, ADX, KER ajustados
        **DAPS Iteración 4: Expansión del universo** - Todos los futuros USDT
        """)
        daps_path = os.path.join(RESULTS_DIR, 'daps_history.json')
        if os.path.exists(daps_path):
            with open(daps_path, 'r') as f:
                daps_hist = json.load(f)
                st.json(daps_hist)
        else:
            st.info("Ejecuta el escaneo para generar el historial DAPS.")
    
    # TAB 5: INFORME
    with tabs[5]:
        st.subheader("📋 Informe FINAL_REPORT.csv")
        try:
            df_report = pd.read_csv(os.path.join(RESULTS_DIR, 'FINAL_REPORT.csv'))
            st.dataframe(df_report)
            st.download_button("📥 Descargar CSV", df_report.to_csv(index=False), "FINAL_REPORT.csv")
        except:
            st.info("Ejecuta el escaneo para generar el informe.")

else:
    st.info("👋 Bienvenido a Golden Capital Engine Ω.\n\nHaz clic en **'Escanear Binance Futures'** en la barra lateral para generar el análisis en tiempo real desde Binance Futures.")
    st.markdown("""
    ### 📊 ¿Qué hace este sistema?
    - Escanea todos los futuros USDT de Binance con volumen suficiente.
    - Calcula indicadores (ADX, KER, PiDelta Score, régimen, etc.)
    - Genera un ranking de los mejores activos LONG y SHORT.
    - Optimiza parámetros por activo (TP, SL, trailing, leverage).
    - Realiza backtesting de 2 años con datos históricos reales.
    - Muestra métricas (Win Rate, Profit Factor, Sharpe, Drawdown).
    """)

st.sidebar.markdown("---")
st.sidebar.caption("Golden Capital Engine Ω v3.0 — Binance Futures")
st.sidebar.caption("Fecha del sistema: " + datetime.now().strftime('%Y-%m-%d %H:%M'))
