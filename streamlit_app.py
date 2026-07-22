# streamlit_app.py
# Dashboard profesional para Golden Capital Engine Ω

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from datetime import datetime
from config import RESULTS_DIR

st.set_page_config(page_title="Golden Capital Engine Ω - Binance Futures", layout="wide")
st.title("🏛️ GOLDEN CAPITAL ENGINE Ω — BINANCE FUTURES QUANT ENGINE")

# =============================================================================
# CARGA DE RESULTADOS
# =============================================================================

ranking = {}
backtest = {}

try:
    with open(os.path.join(RESULTS_DIR, 'ranking.json'), 'r') as f:
        ranking = json.load(f)
except:
    pass

try:
    with open(os.path.join(RESULTS_DIR, 'backtest_2years.json'), 'r') as f:
        backtest = json.load(f)
except:
    pass

# =============================================================================
# SIDEBAR
# =============================================================================

st.sidebar.header("📊 Estado del sistema")
st.sidebar.write(f"Ranking: {'✅' if ranking else '❌'}")
st.sidebar.write(f"Backtest: {'✅' if backtest else '❌'}")
st.sidebar.write(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# =============================================================================
# TABS
# =============================================================================

tabs = st.tabs([
    "📊 Dashboard",
    "🏆 TOP 10 LONG",
    "🏆 TOP 10 SHORT",
    "📈 Backtest 2 años",
    "🔬 DAPS 4",
    "📋 Informe",
])

# =============================================================================
# TAB 0: DASHBOARD
# =============================================================================

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
            st.dataframe(df_long[['symbol', 'score', 'confidence', 'entry', 'tp', 'sl', 'leverage', 'hours_to_entry']])
        
        # TOP 5 SHORT
        st.subheader("🏅 TOP 5 SHORT - Próximas oportunidades")
        top5_short = ranking.get('short', [])[:5]
        if top5_short:
            df_short = pd.DataFrame(top5_short)
            st.dataframe(df_short[['symbol', 'score', 'confidence', 'entry', 'tp', 'sl', 'leverage', 'hours_to_entry']])
    else:
        st.info("Ejecuta `python main.py --full` para generar datos.")

# =============================================================================
# TAB 1: TOP 10 LONG
# =============================================================================

with tabs[1]:
    if ranking and ranking.get('long'):
        df_long = pd.DataFrame(ranking['long'])
        st.dataframe(df_long[['symbol', 'score', 'confidence', 'win_rate', 'profit_factor',
                              'sharpe', 'entry', 'tp', 'sl', 'leverage', 'hours_to_entry']])
        fig = px.bar(df_long, x='symbol', y='score', title='Scores TOP 10 LONG')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos LONG disponibles.")

# =============================================================================
# TAB 2: TOP 10 SHORT
# =============================================================================

with tabs[2]:
    if ranking and ranking.get('short'):
        df_short = pd.DataFrame(ranking['short'])
        st.dataframe(df_short[['symbol', 'score', 'confidence', 'win_rate', 'profit_factor',
                               'sharpe', 'entry', 'tp', 'sl', 'leverage', 'hours_to_entry']])
        fig = px.bar(df_short, x='symbol', y='score', title='Scores TOP 10 SHORT')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos SHORT disponibles.")

# =============================================================================
# TAB 3: BACKTEST 2 AÑOS
# =============================================================================

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
        st.info("Ejecuta `python main.py --full` para backtesting.")

# =============================================================================
# TAB 4: DAPS 4
# =============================================================================

with tabs[4]:
    st.subheader("🔬 Laboratorio DAPS 4")
    st.markdown("""
    **DAPS Iteración 1: Análisis de pérdidas** - Clasifica pérdidas por tipo
    **DAPS Iteración 2: Optimización de salida** - TP/SL/Trailing por activo
    **DAPS Iteración 3: Optimización de entrada** - Score, ADX, KER ajustados
    **DAPS Iteración 4: Expansión del universo** - Todos los futuros USDT
    """)

# =============================================================================
# TAB 5: INFORME
# =============================================================================

with tabs[5]:
    st.subheader("📋 Informe FINAL_REPORT.csv")
    try:
        df_report = pd.read_csv(os.path.join(RESULTS_DIR, 'FINAL_REPORT.csv'))
        st.dataframe(df_report)
        st.download_button("📥 Descargar CSV", df_report.to_csv(index=False), "FINAL_REPORT.csv")
    except:
        st.info("Ejecuta `python main.py --full` para generar el informe.")
