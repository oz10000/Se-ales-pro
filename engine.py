# engine.py
# Motor de datos, indicadores y señales con predicción de tiempo

import ccxt
import pandas as pd
import numpy as np
import os
import pickle
import hashlib
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from config import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# INDICADORES TÉCNICOS (sin cambios)
# =============================================================================

def atr(df, period=ATR_PERIOD):
    tr = np.maximum(df['high'] - df['low'],
                    np.maximum(abs(df['high'] - df['close'].shift()),
                               abs(df['low'] - df['close'].shift())))
    return tr.rolling(period).mean()

def adx(df, period=ADX_PERIOD):
    if len(df) < period + 1:
        return pd.Series(0.0, index=df.index)
    up = df['high'].diff()
    down = -df['low'].diff()
    plus = pd.Series(0.0, index=df.index)
    minus = pd.Series(0.0, index=df.index)
    plus[(up > down) & (up > 0)] = up
    minus[(down > up) & (down > 0)] = down
    atr_val = atr(df, period)
    plus_di = 100 * plus.rolling(period).mean() / atr_val
    minus_di = 100 * minus.rolling(period).mean() / atr_val
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    return dx.rolling(period).mean()

def ker(close, period=KER_PERIOD):
    if len(close) < period + 1:
        return pd.Series(0.0, index=close.index)
    abs_diff = abs(close.diff(period))
    sum_abs = close.diff().abs().rolling(period).sum()
    return (abs_diff / (sum_abs + 1e-9)).fillna(0)

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def vwap(df):
    return (df['close'] * df['volume']).cumsum() / (df['volume'].cumsum() + 1e-9)

def compute_pidelta_score(df, weights=None):
    if len(df) < 50:
        return 0.0
    w = weights or {'trend':0.25, 'strength':0.20, 'ker':0.15, 'atr_rel':0.20, 'momentum_short':0.20}
    close = df['close']
    a = atr(df, 12)
    ema22 = ema(close, 22)
    trend = np.tanh((close.iloc[-1] - ema22.iloc[-1]) / (a.iloc[-1] + 1e-9))
    adx_val = adx(df, 14).iloc[-1]
    strength = min(1.0, adx_val / 40.0)
    ker_val = ker(close, 10).iloc[-1]
    atr_rel = min(1.0, (a.iloc[-1] / close.iloc[-1] * 100) / 3.5)
    mom = close.pct_change(5).iloc[-1] * 100
    mom_norm = min(1.0, abs(mom) / 5.0)
    raw = (w['trend'] * trend + w['strength'] * strength + w['ker'] * ker_val +
           w['atr_rel'] * atr_rel + w['momentum_short'] * mom_norm)
    return float(np.tanh(raw))

def classify_regime(df):
    if len(df) < 60:
        return 'Indefinido', 0.5
    adx_val = adx(df, 14).iloc[-1]
    ker_val = ker(df['close'], 10).iloc[-1]
    atr_pct = atr(df, 12).iloc[-1] / df['close'].iloc[-1] * 100
    if adx_val > 28 and ker_val > 0.6:
        return 'Tendencia_Fuerte', 0.9
    if adx_val > 22 and ker_val > 0.5:
        return 'Tendencia_Débil', 0.75
    if ker_val < 0.4 or adx_val < 20:
        return 'Chop', 0.3
    if atr_pct > 2.0 and adx_val > 25:
        return 'Expansión', 0.85
    return 'Normal', 0.6

def detect_breakout(df, lookback=20):
    high = df['high'].rolling(lookback).max()
    low = df['low'].rolling(lookback).min()
    current = df['close'].iloc[-1]
    if current > high.iloc[-1]:
        return 'bullish'
    elif current < low.iloc[-1]:
        return 'bearish'
    return None

# =============================================================================
# PREDICCIÓN DE TIEMPO (NUEVO)
# =============================================================================

