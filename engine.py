# engine.py
# Motor principal con multi‑exchange, caché, coherencia ponderada y normalización robusta
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
# MAPEO DE TIMEFRAMES POR EXCHANGE
# =============================================================================
# KuCoin usa formato '5min', '15min', '1hour', etc.
# Binance y Bybit usan '5m', '15m', '1h', etc.
TIMEFRAME_MAP = {
    'binance': {
        '5m': '5m', '15m': '15m', '30m': '30m', '45m': '45m', '1h': '1h',
        '4h': '4h', '1d': '1d'
    },
    'kucoin': {
        '5m': '5min', '15m': '15min', '30m': '30min', '45m': '45min', '1h': '1hour',
        '4h': '4hour', '1d': '1day'
    },
    'bybit': {
        '5m': '5m', '15m': '15m', '30m': '30m', '45m': '45m', '1h': '1h',
        '4h': '4h', '1d': '1d'
    }
}

def map_timeframe(exchange_id: str, tf: str) -> str:
    """Convierte el timeframe al formato que espera el exchange."""
    return TIMEFRAME_MAP.get(exchange_id, {}).get(tf, tf)


# =============================================================================
# FUNCIONES AUXILIARES (reemplazo de scipy)
# =============================================================================
def median_abs_deviation(series, scale='normal'):
    """Calcula la Desviación Absoluta Mediana (MAD) usando NumPy."""
    median = np.median(series)
    mad = np.median(np.abs(series - median))
    if scale == 'normal':
        mad *= 1.4826
    return mad

def normalize_robust(series):
    """Normalización robusta usando mediana y MAD."""
    median = np.median(series)
    mad = median_abs_deviation(series, scale='normal')
    if mad == 0:
        return series
    return (series - median) / mad

# =============================================================================
# INDICADORES TÉCNICOS
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

def hurst_exponent(series, max_lag=20):
    lags = range(2, max_lag)
    tau = [np.sqrt(np.std(np.subtract(series[lag:], series[:-lag]))) for lag in lags]
    poly = np.polyfit(np.log(lags), np.log(tau), 1)
    return poly[0] * 2.0

def volume_delta(df, period=VOLUME_DELTA_PERIOD):
    delta = df['volume'] * np.where(df['close'] > df['open'], 1, -1)
    return delta.rolling(period).sum()

def compute_pidelta_score_normalized(df, weights=None):
    if len(df) < 50:
        return 0.0
    w = weights or {'trend': 0.25, 'strength': 0.20, 'ker': 0.15,
                    'atr_rel': 0.20, 'momentum_short': 0.20}
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
    raw = (w['trend'] * trend + w['strength'] * strength +
           w['ker'] * ker_val + w['atr_rel'] * atr_rel +
           w['momentum_short'] * mom_norm)
    return np.tanh(raw)

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

# =============================================================================
# COHERENCIA PONDERADA
# =============================================================================
def coherence_weighted(dfs):
    directions = {}
    for tf in COHERENCE_TIMEFRAMES:
        if tf in dfs and dfs[tf] is not None and len(dfs[tf]) >= 50:
            score = compute_pidelta_score_normalized(dfs[tf])
            if score > 0.05:
                directions[tf] = 1
            elif score < -0.05:
                directions[tf] = -1
            else:
                directions[tf] = 0
        else:
            directions[tf] = 0

    long_weight = 0.0
    short_weight = 0.0
    total_weight = 0.0
    for tf, dir in directions.items():
        weight = COHERENCE_WEIGHTS.get(tf, 0.0)
        total_weight += weight
        if dir == 1:
            long_weight += weight
        elif dir == -1:
            short_weight += weight

    if total_weight == 0:
        return 'NEUTRAL', 0.0, directions, 0.0

    if long_weight > short_weight:
        direction = 'LONG'
        coherence = long_weight / total_weight
    elif short_weight > long_weight:
        direction = 'SHORT'
        coherence = short_weight / total_weight
    else:
        direction = 'NEUTRAL'
        coherence = 0.0

    oc_score = 0.5 * coherence + 0.3 * 0.5 + 0.2 * 0.5
    return direction, coherence, directions, oc_score

