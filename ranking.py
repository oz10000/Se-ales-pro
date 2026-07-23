# ranking.py
# Ranking dinámico TOP 5 LONG / SHORT mostrando estado de cada activo

import pandas as pd
import numpy as np
from typing import Dict, List
from config import *
from engine import BybitDataEngine, generate_signal, atr, adx, ker, compute_pidelta_score, classify_regime
from backtester import run_backtest_advanced
import logging

logger = logging.getLogger(__name__)

def compute_ranking(symbols, data_engine, params=None, max_symbols=None):
    """
    Genera ranking TOP 5 LONG y SHORT, mostrando activos aunque no cumplan todos los filtros.
    Cada activo muestra su estado (cumple/no cumple) para cada criterio.
    """
    if max_symbols is None:
        max_symbols = len(symbols)

    results = []
    for sym in symbols[:max_symbols]:
        try:
            df_1h = data_engine.fetch_historical(sym, '1h', max_days=60)
            df_4h = data_engine.fetch_historical(sym, '4h', max_days=120)
            df_1d = data_engine.fetch_historical(sym, '1d', max_days=365)
            if df_1h is None or len(df_1h) < 60:
                continue

            # Datos de backtesting (si no hay, métricas por defecto)
            bt = run_backtest_advanced(sym, data_engine, params, days=180)
            if bt.get('total_trades', 0) < 5:
                win_rate = 0.55
                profit_factor = 1.2
                sharpe = 0.8
            else:
                win_rate = bt['win_rate']
                profit_factor = bt['profit_factor']
                sharpe = bt['sharpe']

            # Indicadores
            score = compute_pidelta_score(df_1h)
            adx_val = adx(df_1h, 14).iloc[-1] if len(df_1h) >= 14 else 0
            ker_val = ker(df_1h['close'], 10).iloc[-1] if len(df_1h) >= 10 else 0
            regime, _ = classify_regime(df_1h)

            # Umbrales (suaves para que siempre haya candidatos)
            min_score = params.get('min_score', 0.05)
            adx_th = params.get('adx_threshold', 5)
            ker_th = params.get('ker_threshold', 0.1)

            score_ok = abs(score) >= min_score
            adx_ok = adx_val >= adx_th
            ker_ok = ker_val >= ker_th
            regime_ok = regime in REGIME_ALLOWED

            # Tendencia (EMAs) para referencia
            current = df_1h['close'].iloc[-1]
            ema50 = ema(df_1h['close'], 50).iloc[-1] if len(df_1h) >= 50 else current
            ema200 = ema(df_1h['close'], 200).iloc[-1] if len(df_1h) >= 200 else current
            trend_ok = (current > ema50 * 0.98 and current > ema200 * 0.98) if score > 0 else (current < ema50 * 1.02 and current < ema200 * 1.02)

            # Puntuación compuesta para ranking
            rank_score = abs(score) * 0.4 + (adx_val / 40.0) * 0.3 + ker_val * 0.3

            direction = 'LONG' if score > 0 else 'SHORT'

            entry = {
                'symbol': sym,
                'direction': direction,
                'score': score,
                'adx': adx_val,
                'ker': ker_val,
                'regime': regime,
                'rank_score': rank_score,
                'score_ok': score_ok,
                'adx_ok': adx_ok,
                'ker_ok': ker_ok,
                'regime_ok': regime_ok,
                'trend_ok': trend_ok,
                'approved': score_ok and adx_ok and ker_ok and regime_ok,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'sharpe': sharpe,
                'current_price': current,
                'entry_price': current,
                'tp': current * 1.02 if direction == 'LONG' else current * 0.98,
                'sl': current * 0.98 if direction == 'LONG' else current * 1.02,
                'leverage': 2,
                'confidence': min(1.0, abs(score) / 0.2),
                'hours_to_entry': 1.0,
                'est_hours': 4.0,
            }
            results.append(entry)

        except Exception as e:
            logger.debug(f"Error en {sym}: {e}")
            continue

    # Separar y ordenar
    long_ops = [r for r in results if r['direction'] == 'LONG']
    short_ops = [r for r in results if r['direction'] == 'SHORT']

    long_ops.sort(key=lambda x: x['rank_score'], reverse=True)
    short_ops.sort(key=lambda x: x['rank_score'], reverse=True)

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
    """Optimización profunda individual (sin cambios)"""
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

    atr_vals = atr(df, 14)
    atr_pct = (atr_vals.mean() / df['close'].mean()) * 100
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
                            'min_score': base_params.get('min_score', 0.05),
                            'adx_threshold': base_params.get('adx_threshold', 5),
                            'ker_threshold': base_params.get('ker_threshold', 0.1),
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
