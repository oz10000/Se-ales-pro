#!/usr/bin/env python3
# main.py
# Punto de entrada con pipeline DAPS completo

import argparse
import json
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from config import *
from engine import BybitDataEngine, generate_signal
from backtester import run_backtest_advanced
from ranking import compute_ranking, optimize_asset_deep
from optimizer import run_daps_full, run_walk_forward_professional, run_monte_carlo_professional, run_optuna_global
from report import (generate_final_report, generate_top_ranking,
                    generate_optimized_parameters, generate_daps_history,
                    generate_global_summary)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def full_pipeline():
    logger.info("🚀 Iniciando pipeline completo con DAPS 4...")

    data_engine = BybitDataEngine()
    symbols = data_engine.get_symbols()
    logger.info(f"Universo: {len(symbols)} símbolos")

    logger.info("🔬 Ejecutando DAPS 4...")
    daps_result = run_daps_full(data_engine, symbols, iterations=4)
    best_params = daps_result['best_params']
    logger.info(f"Mejores parámetros encontrados: {best_params}")

    logger.info("📊 Generando ranking optimizado...")
    ranking = compute_ranking(symbols, data_engine, best_params)
    logger.info(f"TOP LONG: {len(ranking['long'])} | TOP SHORT: {len(ranking['short'])}")
    logger.info(f"Total analizados: {ranking.get('total_analyzed', 0)}")

    # Mostrar estadísticas de activos aprobados vs no aprobados
    all_assets = ranking.get('all', [])
    approved = [a for a in all_assets if a.get('approved', False)]
    logger.info(f"Activos aprobados: {len(approved)} de {len(all_assets)}")

    # Si no hay señales aprobadas, igualmente el ranking mostrará los mejores candidatos
    if len(approved) == 0:
        logger.info("⚠️ No hay activos que cumplan todos los criterios. Mostrando candidatos por puntuación.")
    else:
        logger.info(f"✅ {len(approved)} activos aprobados")

    # Optimización TOP 5 LONG y SHORT (con los mejores, aunque no estén aprobados)
    logger.info("🔍 Optimizando TOP 5 LONG y SHORT...")
    optimized = []
    for item in ranking.get('long_deep', []) + ranking.get('short_deep', []):
        opt = optimize_asset_deep(item['symbol'], item['direction'], data_engine, best_params)
        if opt:
            optimized.append(opt)

    logger.info("📈 Ejecutando backtesting 2 años...")
    backtest_results = {}
    for sym in symbols[:30]:
        bt = run_backtest_advanced(sym, data_engine, best_params, days=730)
        if bt:
            backtest_results[sym] = bt

    logger.info("🔄 Ejecutando Walk Forward...")
    wf_results = {}
    for sym in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']:
        wf = run_walk_forward_professional(sym, data_engine, best_params)
        if wf:
            wf_results[sym] = wf

    logger.info("🎲 Ejecutando Monte Carlo...")
    mc_results = {}
    for sym in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']:
        mc = run_monte_carlo_professional(sym, data_engine, best_params)
        if mc:
            mc_results[sym] = mc

    logger.info("📋 Generando reportes...")
    df_report = generate_final_report(optimized, data_engine, best_params)
    generate_top_ranking(ranking)
    generate_optimized_parameters(optimized)
    generate_daps_history(daps_result)
    global_summary = generate_global_summary(backtest_results, ranking)

    # Guardar todos los resultados
    with open('results/ranking.json', 'w') as f:
        json.dump(ranking, f, indent=2, default=str)
    with open('results/backtest_2years.json', 'w') as f:
        json.dump(backtest_results, f, indent=2, default=str)
    with open('results/walkforward.json', 'w') as f:
        json.dump(wf_results, f, indent=2, default=str)
    with open('results/montecarlo.json', 'w') as f:
        json.dump(mc_results, f, indent=2, default=str)
    with open('results/global_summary.json', 'w') as f:
        json.dump(global_summary, f, indent=2, default=str)

    logger.info("✅ Pipeline completado. Resultados en results/")
    return {
        'ranking': ranking,
        'backtest': backtest_results,
        'daps': daps_result,
        'optimized': optimized,
        'global_summary': global_summary,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true', help='Ejecutar pipeline completo con DAPS 4')
    parser.add_argument('--scan', action='store_true', help='Generar ranking solo')
    parser.add_argument('--backtest', type=str, help='Backtest de un símbolo')
    parser.add_argument('--optimize', action='store_true', help='Ejecutar Optuna global')
    parser.add_argument('--daps', action='store_true', help='Ejecutar DAPS 4')
    args = parser.parse_args()

    if args.full:
        full_pipeline()
    elif args.scan:
        data_engine = BybitDataEngine()
        symbols = data_engine.get_symbols()
        ranking = compute_ranking(symbols, data_engine)
        print(json.dumps(ranking, indent=2, default=str))
    elif args.backtest:
        data_engine = BybitDataEngine()
        bt = run_backtest_advanced(args.backtest, data_engine, days=365*2)
        print(json.dumps(bt, indent=2, default=str))
    elif args.optimize:
        best = run_optuna_global()
        print(f"Mejores parámetros: {best}")
    elif args.daps:
        data_engine = BybitDataEngine()
        symbols = data_engine.get_symbols()
        result = run_daps_full(data_engine, symbols, iterations=4)
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usa --full para el pipeline completo con DAPS 4.")

if __name__ == '__main__':
    main()
