# config.py
# Configuración central para Golden Capital Engine Ω - Binance Futures

import os

# ========== EXCHANGE (BINANCE FUTURES) ==========
EXCHANGE = {
    'name': 'binance',
    'market': 'future',          # USDⓈ-M Futures
    'api_endpoint': 'https://fapi.binance.com',
    'rate_limit': 1200,
}

# ========== TIMEFRAMES ==========
TIMEFRAMES = ['5m', '15m', '30m', '1h', '4h', '8h', '1d']
PRIMARY_TF = '1h'
TREND_TF = '4h'
MACRO_TF = '1d'
ENTRY_TF = '15m'

# ========== INDICADORES ==========
ATR_PERIOD = 14
ADX_PERIOD = 14
KER_PERIOD = 10
EMA_FAST = 20
EMA_MID = 50
EMA_SLOW = 200
RSI_PERIOD = 14
VWAP_PERIOD = 20
MIN_VOLUME_RATIO = 0.3

# ========== SEÑALES ==========
MIN_SCORE = 0.18
ADX_THRESHOLD = 14
KER_THRESHOLD = 0.32
REGIME_ALLOWED = ['Tendencia_Fuerte', 'Tendencia_Débil', 'Expansión']

# ========== RIESGO ==========
MAX_LEVERAGE = 5
RISK_PER_TRADE = 0.02
MAX_POSITIONS = 2
COMMISSION = 0.0004          # Binance Futures taker fee
SLIPPAGE = 0.0005
INITIAL_CAPITAL = 1000.0

# ========== TP/SL DINÁMICOS ==========
TAKE_PROFIT_MULT = 2.2
STOP_LOSS_MULT = 1.2
TRAIL_ACTIVATION = 0.0035
TRAIL_DISTANCE = 1.0
BREAK_EVEN_ACTIVATION = 0.003
BREAK_EVEN_BUFFER = 0.001

# ========== OPTIMIZACIÓN DAPS ==========
DAPS_ITERATIONS = 4
OPTUNA_TRIALS = 100
WALK_FORWARD_RATIOS = [0.70, 0.60, 0.50]
MONTE_CARLO_SIMULATIONS = 1000
BACKTEST_YEARS = 2

# ========== RANKING ==========
TOP_N = 10
TOP_DEEP = 5

# ========== HORARIO ÓPTIMO ==========
OPTIMAL_HOURS_START = 8
OPTIMAL_HOURS_END = 20
PREFERRED_DAYS = [1, 2, 3, 4]

# ========== FILTROS DE LIQUIDEZ ==========
MIN_VOLUME_24H = 200_000      # Binance Futures tiene alta liquidez
MAX_SPREAD_PCT = 0.025

# ========== DIRECTORIOS ==========
CACHE_DIR = 'data/cache'
RESULTS_DIR = 'results'

for d in [CACHE_DIR, RESULTS_DIR]:
    os.makedirs(d, exist_ok=True)
