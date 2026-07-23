# config.py
import os

# ==================== DIRECTORIOS ====================
CACHE_DIR = './cache'
REPORTS_DIR = './reports'
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# ==================== EXCHANGE Y DATOS ====================
MIN_VOLUME_USD = 200_000      # <--- ESTA FALTABA
MAX_SYMBOLS = 200             # <--- ESTA TAMBIÉN
TIMEFRAME = '5m'
HISTORICAL_DAYS = 730

# ==================== INDICADORES ====================
ATR_PERIOD = 14
ADX_PERIOD = 14
KER_PERIOD = 10
VOLUME_DELTA_PERIOD = 20

# ==================== COHERENCIA ====================
COHERENCE_TIMEFRAMES = ['5m', '15m', '30m', '45m', '1h']
COHERENCE_WEIGHTS = {
    '5m': 0.35,
    '15m': 0.25,
    '30m': 0.20,
    '45m': 0.10,
    '1h': 0.10,
}

# ==================== RANKING ====================
MIN_SCORE = 0.15
BUCKET_THRESHOLDS = [0.0, 0.33, 0.66, 1.0]

# ==================== BACKTEST ====================
INITIAL_CAPITAL = 10000
COMMISSION = 0.001   # 0.1%
SLIPPAGE = 0.0005

# ==================== WALK-FORWARD ====================
WALK_FORWARD_ITERATIONS = 50
WALK_FORWARD_WINDOW = 365   # días de entrenamiento
WALK_FORWARD_TEST = 90      # días de prueba

# ==================== OPTIMIZACIÓN ====================
OPTIMIZATION_ITERATIONS = 100
