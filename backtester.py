# backtester.py
# Módulo de backtesting simple
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from config import INITIAL_CAPITAL, COMMISSION
import logging

logger = logging.getLogger(__name__)

def run_backtest_advanced(symbol: str, data_engine, days: int = 730) -> Dict:
    """
    Ejecuta un backtest avanzado sobre un símbolo.
    """
    # Obtener datos históricos usando el nuevo método
    df = data_engine.fetch_historical(symbol, '5m', max_days=days)
    if df is None or len(df) < 100:
        logger.warning(f"No hay datos suficientes para backtestear {symbol}")
        return {
            'symbol': symbol,
            'total_return': 0.0,
            'sharpe': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'trades': 0
        }

    # Aquí iría tu lógica de backtest (ejemplo simple)
    # Simular estrategia de compra/venta basada en cruce de medias móviles
    df['ema_fast'] = df['close'].ewm(span=10, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=30, adjust=False).mean()
    df['signal'] = 0
    df.loc[df['ema_fast'] > df['ema_slow'], 'signal'] = 1
    df.loc[df['ema_fast'] <= df['ema_slow'], 'signal'] = -1
    df['position'] = df['signal'].shift()

    # Calcular retornos
    df['returns'] = df['close'].pct_change()
    df['strategy_returns'] = df['position'] * df['returns'] - COMMISSION * (df['position'].diff().abs() / 2)
    df['cumulative'] = (1 + df['strategy_returns']).cumprod()

    # Métricas
    total_return = df['cumulative'].iloc[-1] - 1
    sharpe = (df['strategy_returns'].mean() / df['strategy_returns'].std()) * np.sqrt(252*288) if df['strategy_returns'].std() != 0 else 0
    drawdown = (df['cumulative'].cummax() - df['cumulative']) / df['cumulative'].cummax()
    max_drawdown = drawdown.max()

    # Trades
    trades = (df['position'].diff().abs() // 2).sum()

    return {
        'symbol': symbol,
        'total_return': total_return,
        'sharpe': sharpe,
        'max_drawdown': max_drawdown,
        'win_rate': 0.5,  # placeholder
        'trades': int(trades)
    }