def estimate_time_to_signal(df, signal):
    """Estima el tiempo hasta que se active la señal y hasta que alcance TP."""
    if signal is None:
        return None

    entry = signal['entry']
    tp = signal['tp']
    current = df['close'].iloc[-1]

    # Velocidad del movimiento (últimos 5 períodos)
    speed = abs(df['close'].pct_change(5).sum() * 100) if len(df) >= 5 else 0.1
    if speed == 0:
        speed = 0.1

    # Distancia al TP
    distance_to_tp = abs(tp - current) / current * 100

    # Tiempo estimado hasta TP (en horas)
    hours_to_tp = distance_to_tp / (speed + 0.01) if speed > 0 else 24

    # Tiempo estimado hasta activación de señal (si no está activa)
    # Simplificado: basado en la distancia al precio de entrada
    distance_to_entry = abs(entry - current) / current * 100
    hours_to_entry = distance_to_entry / (speed + 0.01) if speed > 0 else 2

    return {
        'hours_to_tp': min(48, hours_to_tp),
        'hours_to_entry': min(12, hours_to_entry),
        'speed_pct': round(speed, 3),
        'distance_to_tp_pct': round(distance_to_tp, 2),
        'distance_to_entry_pct': round(distance_to_entry, 2),
    }

# =============================================================================
# GENERACIÓN DE SEÑALES (VERSIÓN MEJORADA)
# =============================================================================

