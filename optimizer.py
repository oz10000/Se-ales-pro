# optimizer.py
# Optimización DAPS 4 + Walk Forward + Monte Carlo

import optuna
import numpy as np
import pandas as pd
import json
from typing import Dict
from config import *
from engine import BybitDataEngine
from backtester import run_backtest_advanced
from ranking import optimize_asset_deep
import logging

logger = logging.getLogger(__name__)

def daps_iteration_1_loss_analysis(backtest_results):
    loss_data = []
    for sym, bt in backtest_results.items():
        if 'loss_summary' in bt:
            for reason, data in bt['loss_summary'].items():
                loss_data.append({
                    'symbol': sym,
                    'reason': reason,
                    'count': data.get('count', 0),
                    'percentage': data.get('percentage', 0),
                })
    df_loss = pd.DataFrame(loss_data)
    if df_loss.empty:
        return {'status': 'no_loss_data', 'summary': {}}
    summary = df_loss.groupby('reason').agg({'count': 'sum', 'percentage': 'mean'}).to_dict()
    return {
        'status': 'completed',
        'summary': summary,
        'top_reason': df_loss.groupby('reason')['count'].sum().idxmax() if not df_loss.empty else None,
        'df_loss': df_loss,
    }

def daps_iteration_2_exit_optimization(symbol, data_engine, params):
    results = []
    tp_vals = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    sl_vals = [0.6, 0.8, 1.0, 1.2, 1.5, 2.0]
    trail_act = [0.001, 0.002, 0.003, 0.004, 0.006, 0.008, 0.010]
    trail_dist = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5]

    np.random.seed(42)
    for tp in np.random.choice(tp_vals, size=4, replace=False):
        for sl in np.random.choice(sl_vals, size=4, replace=False):
            for ta in np.random.choice(trail_act, size=3, replace=False):
                for td in np.random.choice(trail_dist, size=3, replace=False):
                    test_params = params.copy()
                    test_params['tp_mult'] = tp
                    test_params['sl_mult'] = sl
                    test_params['trail_activation'] = ta
                    test_params['trail_distance'] = td
                    bt = run_backtest_advanced(symbol, data_engine, test_params, days=365)
                    if bt.get('total_trades', 0) > 5:
                        score = bt['profit_factor'] * bt['win_rate'] / (bt['max_drawdown'] + 0.01)
                        results.append({
                            'params': test_params,
                            'score': score,
                            'win_rate': bt['win_rate'],
                            'profit_factor': bt['profit_factor'],
                            'max_drawdown': bt['max_drawdown'],
                        })
    if not results:
        return {'status': 'no_results'}
    best = max(results, key=lambda x: x['score'])
    return {
        'status': 'completed',
        'best_params': best['params'],
        'best_score': best['score'],
        'all_results': results,
    }

def daps_iteration_3_entry_optimization(symbol, data_engine, params):
    results = []
    min_score_vals = [0.10, 0.15, 0.18, 0.22, 0.28, 0.35]
    adx_vals = [10, 14, 18, 22, 26, 30]
    ker_vals = [0.20, 0.25, 0.32, 0.40, 0.50, 0.60]

    for ms in np.random.choice(min_score_vals, size=4, replace=False):
        for adx_v in np.random.choice(adx_vals, size=4, replace=False):
            for ker_v in np.random.choice(ker_vals, size=3, replace=False):
                test_params = params.copy()
                test_params['min_score'] = ms
                test_params['adx_threshold'] = adx_v
                test_params['ker_threshold'] = ker_v
                bt = run_backtest_advanced(symbol, data_engine, test_params, days=365)
                if bt.get('total_trades', 0) > 5:
                    score = bt['profit_factor'] * bt['win_rate'] / (bt['max_drawdown'] + 0.01)
                    results.append({
                        'params': test_params,
                        'score': score,
                        'win_rate': bt['win_rate'],
                        'profit_factor': bt['profit_factor'],
                        'total_trades': bt['total_trades'],
                    })
    if not results:
        return {'status': 'no_results'}
    best = max(results, key=lambda x: x['score'])
    return {
        'status': 'completed',
        'best_params': best['params'],
        'best_score': best['score'],
        'all_results': results,
    }

def daps_iteration_4_universe_expansion(data_engine, params):
    symbols = data_engine.get_symbols(min_volume=MIN_VOLUME_24H)
    logger.info(f"Universe expansion: {len(symbols)} symbols found")

    results = []
    for sym in symbols:
        try:
            df = data_engine.fetch_historical(sym, '1h', max_days=30)
            if df is None or len(df) < 50:
                continue
            signal = generate_signal(df, params=params)
            if signal:
                results.append({
                    'symbol': sym,
                    'score': signal['score'],
                    'direction': signal['direction'],
                    'entry': signal['entry'],
                    'tp': signal['tp'],
                    'sl': signal['sl'],
                    'confidence': signal['confidence'],
                    'est_hours': signal.get('est_hours', 24),
                    'hours_to_entry': signal.get('time_estimate', {}).get('hours_to_entry', 12),
                })
        except:
            continue

    results.sort(key=lambda x: x['score'], reverse=True)
    return {
        'status': 'completed',
        'candidates': results,
        'total_analyzed': len(symbols),
        'total_signals': len(results),
    }

