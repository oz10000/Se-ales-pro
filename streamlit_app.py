# streamlit_app.py
# Dashboard profesional con top 3, coherencia, buckets y detalle

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from config import RESULTS_DIR
from datetime import datetime

st.set_page_config(page_title="Golden Capital Engine Ω - Bybit Futures", layout="wide")
st.title("🏛️ GOLDEN CAPITAL ENGINE Ω — BYBIT FUTURES QUANT ENGINE")

# Cargar resultados
ranking = {}
backtest = {}
try:
    with open(os.path.join(RESULTS_DIR, 'ranking.json'), 'r') as f:
        ranking = json.load(f)
except:
    pass

try:
    with open(os.path.join(RESULTS_DIR, 'backtest_by_asset.csv'), 'r') as f:
        backtest = pd.read_csv(f)
except:
    pass

st.sidebar.header("📊 Estado")
st.sidebar.write(f"Ranking: {'✅' if ranking else '❌'}")
st.sidebar.write(f"Backtest: {'✅' if backtest else '❌'}")

if ranking:
    top_long = ranking.get('top_long', [])
    top_short = ranking.get('top_short', [])

    tabs = st.tabs(["📊 Dashboard", "🏆 TOP 3 LONG", "🏆 TOP 3 SHORT", "📈 Backtest", "📋 Informe"])

    with tabs[0]:
        col1, col2, col3 = st.columns(3)
        col1.metric("Activos analizados", ranking.get('total_analyzed', 0))
        col2.metric("TOP LONG", len(top_long))
        col3.metric("TOP SHORT", len(top_short))

        st.subheader("🏅 TOP 3 LONG")
        for i, s in enumerate(top_long):
            with st.expander(f"#{i+1} {s['symbol']} — OC: {s['oc_score']:.3f}"):
                st.write(f"**Coherencia:** {s['coherence']:.0%} | **Bucket:** {s['bucket']} | **Tiempo:** {s['time_minutes']:.1f} min")
                st.write(f"**Entrada:** {s['entry']:.4f} | **TP:** {s['tp']:.4f} | **SL:** {s['sl']:.4f}")
                st.write(f"**Calidad:** {s['quality']} | **Win Rate:** {s['win_rate']:.1%} | **PF:** {s['profit_factor']:.2f}")

        st.subheader("🏅 TOP 3 SHORT")
        for i, s in enumerate(top_short):
            with st.expander(f"#{i+1} {s['symbol']} — OC: {s['oc_score']:.3f}"):
                # similar

    with tabs[1]:
        if top_long:
            df = pd.DataFrame(top_long)
            st.dataframe(df[['symbol', 'oc_score', 'coherence', 'bucket', 'entry', 'tp', 'sl', 'quality']])
            fig = px.bar(df, x='symbol', y='oc_score', title='TOP 3 LONG Scores')
            st.plotly_chart(fig)
        else:
            st.info("No hay TOP 3 LONG")

    with tabs[2]:
        # similar para short

    with tabs[3]:
        if backtest:
            st.dataframe(backtest)

    with tabs[4]:
        st.subheader("📋 Informe de validación")
        try:
            with open(os.path.join(RESULTS_DIR, 'montecarlo.json'), 'r') as f:
                mc = json.load(f)
                st.json(mc)
        except:
            st.info("Ejecuta --full para generar el informe.")

else:
    st.info("Ejecuta `python main.py --full` para generar resultados.")