def generate_signal(df, df_trend=None, df_macro=None, params=None, hour=None, day=None):
    """Genera señal LONG/SHORT con filtros mejorados y horario"""
    if df is None or len(df) < 60:
        return None

    p = params or {}
    min_score = p.get('min_score', MIN_SCORE)
    adx_th = p.get('adx_threshold', ADX_THRESHOLD)
    ker_th = p.get('ker_threshold', KER_THRESHOLD)

    # 1. Horario
    if hour is not None:
        if hour < OPTIMAL_HOURS_START or hour > OPTIMAL_HOURS_END:
            if day is not None and day not in PREFERRED_DAYS:
                return None
            min_score_boost = 0.05
            if min_score + min_score_boost > 0.5:
                return None

    # 2. Score PiDelta
    score = compute_pidelta_score(df)
    if abs(score) < min_score:
        return None

    # 3. ADX y KER
    adx_val = adx(df, ADX_PERIOD).iloc[-1]
    ker_val = ker(df['close'], KER_PERIOD).iloc[-1]
    if adx_val < adx_th or ker_val < ker_th:
        return None

    # 4. Régimen
    regime, _ = classify_regime(df)
    if regime not in REGIME_ALLOWED:
        return None

    # 5. Breakout
    breakout = detect_breakout(df)
    if breakout is None and abs(score) < 0.25:
        return None

    direction = 'LONG' if score > 0 else 'SHORT'
    current = df['close'].iloc[-1]

    # 6. EMAs
    ema50 = ema(df['close'], EMA_MID).iloc[-1] if len(df) >= EMA_MID else current
    ema200 = ema(df['close'], EMA_SLOW).iloc[-1] if len(df) >= EMA_SLOW else current

    if direction == 'LONG' and (current < ema50 * 0.98 or current < ema200 * 0.98):
        return None
    if direction == 'SHORT' and (current > ema50 * 1.02 or current > ema200 * 1.02):
        return None

    # 7. Tendencia superior (4H)
    if df_trend is not None and len(df_trend) >= 50:
        t_price = df_trend['close'].iloc[-1]
        t_ema50 = ema(df_trend['close'], EMA_MID).iloc[-1]
        t_ema200 = ema(df_trend['close'], EMA_SLOW).iloc[-1]
        if direction == 'LONG' and (t_price < t_ema50 * 0.98 or t_price < t_ema200 * 0.98):
            return None
        if direction == 'SHORT' and (t_price > t_ema50 * 1.02 or t_price > t_ema200 * 1.02):
            return None

    # 8. Macro (1D)
    if df_macro is not None and len(df_macro) >= 50:
        m_price = df_macro['close'].iloc[-1]
        m_ema50 = ema(df_macro['close'], EMA_MID).iloc[-1]
        m_ema200 = ema(df_macro['close'], EMA_SLOW).iloc[-1]
        if direction == 'LONG' and (m_price < m_ema50 * 0.98 or m_price < m_ema200 * 0.98):
            return None
        if direction == 'SHORT' and (m_price > m_ema50 * 1.02 or m_price > m_ema200 * 1.02):
            return None

    # 9. VWAP
    vwap_val = vwap(df).iloc[-1]
    if direction == 'LONG' and current < vwap_val * 0.98:
        return None
    if direction == 'SHORT' and current > vwap_val * 1.02:
        return None

    # 10. Volatilidad (ATR%)
    atr_val = atr(df, ATR_PERIOD).iloc[-1]
    atr_pct = atr_val / current * 100
    if atr_pct < 0.5 or atr_pct > 4.0:
        return None

    # 11. TP/SL dinámicos (optimizados por activo)
    tp_mult = p.get('tp_mult', TAKE_PROFIT_MULT)
    sl_mult = p.get('sl_mult', STOP_LOSS_MULT)

    # Ajuste por volatilidad
    if atr_pct > 2.5:
        tp_mult = tp_mult * 1.1
    elif atr_pct < 1.0:
        tp_mult = tp_mult * 0.85

    tp = current + atr_val * tp_mult if direction == 'LONG' else current - atr_val * tp_mult
    sl = current - atr_val * sl_mult if direction == 'LONG' else current + atr_val * sl_mult

    if atr_pct > 3.0:
        sl_mult = sl_mult * 1.2

    confidence = min(1.0, abs(score) / 0.25 + 0.1 * (breakout is not None))
    leverage = max(1, min(MAX_LEVERAGE, int(MAX_LEVERAGE * (1.2 / (atr_pct + 0.5)))))

    # Velocidad y tiempo estimado
    speed = abs(df['close'].pct_change(5).sum() * 100) if len(df) >= 5 else 0.1
    distance_pct = abs(tp - current) / current * 100
    est_hours = distance_pct / (speed + 0.01) if speed > 0 else 24

    # Volumen relativo
    vol_ratio = df['volume'].iloc[-1] / df['volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else 1.0

    # VWAP distance
    vwap_dist = (current - vwap_val) / vwap_val * 100

    # Break-even basado en volatilidad
    be_activation = 0.002 + 0.001 * (atr_pct / 1.5)
    be_activation = min(0.008, max(0.0015, be_activation))

    # Tiempo estimado hasta activación
    time_estimate = estimate_time_to_signal(df, {
        'entry': current,  # Ya estamos en la señal
        'tp': tp,
    })

    return {
        'direction': direction,
        'entry': current,
        'tp': tp,
        'sl': sl,
        'score': score,
        'regime': regime,
        'confidence': confidence,
        'leverage': leverage,
        'atr_pct': atr_pct,
        'atr': atr_val,
        'adx': adx_val,
        'ker': ker_val,
        'vwap_distance': vwap_dist,
        'vol_ratio': vol_ratio,
        'est_hours': min(48, est_hours),
        'breakout': breakout,
        'be_activation': be_activation,
        'time_estimate': time_estimate,
        'timestamp': df.index[-1],
    }

# =============================================================================
# DATA ENGINE (sin cambios)
# =============================================================================

class BybitDataEngine:
    def __init__(self):
        self.exchange = ccxt.bybit({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
        self.exchange.load_markets()
        self.cache_dir = CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_symbols(self, min_volume=MIN_VOLUME_24H):
        tickers = self.exchange.fetch_tickers()
        symbols = []
        for sym, ticker in tickers.items():
            if not sym.endswith('USDT'):
                continue
            if ticker.get('quoteVolume', 0) < min_volume:
                continue
            spread = (ticker.get('ask', 0) - ticker.get('bid', 0)) / (ticker.get('bid', 1) + 1e-9)
            if spread > MAX_SPREAD_PCT:
                continue
            symbols.append(sym)
        return symbols

    def fetch_ohlcv(self, symbol, timeframe='1h', limit=1000, since=None):
        cache_key = hashlib.md5(f"{symbol}_{timeframe}_{limit}_{since}".encode()).hexdigest()
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.pkl")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except:
                pass
        try:
            since_ts = int(since.timestamp() * 1000) if since else None
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit, since=since_ts)
            if not ohlcv:
                return None
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            with open(cache_path, 'wb') as f:
                pickle.dump(df, f)
            return df
        except Exception as e:
            logger.warning(f"Error fetching {symbol}: {e}")
            return None

    def fetch_historical(self, symbol, timeframe='1h', max_days=BACKTEST_YEARS*365):
        end = datetime.now()
        start = end - timedelta(days=max_days)
        since = start
        all_dfs = []
        while True:
            df = self.fetch_ohlcv(symbol, timeframe, limit=1000, since=since)
            if df is None or len(df) == 0:
                break
            all_dfs.append(df)
            last_time = df.index[-1]
            if last_time >= end:
                break
            since = last_time + timedelta(seconds=1)
            time.sleep(0.1)
        if not all_dfs:
            return None
        return pd.concat(all_dfs).drop_duplicates().sort_index()
