# ranking.py
# Ranking dinámico TOP 10 LONG / SHORT con predicción de tiempo

import pandas as pd
import numpy as np
from typing import Dict, List
from config import *
from engine import BybitDataEngine, generate_signal, estimate_time_to_signal
from backtester import run_backtest_advanced
import logging

logger = logging.getLogger(__name__)

def compute_ranking(symbols, data_engine, params=None, max_symbols=None):
    """Genera ranking TOP 10 LONG y SHORT con scoring mejorado"""
    if max_symbols is None:
        max_symbols = len(symbols)  # ANALIZAR TODOS

    results = []
    for sym in symbols[:max_symbols]:
        try:
            df_1h = data_engine.fetch_historical(sym, '1h', max_days=60)
            df_4h = data_engine.fetch_historical(sym, '4h', max_days=120)
            df_1d = data_engine.fetch_historical(sym, '1d', max_days=365)
            if df_1h is None or len(df_1h) < 60:
                continue

            bt = run_backtest_advanced(sym, data_engine, params, days=180)
            if bt.get('total_trades', 0) < 5:  # REDUCIDO: acepta menos trades
                continue

            current_hour = pd.Timestamp.now().hour
            current_day = pd.Timestamp.now().weekday()
            signal = generate_signal(df_1h, df_trend=df_4h, df_macro=df_1d, params=params,
                                     hour=current_hour, day=current_day)
            if signal is None:
                continue

            # Predicción de tiempo
            time_est = signal.get('time_estimate', {})

            # Score compuesto mejorado
            score = (bt['win_rate'] * 0.20 +
                     bt['profit_factor'] / 3.0 * 0.18 +
                     bt['sharpe'] / 2.0 * 0.12 +
                     signal['confidence'] * 0.15 +
                     (1 / (signal.get('est_hours', 24) + 1)) * 0.10 +
                     min(1.0, signal.get('vol_ratio', 1.0) / 2.0) * 0.10 +
                     0.05 * (signal.get('breakout') is not None) +
                     0.10 * (1 / (time_est.get('hours_to_entry', 12) + 1)))

            results.append({
                'symbol': sym,
                'direction': signal['direction'],
                'entry': signal['entry'],
                'tp': signal['tp'],
                'sl': signal['sl'],
                'leverage': signal['leverage'],
                'confidence': signal['confidence'],
                'win_rate': bt['win_rate'],
                'profit_factor': bt['profit_factor'],
                'sharpe': bt['sharpe'],
                'sortino': bt.get('sortino', 0),
                'max_drawdown': bt['max_drawdown'],
                'avg_duration': bt['avg_duration_hours'],
                'total_trades': bt['total_trades'],
                'score': score,
                'est_hours': signal.get('est_hours', 24),
                'regime': signal['regime'],
                'adx': signal['adx'],
                'ker': signal['ker'],
                'atr_pct': signal['atr_pct'],
                'vwap_distance': signal.get('vwap_distance', 0),
                'vol_ratio': signal.get('vol_ratio', 1.0),
                'breakout': signal.get('breakout'),
                'be_activation': signal.get('be_activation', 0.003),
                'hours_to_entry': time_est.get('hours_to_entry', 12),
                'hours_to_tp': time_est.get('hours_to_tp', 24),
                'loss_summary': bt.get('loss_summary', {}),
            })
        except Exception as e:
            logger.debug(f"Error en {sym}: {e}")

    long_ops = [r for r in results if r['direction'] == 'LONG']
    short_ops = [r for r in results if r['direction'] == 'SHORT']
    long_ops.sort(key=lambda x: x['score'], reverse=True)
    short_ops.sort(key=lambda x: x['score'], reverse=True)

    return {
        'long': long_ops[:TOP_N],
        'short': short_ops[:TOP_N],
        'long_deep': long_ops[:TOP_DEEP],
        'short_deep': short_ops[:TOP_DEEP],
        'all': results,
        'timestamp': pd.Timestamp.now().isoformat(),
        'total_analyzed': len(results),
    }

def optimize_asset_deep(symbol, direction, data_engine, base_params=None):
    if base_params is None:
        base_params = {}

    tp_vals = [1.8, 2.0, 2.5, 3.0, 3.5]
    sl_vals = [0.6, 0.8, 1.0, 1.2, 1.5]
    trail_act = [0.002, 0.003, 0.004, 0.006, 0.008]
    trail_dist = [0.8, 1.0, 1.2, 1.5, 2.0]
    lev_vals = [1, 2, 3, 4, 5]

    df = data_engine.fetch_historical(symbol, '1h', max_days=90)
    if df is None or len(df) < 50:
        return None

    atr_pct = (atr(df, 14).mean() / df['close'].mean()) * 100
    volatility_profile = 'high' if atr_pct > 2.5 else 'medium' if atr_pct > 1.2 else 'low'

    best_score = -np.inf
    best_params = {}
    best_bt = None

    if volatility_profile == 'high':
        tp_vals = [2.5, 3.0, 3.5, 4.0]
        sl_vals = [0.8, 1.0, 1.2, 1.5]
        trail_act = [0.004, 0.006, 0.008]
    elif volatility_profile == 'low':
        tp_vals = [1.5, 1.8, 2.0, 2.2]
        sl_vals = [0.6, 0.8, 1.0]
        trail_act = [0.002, 0.003, 0.004]

    for tp in tp_vals:
        for sl in sl_vals:
            for ta in trail_act:
                for td in trail_dist:
                    for lev in lev_vals:
                        params = {
                            'tp_mult': tp,
                            'sl_mult': sl,
                            'trail_activation': ta,
                            'trail_distance': td,
                            'leverage': lev,
                            'min_score': base_params.get('min_score', MIN_SCORE),
                            'adx_threshold': base_params.get('adx_threshold', ADX_THRESHOLD),
                            'ker_threshold': base_params.get('ker_threshold', KER_THRESHOLD),
                        }
                        bt = run_backtest_advanced(symbol, data_engine, params, days=365)
                        if bt.get('total_trades', 0) < 5:
                            continue
                        score = bt['profit_factor'] * bt['win_rate'] / (bt['max_drawdown'] + 0.01)
                        if score > best_score:
                            best_score = score
                            best_params = params
                            best_bt = bt

    if best_bt is None:
        return None

    return {
        'symbol': symbol,
        'direction': direction,
        'best_params': best_params,
        'win_rate': best_bt['win_rate'],
        'profit_factor': best_bt['profit_factor'],
        'sharpe': best_bt['sharpe'],
        'max_drawdown': best_bt['max_drawdown'],
        'total_trades': best_bt['total_trades'],
        'final_capital': best_bt['final_capital'],
        'total_pnl': best_bt['total_pnl'],
        'loss_summary': best_bt.get('loss_summary', {}),
        'trades': best_bt['trades'],
    }
