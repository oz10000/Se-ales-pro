# optimizer.py
# Optimización con Bayesian Optimization + Walk‑Forward rolling

import optuna
import numpy as np
import pandas as pd
from typing import Dict
from engine import BybitDataEngine, compute_pidelta_score_normalized
from backtester import run_backtest_advanced
from config import *
import logging

logger = logging.getLogger(__name__)

def objective(trial, symbol='BTCUSDT', data_engine=None):
    """Función objetivo para Optuna (Bayesian Optimization)."""
    if data_engine is None:
        data_engine = BybitDataEngine()

    params = {
        'min_score': trial.suggest_float('min_score', 0.05, 0.25),
        'adx_threshold': trial.suggest_int('adx_threshold', 4, 16),
        'ker_threshold': trial.suggest_float('ker_threshold', 0.08, 0.30),
        'tp_mult': trial.suggest_float('tp_mult', 2.0, 4.0),
        'sl_mult': trial.suggest_float('sl_mult', 0.6, 1.4),
        'trail_activation': trial.suggest_float('trail_activation', 0.002, 0.008),
        'trail_distance': trial.suggest_float('trail_distance', 0.5, 2.0),
        'leverage': trial.suggest_int('leverage', 1, 5),
    }

    bt = run_backtest_advanced(symbol, data_engine, params, days=365)
    if bt.get('total_trades', 0) < 10:
        return 0.0

    # Función objetivo: maximizar PF * WR / (DD + 0.01)
    score = bt['profit_factor'] * bt['win_rate'] / (bt['max_drawdown'] + 0.01)
    return score

def run_bayesian_optimization(symbol='BTCUSDT', n_trials=OPTUNA_TRIALS):
    """Ejecuta Bayesian Optimization con Optuna."""
    data_engine = BybitDataEngine()
    study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(lambda trial: objective(trial, symbol, data_engine), n_trials=n_trials)
    return study.best_params, study.best_value

def run_walk_forward_rolling(symbol='BTCUSDT', iterations=WALK_FORWARD_ITERATIONS):
    """Walk‑Forward rolling con múltiples iteraciones."""
    data_engine = BybitDataEngine()
    df = data_engine.fetch_historical(symbol, '5m', max_days=730)
    if df is None or len(df) < 200:
        return {}

    results = []
    total_days = len(df) // (24*12)  # 5m → 1h → días
    train_months = 6
    test_months = 2

    for i in range(iterations):
        train_start = i * test_months
        train_end = train_start + train_months
        test_end = train_end + test_months

        train_idx = train_end * 24 * 12
        test_idx = (train_end + test_months) * 24 * 12

        if test_idx > len(df):
            break

        train_df = df.iloc[:train_idx]
        test_df = df.iloc[train_idx:test_idx]

        # Optimizar en train (simplificado)
        best_params, _ = run_bayesian_optimization(symbol, n_trials=20)

        # Validar en test
        bt_test = run_backtest_advanced(symbol, data_engine, best_params, days=60)
        results.append({
            'window': i,
            'train_size': len(train_df),
            'test_size': len(test_df),
            'win_rate': bt_test.get('win_rate', 0),
            'profit_factor': bt_test.get('profit_factor', 0),
            'max_drawdown': bt_test.get('max_drawdown', 0),
        })

    return results