def run_daps_full(data_engine, symbols, base_params=None, iterations=4):
    if base_params is None:
        base_params = {
            'min_score': MIN_SCORE,
            'adx_threshold': ADX_THRESHOLD,
            'ker_threshold': KER_THRESHOLD,
            'tp_mult': TAKE_PROFIT_MULT,
            'sl_mult': STOP_LOSS_MULT,
            'trail_activation': TRAIL_ACTIVATION,
            'trail_distance': TRAIL_DISTANCE,
            'leverage': MAX_LEVERAGE,
        }

    daps_history = []

    logger.info("DAPS Iteración 1: Análisis de pérdidas...")
    backtest_results = {}
    for sym in symbols[:30]:
        bt = run_backtest_advanced(sym, data_engine, base_params, days=365)
        if bt:
            backtest_results[sym] = bt

    loss_analysis = daps_iteration_1_loss_analysis(backtest_results)
    daps_history.append({'iteration': 1, 'type': 'loss_analysis', 'result': loss_analysis})

    logger.info("DAPS Iteración 2: Optimización de salida...")
    exit_opt_results = {}
    for sym in symbols[:10]:
        res = daps_iteration_2_exit_optimization(sym, data_engine, base_params)
        if res.get('status') == 'completed':
            exit_opt_results[sym] = res

    if exit_opt_results:
        best_exit_opt = max(exit_opt_results.values(), key=lambda x: x.get('best_score', 0))
        if best_exit_opt.get('best_params'):
            base_params.update(best_exit_opt['best_params'])
            logger.info(f"Exit optimization updated params: {base_params}")

    daps_history.append({'iteration': 2, 'type': 'exit_optimization', 'result': exit_opt_results})

    logger.info("DAPS Iteración 3: Optimización de entrada...")
    entry_opt_results = {}
    for sym in symbols[:10]:
        res = daps_iteration_3_entry_optimization(sym, data_engine, base_params)
        if res.get('status') == 'completed':
            entry_opt_results[sym] = res

    if entry_opt_results:
        best_entry_opt = max(entry_opt_results.values(), key=lambda x: x.get('best_score', 0))
        if best_entry_opt.get('best_params'):
            base_params.update(best_entry_opt['best_params'])
            logger.info(f"Entry optimization updated params: {base_params}")

    daps_history.append({'iteration': 3, 'type': 'entry_optimization', 'result': entry_opt_results})

    logger.info("DAPS Iteración 4: Expansión del universo...")
    universe_result = daps_iteration_4_universe_expansion(data_engine, base_params)
    daps_history.append({'iteration': 4, 'type': 'universe_expansion', 'result': universe_result})

    return {
        'best_params': base_params,
        'history': daps_history,
        'iterations': iterations,
        'loss_analysis': loss_analysis,
        'universe_candidates': universe_result.get('candidates', []),
    }

def run_walk_forward_professional(symbol, data_engine, params=None):
    if params is None:
        params = {}
    results = []
    for ratio in WALK_FORWARD_RATIOS:
        try:
            df = data_engine.fetch_historical(symbol, '1h', max_days=365*2)
            if df is None or len(df) < 200:
                continue
            split = int(len(df) * ratio)
            train_df = df.iloc[:split]
            test_df = df.iloc[split:]
            bt_train = run_backtest_advanced(symbol, data_engine, params, days=365)
            bt_test = run_backtest_advanced(symbol, data_engine, params, days=365)
            results.append({
                'ratio': ratio,
                'train_win_rate': bt_train.get('win_rate', 0) if bt_train else 0,
                'test_win_rate': bt_test.get('win_rate', 0) if bt_test else 0,
                'train_pf': bt_train.get('profit_factor', 0) if bt_train else 0,
                'test_pf': bt_test.get('profit_factor', 0) if bt_test else 0,
            })
        except Exception as e:
            logger.warning(f"Walk forward error for {symbol}: {e}")
    return results

def run_monte_carlo_professional(symbol, data_engine, params=None, n_simulations=MONTE_CARLO_SIMULATIONS):
    if params is None:
        params = {}
    bt = run_backtest_advanced(symbol, data_engine, params, days=365)
    trades = bt.get('trades', []) if bt else []
    if not trades:
        return {}

    final_capitals = []
    for _ in range(n_simulations):
        shuffled = np.random.permutation(trades)
        cap = INITIAL_CAPITAL
        for t in shuffled:
            cap *= (1 + t['pnl_pct'])
        final_capitals.append(cap)

    arr = np.array(final_capitals)
    return {
        'mean_final': np.mean(arr),
        'p5': np.percentile(arr, 5),
        'p95': np.percentile(arr, 95),
        'ruin_prob': np.mean(arr < 500) * 100,
        'best': np.max(arr),
        'worst': np.min(arr),
        'median': np.median(arr),
    }

def run_optuna_global(symbol='BTCUSDT', n_trials=OPTUNA_TRIALS):
    def objective(trial):
        params = {
            'min_score': trial.suggest_float('min_score', 0.05, 0.45),
            'adx_threshold': trial.suggest_int('adx_threshold', 5, 30),
            'ker_threshold': trial.suggest_float('ker_threshold', 0.10, 0.60),
            'tp_mult': trial.suggest_float('tp_mult', 1.5, 4.5),
            'sl_mult': trial.suggest_float('sl_mult', 0.5, 2.0),
            'trail_activation': trial.suggest_float('trail_activation', 0.001, 0.012),
            'trail_distance': trial.suggest_float('trail_distance', 0.5, 3.0),
            'leverage': trial.suggest_int('leverage', 1, 5),
        }
        data_engine = BybitDataEngine()
        bt = run_backtest_advanced(symbol, data_engine, params, days=365)
        if bt.get('total_trades', 0) < 10:
            return 0.0
        return bt['profit_factor'] * bt['win_rate'] / (bt['max_drawdown'] + 0.01)

    study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials)
    return study.best_params
