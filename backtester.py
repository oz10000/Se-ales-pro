# backtester.py
# Backtesting profesional sin look‑ahead bias, con gestión de riesgo adaptativa

import pandas as pd
import numpy as np
from typing import Dict, List
from config import *
from engine import BybitDataEngine, compute_pidelta_score_normalized, classify_regime, atr, adx, ker
import logging

logger = logging.getLogger(__name__)

def run_backtest_advanced(symbol, data_engine, params=None, days=BACKTEST_YEARS*365, classify_losses=True):
    """
    Backtesting con ejecución realista, sin look‑ahead bias.
    """
    df = data_engine.fetch_historical(symbol, '5m', max_days=days)
    if df is None or len(df) < 100:
        return {}

    p = params or {}
    tp_mult = p.get('tp_mult', TAKE_PROFIT_MULT)
    sl_mult = p.get('sl_mult', STOP_LOSS_MULT)
    lev = p.get('leverage', MAX_LEVERAGE)
    min_score = p.get('min_score', MIN_SCORE)
    adx_th = p.get('adx_threshold', ADX_THRESHOLD)
    ker_th = p.get('ker_threshold', KER_THRESHOLD)

    trades = []
    equity = [INITIAL_CAPITAL]
    capital = equity[0]

    for i in range(60, len(df)):
        slice_df = df.iloc[:i]
        if len(slice_df) < 60:
            continue

        score = compute_pidelta_score_normalized(slice_df)
        if abs(score) < min_score:
            continue

        adx_val = adx(slice_df, 14).iloc[-1]
        ker_val = ker(slice_df['close'], 10).iloc[-1]
        if adx_val < adx_th or ker_val < ker_th:
            continue

        regime, _ = classify_regime(slice_df)
        if regime not in REGIME_ALLOWED:
            continue

        direction = 'LONG' if score > 0 else 'SHORT'
        current = slice_df['close'].iloc[-1]
        atr_val = atr(slice_df, 12).iloc[-1]

        tp = current + atr_val * tp_mult if direction == 'LONG' else current - atr_val * tp_mult
        sl = current - atr_val * sl_mult if direction == 'LONG' else current + atr_val * sl_mult

        entry = current * (1 + np.random.uniform(-SLIPPAGE, SLIPPAGE))
        exit_price = None
        exit_reason = None
        duration = 0
        max_price = entry
        min_price = entry
        exit_time = df.index[-1]

        for j in range(i, len(df)):
            price = df['close'].iloc[j]
            high = df['high'].iloc[j]
            low = df['low'].iloc[j]
            if direction == 'LONG':
                max_price = max(max_price, high)
                min_price = min(min_price, low)
                if high >= tp:
                    exit_price = tp
                    exit_reason = 'TP'
                    exit_time = df.index[j]
                    break
                elif low <= sl:
                    exit_price = sl
                    exit_reason = 'SL'
                    exit_time = df.index[j]
                    break
            else:
                max_price = max(max_price, high)
                min_price = min(min_price, low)
                if low <= tp:
                    exit_price = tp
                    exit_reason = 'TP'
                    exit_time = df.index[j]
                    break
                elif high >= sl:
                    exit_price = sl
                    exit_reason = 'SL'
                    exit_time = df.index[j]
                    break
            duration = (df.index[j] - df.index[i]).total_seconds() / 3600
            if duration > 48:
                exit_price = price
                exit_reason = 'Timeout'
                exit_time = df.index[j]
                break

        if exit_price is None:
            exit_price = df['close'].iloc[-1]
            exit_reason = 'EndOfData'
            exit_time = df.index[-1]

        if direction == 'LONG':
            pnl = (exit_price - entry) / entry * lev
            mfe = (max_price - entry) / entry * lev
            mae = (min_price - entry) / entry * lev
        else:
            pnl = (entry - exit_price) / entry * lev
            mfe = (entry - min_price) / entry * lev
            mae = (entry - max_price) / entry * lev

        pnl -= COMMISSION
        capital *= (1 + pnl)
        equity.append(capital)

        trades.append({
            'symbol': symbol,
            'direction': direction,
            'entry_time': df.index[i],
            'exit_time': exit_time,
            'entry': entry,
            'exit': exit_price,
            'tp': tp,
            'sl': sl,
            'leverage': lev,
            'pnl_pct': pnl,
            'duration_hours': duration,
            'mfe': mfe,
            'mae': mae,
            'exit_reason': exit_reason,
            'score': score,
            'regime': regime,
        })

    if not trades:
        return {}

    df_t = pd.DataFrame(trades)
    wins = df_t[df_t['pnl_pct'] > 0]
    losses = df_t[df_t['pnl_pct'] <= 0]
    total = len(df_t)
    wr = len(wins) / total if total > 0 else 0
    pf = abs(wins['pnl_pct'].sum()) / abs(losses['pnl_pct'].sum()) if len(losses) > 0 and losses['pnl_pct'].sum() != 0 else 0

    eq = np.array(equity)
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak * 100
    max_dd = dd.max()
    returns = np.diff(eq) / eq[:-1]
    sharpe = returns.mean() / (returns.std() + 1e-9) * np.sqrt(252) if len(returns) > 1 else 0
    downside = returns[returns < 0]
    sortino = returns.mean() / (downside.std() + 1e-9) * np.sqrt(252) if len(downside) > 0 else 0

    avg_duration = df_t['duration_hours'].mean()
    avg_win = wins['pnl_pct'].mean() if not wins.empty else 0
    avg_loss = losses['pnl_pct'].mean() if not losses.empty else 0
    best = df_t['pnl_pct'].max()
    worst = df_t['pnl_pct'].min()

    max_win_streak = 0
    max_loss_streak = 0
    cur_w = 0
    cur_l = 0
    for _, row in df_t.iterrows():
        if row['pnl_pct'] > 0:
            cur_w += 1
            cur_l = 0
            max_win_streak = max(max_win_streak, cur_w)
        else:
            cur_l += 1
            cur_w = 0
            max_loss_streak = max(max_loss_streak, cur_l)

    total_pnl = equity[-1] - equity[0]
    expectancy = total_pnl / total if total > 0 else 0

    return {
        'total_trades': total,
        'win_count': len(wins),
        'loss_count': len(losses),
        'win_rate': wr,
        'profit_factor': pf,
        'total_pnl': total_pnl,
        'max_drawdown': max_dd,
        'sharpe': sharpe,
        'sortino': sortino,
        'avg_duration_hours': avg_duration,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'best_trade': best,
        'worst_trade': worst,
        'max_win_streak': max_win_streak,
        'max_loss_streak': max_loss_streak,
        'expectancy': expectancy,
        'final_capital': equity[-1],
        'trades': trades,
        'equity_curve': equity,
    }
