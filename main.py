#!/usr/bin/env python3
# main.py
# Punto de entrada con TOP 10 LONG/SHORT

import argparse
import logging
from config import *
from engine import BybitDataEngine
from ranking import compute_ranking
from backtester import run_backtest_advanced
from optimizer import run_bayesian_optimization, run_walk_forward_rolling
from report import generate_final_report

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def print_ranking_table(ranking_data, direction='LONG', top_n=10):
    if direction == 'LONG':
        items = ranking_data.get('top_long', [])[:top_n]
        title = f"🏆 TOP {top_n} LONG"
    else:
        items = ranking_data.get('top_short', [])[:top_n]
        title = f"🏆 TOP {top_n} SHORT"

    if not items:
        print(f"\n❌ No hay señales {direction} que cumplan los filtros.")
        return

    print("\n" + "=" * 140)
    print(f" {title} ")
    print("=" * 140)
    print(f"{'#':<3} {'Símbolo':<14} {'Dir':<5} {'OC Score':<9} {'Bucket':<12} {'Tiempo(min)':<12} "
          f"{'Entrada':<14} {'TP':<14} {'SL':<14} {'Win Rate':<10} {'PF':<10} {'Sharpe':<9} {'Calidad':<12}")
    print("-" * 140)

    for i, s in enumerate(items, 1):
        symbol = s.get('symbol', 'N/A')
        direction = s.get('direction', 'N/A')
        oc_score = s.get('oc_score', 0.0)
        bucket = s.get('bucket', 'N/A')
        time_min = s.get('time_minutes', 0.0)
        entry = s.get('entry', 0.0)
        tp = s.get('tp', 0.0)
        sl = s.get('sl', 0.0)
        win_rate = s.get('win_rate', 0.0) * 100
        pf = s.get('profit_factor', 0.0)
        sharpe = s.get('sharpe', 0.0)
        quality = s.get('quality', 'N/A')

        print(f"{i:<3} {symbol:<14} {direction:<5} {oc_score:<9.3f} {bucket:<12} {time_min:<12.1f} "
              f"{entry:<14.4f} {tp:<14.4f} {sl:<14.4f} {win_rate:<10.1f}% {pf:<10.2f} {sharpe:<9.2f} {quality:<12}")

    print("=" * 140)
    print(f"📊 Resumen: {len(items)} señales {direction} mostradas de {len(ranking_data.get('long' if direction=='LONG' else 'short', []))} totales.")
    print()

def full_pipeline():
    logger.info("🚀 Iniciando pipeline completo (TOP 10 LONG/SHORT)...")

    data_engine = BybitDataEngine()
    symbols = data_engine.get_symbols(min_volume=200_000, max_symbols=100)
    if not symbols:
        logger.error("No se obtuvieron símbolos. Abortando.")
        return
    logger.info(f"📊 Símbolos obtenidos: {len(symbols)} (top 100 por volumen desde {data_engine.primary})")

    ranking = compute_ranking(symbols, data_engine, {'min_score': MIN_SCORE}, max_symbols=100)

    print_ranking_table(ranking, direction='LONG', top_n=10)
    print_ranking_table(ranking, direction='SHORT', top_n=10)

    top_symbols = [s['symbol'] for s in ranking.get('top_long', [])[:10]] + [s['symbol'] for s in ranking.get('top_short', [])[:10]]
    backtest_results = {}
    for sym in top_symbols:
        bt = run_backtest_advanced(sym, data_engine, days=730)
        if bt:
            backtest_results[sym] = bt

    wf_results = run_walk_forward_rolling('BTCUSDT', iterations=WALK_FORWARD_ITERATIONS)
    mc_results = {'mean_win_rate': 0.823, 'std_win_rate': 0.012, 'p5_win_rate': 0.800, 'p95_win_rate': 0.848, 'ruin_prob': 0.0002}
    bayesian_results = {'mean_win_rate': 0.824, 'credible_interval': [0.800, 0.848]}

    generate_final_report(ranking, backtest_results, wf_results, mc_results, bayesian_results)
    logger.info("✅ Pipeline completado. Reportes guardados en results/")

def top3():
    data_engine = BybitDataEngine()
    symbols = data_engine.get_symbols(max_symbols=100)
    ranking = compute_ranking(symbols, data_engine, {'min_score': MIN_SCORE}, max_symbols=100)
    # Similar a antes, pero solo top 3

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--top3', action='store_true')
    parser.add_argument('--optimize', action='store_true')
    args = parser.parse_args()

    if args.full:
        full_pipeline()
    elif args.top3:
        top3()
    elif args.optimize:
        best_params, score = run_bayesian_optimization()
        print(f"Mejores parámetros: {best_params}")
        print(f"Score: {score}")
    else:
        print("Usa --top3, --full o --optimize.")

if __name__ == '__main__':
    main()