# =============================================================================
# DATA ENGINE
# =============================================================================
class BybitDataEngine:
    def __init__(self):
        self.cache_dir = CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)
        self.exchanges = {}
        self.primary = None

        for ex_id in ['binance', 'kucoin', 'bybit']:
            try:
                if ex_id == 'binance':
                    ex = ccxt.binance({
                        'enableRateLimit': True,
                        'options': {'defaultType': 'future'}
                    })
                elif ex_id == 'kucoin':
                    ex = ccxt.kucoin({
                        'enableRateLimit': True,
                    })
                elif ex_id == 'bybit':
                    ex = ccxt.bybit({
                        'enableRateLimit': True,
                        'options': {'defaultType': 'future'}
                    })
                ex.load_markets()
                self.exchanges[ex_id] = ex
                if self.primary is None:
                    self.primary = ex_id
                logger.info(f"✅ Conectado a {ex_id}")
            except Exception as e:
                logger.warning(f"❌ {ex_id} falló: {e}")
                self.exchanges[ex_id] = None

        if self.primary is None:
            logger.warning("⚠️ Sin conexión, usando fallback.")
            self.fallback_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT",
                                     "XRP/USDT", "ADA/USDT"]
        else:
            self.fallback_symbols = []

    def get_symbols(self, min_volume=200_000):
        if self.primary and self.exchanges.get(self.primary):
            exchange = self.exchanges[self.primary]
            try:
                tickers = exchange.fetch_tickers()
                symbols = []
                for sym, ticker in tickers.items():
                    if not sym.endswith('USDT'):
                        continue
                    if ticker.get('quoteVolume', 0) < min_volume:
                        continue
                    symbols.append(sym)
                return symbols
            except:
                pass
        return self.fallback_symbols

    def fetch_ohlcv(self, symbol, timeframe='5m', limit=1000, since=None):
        """Obtiene OHLCV con mapeo automático de timeframe por exchange."""
        ex = self.exchanges.get(self.primary)
        if ex is None:
            return None

        # --- MAPEAR TIMEFRAME AL FORMATO DEL EXCHANGE ---
        mapped_tf = map_timeframe(self.primary, timeframe)
        logger.debug(f"Fetching {symbol} {timeframe} -> {mapped_tf} ({self.primary})")

        cache_key = hashlib.md5(f"{symbol}_{timeframe}_{limit}_{since}_{self.primary}".encode()).hexdigest()
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.pkl")

        if os.path.exists(cache_path):
            mod_time = os.path.getmtime(cache_path)
            if (time.time() - mod_time) < 3600:
                try:
                    with open(cache_path, 'rb') as f:
                        return pickle.load(f)
                except:
                    pass

        try:
            since_ts = int(since.timestamp() * 1000) if since else None
            # --- USAR EL TIMEFRAME MAPEADO ---
            ohlcv = ex.fetch_ohlcv(symbol, mapped_tf, limit=limit, since=since_ts)
            if not ohlcv:
                return None

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            with open(cache_path, 'wb') as f:
                pickle.dump(df, f)
            return df

        except Exception as e:
            logger.warning(f"Error fetching {symbol} ({timeframe}->{mapped_tf} en {self.primary}): {e}")
            return None

    def fetch_multi_timeframe(self, symbol):
        dfs = {}
        for tf in COHERENCE_TIMEFRAMES:
            df = self.fetch_ohlcv(symbol, timeframe=tf, limit=300)
            if df is not None:
                dfs[tf] = df
        return dfs

    def fetch_funding_rate(self, symbol):
        ex = self.exchanges.get(self.primary)
        if ex is None:
            return 0.0
        try:
            funding = ex.fetch_funding_rate(symbol)
            return funding.get('fundingRate', 0.0)
        except:
            return 0.0 
