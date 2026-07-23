# ranking.py
# Ranking multicriterio con coherencia ponderada y penalización temporal

import pandas as pd
import numpy as np
from typing import Dict, List
from config import *          # <--- INCLUYE TOP_N
from engine import BybitDataEngine, compute_pidelta_score_normalized, classify_regime, coherence_weighted
from backtester import run_backtest_advanced
from velocity_engine import calculate_velocity_score
import logging

logger = logging.getLogger(__name__)

def compute_ranking(symbols, data_engine, params=None, max_symbols=None):
    if max_symbols is None:
        max_symbols = len(symbols)

    results = []
    for sym in symbols[:max_symbols]:
        try:
            dfs = data_engine.fetch_multi_timeframe(sym)
            if not dfs or '5m' not in dfs:
                continue
            df_5m = dfs['5m']
            if len(df_5m) < 60:
                continue

            direction, coherence, dirs, oc_base = coherence_weighted(dfs)

            score = compute_pidelta_score_normalized(df_5m)
            if abs(score) < params.get('min_score', MIN_SCORE):
                continue

            vel = calculate_velocity_score(df_5m, {k: v for k, v in dfs.items() if k != '5m'})
            oc_score = vel['oc_score']

            bt = run_backtest_advanced(sym, data_engine, params, days=180)
            if bt.get('total_trades', 0) < 5:
                win_rate = 0.55
                profit_factor = 1.2
                sharpe = 0.8
            else:
                win_rate = bt['win_rate']
                profit_factor = bt['profit_factor']
                sharpe = bt['sharpe']

            current = df_5m['close'].iloc[-1]
            atr_val = atr(df_5m, 14).iloc[-1]
            tp = current + atr_val * TAKE_PROFIT_MULT if direction == 'LONG' else current - atr_val * TAKE_PROFIT_MULT
            sl = current - atr_val * STOP_LOSS_MULT if direction == 'LONG' else current + atr_val * STOP_LOSS_MULT

            if oc_score >= 0.80:
                quality = 'Excelente'
            elif oc_score >= 0.65:
                quality = 'Muy buena'
            elif oc_score >= 0.50:
                quality = 'Buena'
            else:
                quality = 'Regular'

            rank_score = (RANKING_WEIGHTS['oc_score'] * oc_score +
                          RANKING_WEIGHTS['coherence'] * coherence +
                          RANKING_WEIGHTS['velocity'] * vel['score'] +
                          RANKING_WEIGHTS['win_rate'] * win_rate +
                          RANKING_WEIGHTS['profit_factor'] * (profit_factor / 3.0) +
                          RANKING_WEIGHTS['temporal_bonus'] * (1 / (vel['time_minutes'] + 1)))

            entry = {
                'symbol': sym,
                'direction': direction,
                'score': score,
                'coherence': coherence,
                'coherence_dirs': dirs,
                'oc_score': oc_score,
                'velocity': vel['score'],
                'bucket': vel['bucket'],
                'time_minutes': vel['time_minutes'],
                'entry': current,
                'tp': tp,
                'sl': sl,
                'leverage': 3 if direction == 'LONG' else 2,
                'be': BREAK_EVEN_ACTIVATION,
                'trail_act': TRAIL_ACTIVATION,
                'trail_dist': TRAIL_DISTANCE,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'sharpe': sharpe,
                'quality': quality,
                'approved': coherence >= COHERENCE_THRESHOLD and abs(score) >= MIN_SCORE,
                'rank_score': rank_score,
            }
            results.append(entry)

        except Exception as e:
            logger.debug(f"Error en {sym}: {e}")

    long_ops = [r for r in results if r['direction'] == 'LONG']
    short_ops = [r for r in results if r['direction'] == 'SHORT']
    long_ops.sort(key=lambda x: x['rank_score'], reverse=True)
    short_ops.sort(key=lambda x: x['rank_score'], reverse=True)

    return {
        'long': long_ops,
        'short': short_ops,
        'top_long': long_ops[:TOP_N],
        'top_short': short_ops[:TOP_N],
        'all': results,
        'timestamp': pd.Timestamp.now().isoformat(),
        'total_analyzed': len(results),
    }
