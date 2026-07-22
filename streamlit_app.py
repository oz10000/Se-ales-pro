# streamlit_app.py
# Dashboard profesional con TOP 5 y tiempo estimado

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from config import RESULTS_DIR

st.set_page_config(page_title="Golden Capital Engine Ω - Bybit Futures", layout="wide")
st.title("🏛️ GOLDEN CAPITAL ENGINE Ω — BYBIT FUTURES QUANT ENGINE")

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

st.sidebar.header("📊 Estado del sistema")
st.sidebar.write(f"Ranking: {'✅' if ranking else '❌'}")
st.sidebar.write(f"Backtest: {'✅' if backtest else '❌'}")

tabs = st.tabs([
    "📊 Dashboard",
    "🏆 TOP 10 LONG",
    "🏆 TOP 10 SHORT",
    "📈 Backtest 2 años",
    "🔬 DAPS 4",
    "📋 Informe",
])

with tabs[0]:
    if ranking:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Activos analizados", ranking.get('total_analyzed', 0))
        col2.metric("TOP LONG", len(ranking.get('long', [])))
        col3.metric("TOP SHORT", len(ranking.get('short', [])))
        col4.metric("Timestamp", ranking.get('timestamp', '')[:19])
        st.success("✅ Sistema operativo. Datos cargados correctamente.")

        # Mostrar TOP 5 LONG con tiempo estimado
        st.subheader("🏅 TOP 5 LONG - Próximas oportunidades")
        top5_long = ranking.get('long', [])[:5]
        if top5_long:
            df_top = pd.DataFrame(top5_long)
            st.dataframe(df_top[['symbol', 'confidence', 'entry', 'tp', 'sl',
                                 'leverage', 'hours_to_entry', 'hours_to_tp']])

        # Mostrar TOP 5 SHORT con tiempo estimado
        st.subheader("🏅 TOP 5 SHORT - Próximas oportunidades")
        top5_short = ranking.get('short', [])[:5]
        if top5_short:
            df_top = pd.DataFrame(top5_short)
            st.dataframe(df_top[['symbol', 'confidence', 'entry', 'tp', 'sl',
                                 'leverage', 'hours_to_entry', 'hours_to_tp']])

        # Predicción de próxima señal
        st.subheader("⏱️ Predicción de próxima señal")
        all_signals = ranking.get('long', []) + ranking.get('short', [])
        if all_signals:
            next_signal = min(all_signals, key=lambda x: x.get('hours_to_entry', 99))
            col1, col2, col3 = st.columns(3)
            col1.metric("Próximo activo", next_signal['symbol'])
            col2.metric("Dirección", next_signal['direction'])
            col3.metric("Tiempo estimado", f"{next_signal.get('hours_to_entry', 0):.1f} horas")
    else:
        st.info("Ejecuta `python main.py --full` para generar datos.")

with tabs[1]:
    if ranking and ranking.get('long'):
        df_long = pd.DataFrame(ranking['long'])
        st.dataframe(df_long[['symbol', 'score', 'confidence', 'win_rate', 'profit_factor',
                              'sharpe', 'entry', 'tp', 'sl', 'leverage', 'hours_to_entry']])
        fig = px.bar(df_long, x='symbol', y='score', title='Scores TOP 10 LONG')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos LONG disponibles.")

with tabs[2]:
    if ranking and ranking.get('short'):
        df_short = pd.DataFrame(ranking['short'])
        st.dataframe(df_short[['symbol', 'score', 'confidence', 'win_rate', 'profit_factor',
                               'sharpe', 'entry', 'tp', 'sl', 'leverage', 'hours_to_entry']])
        fig = px.bar(df_short, x='symbol', y='score', title='Scores TOP 10 SHORT')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos SHORT disponibles.")

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

with tabs[4]:
    st.subheader("🔬 Laboratorio DAPS 4")
    st.markdown("""
    **DAPS Iteración 1: Análisis de pérdidas** - Clasifica pérdidas por tipo
    **DAPS Iteración 2: Optimización de salida** - TP/SL/Trailing por activo
    **DAPS Iteración 3: Optimización de entrada** - Score, ADX, KER ajustados
    **DAPS Iteración 4: Expansión del universo** - Todos los futuros USDT
    """)

with tabs[5]:
    st.subheader("📋 Informe FINAL_REPORT.csv")
    try:
        df_report = pd.read_csv(os.path.join(RESULTS_DIR, 'FINAL_REPORT.csv'))
        st.dataframe(df_report)
        st.download_button("📥 Descargar CSV", df_report.to_csv(index=False), "FINAL_REPORT.csv")
    except:
        st.info("Ejecuta `python main.py --full` para generar el informe.")
