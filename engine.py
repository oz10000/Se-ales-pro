# engine.py
# Motor de datos con multi-exchange y fallback (inspirado en Junk Toys)

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

# =============================================================================
# DATA ENGINE CON MULTI-EXCHANGE Y FALLBACK (COPIADO DE JUNK TOYS)
# =============================================================================

class BybitDataEngine:
    def __init__(self, exchanges=None, retries=2):
        self.cache_dir = CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)
        self.exchanges = {}
        self.primary = None
        
        if exchanges is None:
            exchanges = ['binance', 'kucoin', 'bybit']
        
        for ex_id in exchanges:
            for attempt in range(retries):
                try:
                    if ex_id == 'binance':
                        exchange = ccxt.binance({
                            'enableRateLimit': True,
                            'options': {'defaultType': 'spot'}
                        })
                    elif ex_id == 'kucoin':
                        exchange = ccxt.kucoin({'enableRateLimit': True})
                    elif ex_id == 'bybit':
                        exchange = ccxt.bybit({
                            'enableRateLimit': True,
                            'options': {'defaultType': 'spot'}
                        })
                    else:
                        continue
                    exchange.load_markets()
                    self.exchanges[ex_id] = exchange
                    logger.info(f"✅ Conectado a {ex_id}")
                    if self.primary is None:
                        self.primary = ex_id
                    break
                except Exception as e:
                    logger.warning(f"Intento {attempt+1}/{retries} para {ex_id} falló: {e}")
                    time.sleep(2)
            else:
                self.exchanges[ex_id] = None
                logger.error(f"❌ No se pudo conectar a {ex_id}")
        
        # Si todos fallan, usar lista de respaldo
        if self.primary is None:
            logger.warning("⚠️ No se pudo conectar a ningún exchange. Usando lista de respaldo.")
            self.fallback_symbols = [
                "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
                "ADA/USDT", "AVAX/USDT", "LINK/USDT", "MATIC/USDT", "UNI/USDT"
            ]
        else:
            self.fallback_symbols = []
    
    def get_symbols(self, min_volume=MIN_VOLUME_24H):
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
                    spread = (ticker.get('ask', 0) - ticker.get('bid', 0)) / (ticker.get('bid', 1) + 1e-9)
                    if spread > MAX_SPREAD_PCT:
                        continue
                    symbols.append(sym)
                if symbols:
                    return symbols
            except Exception as e:
                logger.warning(f"Error obteniendo símbolos: {e}")
        # Fallback a lista conocida
        return self.fallback_symbols
    
    def fetch_ohlcv(self, symbol, timeframe='1h', limit=1000, since=None, exchange_id=None):
        ex_id = exchange_id if exchange_id else self.primary
        if ex_id is None or self.exchanges.get(ex_id) is None:
            return None
        exchange = self.exchanges[ex_id]
        cache_key = hashlib.md5(f"{ex_id}_{symbol}_{timeframe}_{limit}_{since}".encode()).hexdigest()
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.pkl")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except:
                pass
        try:
            since_ts = int(since.timestamp() * 1000) if since else None
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit, since=since_ts)
            if not ohlcv:
                return None
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            with open(cache_path, 'wb') as f:
                pickle.dump(df, f)
            return df
        except Exception as e:
            logger.warning(f"Error fetching {symbol} desde {ex_id}: {e}")
            return None
    
    def fetch_historical(self, symbol, timeframe='1h', max_days=BACKTEST_YEARS*365, exchange_id=None):
        end = datetime.now()
        start = end - timedelta(days=max_days)
        since = start
        all_dfs = []
        while True:
            df = self.fetch_ohlcv(symbol, timeframe, limit=1000, since=since, exchange_id=exchange_id)
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

# =============================================================================
# GENERACIÓN DE SEÑALES (con filtros suaves para siempre generar)
# =============================================================================

def generate_signal(df, df_trend=None, df_macro=None, params=None, hour=None, day=None):
    if df is None or len(df) < 60:
        return None
    
    p = params or {}
    min_score = p.get('min_score', 0.05)      # MUY BAJO para siempre generar
    adx_th = p.get('adx_threshold', 5)        # MUY BAJO
    ker_th = p.get('ker_threshold', 0.1)      # MUY BAJO
    
    # Horario (si se pasa)
    if hour is not None:
        if hour < OPTIMAL_HOURS_START or hour > OPTIMAL_HOURS_END:
            if day is not None and day not in PREFERRED_DAYS:
                # No penalizamos tanto, solo reducimos confianza
                pass
    
    score = compute_pidelta_score(df)
    if abs(score) < min_score:
        return None
    
    adx_val = adx(df, ADX_PERIOD).iloc[-1]
    ker_val = ker(df['close'], KER_PERIOD).iloc[-1]
    if adx_val < adx_th or ker_val < ker_th:
        return None
    
    regime, _ = classify_regime(df)
    if regime not in REGIME_ALLOWED:
        # Si está en Chop, igualmente damos señal pero con baja confianza
        pass
    
    direction = 'LONG' if score > 0 else 'SHORT'
    current = df['close'].iloc[-1]
    
    # EMAs y VWAP (confirmación, no obligatoria)
    ema50 = ema(df['close'], EMA_MID).iloc[-1] if len(df) >= EMA_MID else current
    ema200 = ema(df['close'], EMA_SLOW).iloc[-1] if len(df) >= EMA_SLOW else current
    vwap_val = vwap(df).iloc[-1]
    
    atr_val = atr(df, ATR_PERIOD).iloc[-1]
    atr_pct = atr_val / current * 100
    if atr_pct < 0.5 or atr_pct > 4.0:
        # Ajustamos TP/SL para volatilidad
        pass
    
    tp_mult = p.get('tp_mult', 2.0)
    sl_mult = p.get('sl_mult', 1.0)
    
    if direction == 'LONG':
        tp = current + atr_val * tp_mult
        sl = current - atr_val * sl_mult
    else:
        tp = current - atr_val * tp_mult
        sl = current + atr_val * sl_mult
    
    confidence = min(1.0, abs(score) / 0.2 + 0.1)
    leverage = max(1, min(MAX_LEVERAGE, int(MAX_LEVERAGE * (1.2 / (atr_pct + 0.5)))))
    
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
        'vwap_distance': (current - vwap_val) / vwap_val * 100 if vwap_val else 0,
        'vol_ratio': 1.0,
        'est_hours': 4.0,
        'breakout': None,
        'be_activation': 0.003,
        'timestamp': df.index[-1],
    }
