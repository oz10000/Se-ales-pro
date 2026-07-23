# engine.py
# Motor multi-exchange con caché y obtención de datos históricos
import ccxt
import pandas as pd
import numpy as np
import os
import pickle
import hashlib
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from config import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# FUNCIONES AUXILIARES (indicadores y normalización)
# =============================================================================
def median_abs_deviation(series, scale='normal'):
    median = np.median(series)
    mad = np.median(np.abs(series - median))
    if scale == 'normal':
        mad *= 1.4826
    return mad

def normalize_robust(series):
    median = np.median(series)
    mad = median_abs_deviation(series, scale='normal')
    if mad == 0:
        return series
    return (series - median) / mad

# Indicadores básicos (se mantienen igual que antes)
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
# CLASE PRINCIPAL: BybitDataEngine (ahora multi-exchange)
# =============================================================================
class BybitDataEngine:
    def __init__(self):
        self.cache_dir = CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)
        self.exchanges = {}
        self.primary = None
        self.active_exchanges = []

        # Inicializar exchanges
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
                # Cargar mercados para verificar conectividad
                ex.load_markets()
                self.exchanges[ex_id] = ex
                self.active_exchanges.append(ex_id)
                if self.primary is None:
                    self.primary = ex_id
                logger.info(f"✅ Conectado a {ex_id}")
            except Exception as e:
                logger.warning(f"❌ {ex_id} falló: {e}")
                self.exchanges[ex_id] = None

        # Si ningún exchange funciona, usar datos de respaldo (solo para pruebas)
        if self.primary is None:
            logger.warning("⚠️ Sin conexión a ningún exchange. Usando datos simulados (fallback).")
            self.primary = 'fallback'
            self.fallback_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT"]
        else:
            self.fallback_symbols = []

    def get_symbols(self, min_volume=MIN_VOLUME_USD, max_symbols=MAX_SYMBOLS):
        """Obtener lista de símbolos del exchange primario."""
        if self.primary == 'fallback':
            return self.fallback_symbols[:max_symbols]

        exchange = self.exchanges.get(self.primary)
        if exchange is None:
            return self.fallback_symbols

        try:
            tickers = exchange.fetch_tickers()
            symbols = []
            for sym, ticker in tickers.items():
                if not sym.endswith('USDT'):
                    continue
                vol = ticker.get('quoteVolume', 0)
                if vol < min_volume:
                    continue
                symbols.append(sym)
            # Ordenar por volumen y limitar
            symbols_sorted = sorted(symbols, key=lambda s: tickers[s].get('quoteVolume', 0), reverse=True)
            return symbols_sorted[:max_symbols]
        except Exception as e:
            logger.warning(f"Error obteniendo símbolos: {e}")
            return self.fallback_symbols

    def fetch_ohlcv(self, symbol, timeframe='5m', limit=1000, since=None):
        """
        Obtiene OHLCV del exchange primario.
        El timeframe se pasa tal cual a ccxt (ej. '5m', '1h').
        ccxt se encarga de convertirlo al formato que cada exchange espera.
        """
        if self.primary == 'fallback':
            # Generar datos sintéticos para pruebas
            return self._generate_fallback_ohlcv(symbol, timeframe, limit)

        exchange = self.exchanges.get(self.primary)
        if exchange is None:
            return None

        # Construir clave de caché (incluye exchange para evitar conflictos)
        cache_key = hashlib.md5(f"{self.primary}_{symbol}_{timeframe}_{limit}_{since}".encode()).hexdigest()
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.pkl")

        # Intentar cargar de caché (válido por 1 hora)
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
            # Pasar timeframe directamente, sin mapeo manual
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit, since=since_ts)
            if not ohlcv:
                return None

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # Guardar en caché
            with open(cache_path, 'wb') as f:
                pickle.dump(df, f)
            return df

        except Exception as e:
            logger.warning(f"Error fetching {symbol} ({timeframe} en {self.primary}): {e}")
            return None

    def fetch_historical(self, symbol, timeframe='5m', max_days=730):
        """
        Obtiene datos históricos completos para backtesting.
        """
        if self.primary == 'fallback':
            return self._generate_fallback_ohlcv(symbol, timeframe, limit=max_days*288)

        # Calcular límite de velas (aprox)
        # Para 5m: 288 velas/día; para 1h: 24 velas/día; etc.
        if timeframe.endswith('m'):
            minutes = int(timeframe[:-1])
            candles_per_day = 1440 // minutes
        elif timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            candles_per_day = 24 // hours
        elif timeframe.endswith('d'):
            candles_per_day = 1
        else:
            candles_per_day = 288  # default 5m

        limit = max_days * candles_per_day
        df = self.fetch_ohlcv(symbol, timeframe, limit=limit)
        if df is None or len(df) < 100:
            logger.warning(f"No hay suficientes datos para {symbol} en {timeframe}")
            return None

        # Filtrar por antigüedad (opcional)
        cutoff = datetime.now() - timedelta(days=max_days)
        df = df[df.index >= cutoff]
        return df

    def fetch_multi_timeframe(self, symbol):
        """Obtiene datos en múltiples timeframes para coherencia."""
        dfs = {}
        for tf in COHERENCE_TIMEFRAMES:
            df = self.fetch_ohlcv(symbol, timeframe=tf, limit=300)
            if df is not None:
                dfs[tf] = df
        return dfs

    def fetch_funding_rate(self, symbol):
        """Obtiene tasa de financiación (si el exchange lo soporta)."""
        if self.primary == 'fallback':
            return 0.0
        exchange = self.exchanges.get(self.primary)
        if exchange is None:
            return 0.0
        try:
            funding = exchange.fetch_funding_rate(symbol)
            return funding.get('fundingRate', 0.0)
        except:
            return 0.0

    # ---------- Fallback para cuando no hay conexión ----------
    def _generate_fallback_ohlcv(self, symbol, timeframe='5m', limit=1000):
        """Genera datos sintéticos para pruebas sin conexión."""
        logger.info(f"Generando datos sintéticos para {symbol} ({timeframe})")
        # Crear fechas
        end = datetime.now()
        if timeframe.endswith('m'):
            delta = timedelta(minutes=int(timeframe[:-1]))
        elif timeframe.endswith('h'):
            delta = timedelta(hours=int(timeframe[:-1]))
        elif timeframe.endswith('d'):
            delta = timedelta(days=int(timeframe[:-1]))
        else:
            delta = timedelta(minutes=5)

        dates = [end - i*delta for i in range(limit)]
        dates.reverse()

        # Precios simulados (random walk)
        np.random.seed(42)
        returns = np.random.normal(0, 0.01, limit)
        prices = 100 * np.exp(np.cumsum(returns))
        prices = np.maximum(prices, 0.1)

        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices * (1 + np.random.uniform(-0.002, 0.002, limit)),
            'high': prices * (1 + np.random.uniform(0, 0.005, limit)),
            'low': prices * (1 - np.random.uniform(0, 0.005, limit)),
            'close': prices,
            'volume': np.random.uniform(1000, 10000, limit)
        })
        df.set_index('timestamp', inplace=True)
        return df
