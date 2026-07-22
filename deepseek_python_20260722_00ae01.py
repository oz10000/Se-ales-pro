# report.py
# Generación de reportes FINAL_REPORT.csv y estadísticas

import pandas as pd
import json
import os
from config import RESULTS_DIR
import logging

logger = logging.getLogger(__name__)

def generate_final_report(optimized_assets, data_engine, base_params=None):
    rows = []
    for asset in optimized_assets:
        if asset is None:
            continue
        params = asset.get('best_params', {})
        rows.append({
            'Activo': asset['symbol'],
            'Dirección': asset['direction'],
            'Win Rate': f"{asset.get('win_rate', 0):.1%}",
            'Profit Factor': f"{asset.get('profit_factor', 0):.2f}",
            'Sharpe': f"{asset.get('sharpe', 0):.2f}",
            'Drawdown': f"{asset.get('max_drawdown', 0):.1f}%",
            'Trades': asset.get('total_trades', 0),
            'TP óptimo': params.get('tp_mult', 'N/A'),
            'SL óptimo': params.get('sl_mult', 'N/A'),
            'Trailing Act': params.get('trail_activation', 'N/A'),
            'Trailing Dist': params.get('trail_distance', 'N/A'),
            'Leverage': params.get('leverage', 1),
            'Ganancia 2 años': f"{asset.get('total_pnl', 0):.2f} USDT",
            'Riesgo': f"{asset.get('max_drawdown', 0):.1f}%",
        })
    df = pd.DataFrame(rows)
    path = os.path.join(RESULTS_DIR, 'FINAL_REPORT.csv')
    df.to_csv(path, index=False)
    logger.info(f"Reporte final guardado en {path}")
    return df

def generate_top_ranking(ranking):
    long_df = pd.DataFrame(ranking.get('long', []))
    short_df = pd.DataFrame(ranking.get('short', []))
    if not long_df.empty:
        long_df['Win Rate'] = long_df['win_rate'].apply(lambda x: f"{x:.1%}")
        long_df['PF'] = long_df['profit_factor'].apply(lambda x: f"{x:.2f}")
        long_df['Horas hasta entrada'] = long_df['hours_to_entry'].apply(lambda x: f"{x:.1f}h")
        long_df.to_csv(os.path.join(RESULTS_DIR, 'top10_long.csv'), index=False)
    if not short_df.empty:
        short_df['Win Rate'] = short_df['win_rate'].apply(lambda x: f"{x:.1%}")
        short_df['PF'] = short_df['profit_factor'].apply(lambda x: f"{x:.2f}")
        short_df['Horas hasta entrada'] = short_df['hours_to_entry'].apply(lambda x: f"{x:.1f}h")
        short_df.to_csv(os.path.join(RESULTS_DIR, 'top10_short.csv'), index=False)
    return long_df, short_df

def generate_optimized_parameters(optimized_assets):
    params_dict = {}
    for asset in optimized_assets:
        if asset:
            params_dict[asset['symbol']] = asset.get('best_params', {})
    path = os.path.join(RESULTS_DIR, 'optimized_parameters.json')
    with open(path, 'w') as f:
        json.dump(params_dict, f, indent=2)
    logger.info(f"Parámetros optimizados guardados en {path}")
    return params_dict

def generate_daps_history(daps_result):
    path = os.path.join(RESULTS_DIR, 'daps_history.json')
    with open(path, 'w') as f:
        json.dump(daps_result.get('history', []), f, indent=2, default=str)
    logger.info(f"Historial DAPS guardado en {path}")

def generate_global_summary(backtest_results, ranking):
    all_trades = []
    for sym, bt in backtest_results.items():
        if bt and 'trades' in bt:
            all_trades.extend(bt['trades'])

    if not all_trades:
        return {}

    df_t = pd.DataFrame(all_trades)
    wins = df_t[df_t['pnl_pct'] > 0]
    losses = df_t[df_t['pnl_pct'] <= 0]
    total = len(df_t)
    wr = len(wins) / total if total > 0 else 0
    pf = abs(wins['pnl_pct'].sum()) / abs(losses['pnl_pct'].sum()) if len(losses) > 0 and losses['pnl_pct'].sum() != 0 else 0

    eq = np.cumsum([t['pnl_pct'] for t in all_trades]) * INITIAL_CAPITAL
    max_dd = 0
    peak = 0
    for val in eq:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    summary = {
        'Capital inicial': INITIAL_CAPITAL,
        'Capital final': INITIAL_CAPITAL + sum([t['pnl_pct'] for t in all_trades]) * INITIAL_CAPITAL,
        'Rentabilidad': sum([t['pnl_pct'] for t in all_trades]) * 100,
        'Total trades': total,
        'Trades por día': total / (365 * 2) if total > 0 else 0,
        'Trades por hora': total / (365 * 2 * 24) if total > 0 else 0,
        'Win Rate': wr * 100,
        'Profit Factor': pf,
        'Sharpe': bt.get('sharpe', 0) if bt else 0,
        'Sortino': bt.get('sortino', 0) if bt else 0,
        'Máximo Drawdown': max_dd * 100,
        'Expectancy': sum([t['pnl_pct'] for t in all_trades]) / total if total > 0 else 0,
        'Mejor trade': max([t['pnl_pct'] for t in all_trades]) if all_trades else 0,
        'Peor trade': min([t['pnl_pct'] for t in all_trades]) if all_trades else 0,
        'Duración media': df_t['duration_hours'].mean() if not df_t.empty else 0,
        'Riesgo de ruina': 0.0,
    }
    return summary