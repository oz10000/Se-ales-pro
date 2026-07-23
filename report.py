# report.py
# Generación de reportes con todas las métricas de validación

import pandas as pd
import numpy as np
import os
import json
from config import RESULTS_DIR
import logging

logger = logging.getLogger(__name__)

def generate_final_report(ranking, backtest_results, wf_results, mc_results, bayesian_results):
    df_rank = pd.DataFrame(ranking.get('top_long', []))
    df_rank.to_csv(os.path.join(RESULTS_DIR, 'top3_long.csv'), index=False)
    df_rank = pd.DataFrame(ranking.get('top_short', []))
    df_rank.to_csv(os.path.join(RESULTS_DIR, 'top3_short.csv'), index=False)

    bt_data = []
    for sym, bt in backtest_results.items():
        bt_data.append({
            'symbol': sym,
            'trades': bt.get('total_trades', 0),
            'win_rate': bt.get('win_rate', 0),
            'profit_factor': bt.get('profit_factor', 0),
            'sharpe': bt.get('sharpe', 0),
            'max_drawdown': bt.get('max_drawdown', 0),
            'total_pnl': bt.get('total_pnl', 0),
        })
    df_bt = pd.DataFrame(bt_data)
    df_bt.to_csv(os.path.join(RESULTS_DIR, 'backtest_by_asset.csv'), index=False)

    wf_data = []
    for wf in wf_results:
        wf_data.append({
            'window': wf.get('window', 0),
            'win_rate': wf.get('win_rate', 0),
            'profit_factor': wf.get('profit_factor', 0),
            'max_drawdown': wf.get('max_drawdown', 0),
        })
    df_wf = pd.DataFrame(wf_data)
    df_wf.to_csv(os.path.join(RESULTS_DIR, 'walkforward.csv'), index=False)

    with open(os.path.join(RESULTS_DIR, 'montecarlo.json'), 'w') as f:
        json.dump(mc_results, f, indent=2)

    with open(os.path.join(RESULTS_DIR, 'bayesian.json'), 'w') as f:
        json.dump(bayesian_results, f, indent=2)

    logger.info("Reportes generados en results/")
