# config.py
# Configuración profesional para Golden Capital Engine Ω - Bybit Futures
# Versión optimizada (Iteración 5) - Auditoría Forense completada

import os
import numpy as np

# ========== EXCHANGE ==========
EXCHANGE = {
    'name': 'binance',
    'market': 'future',
    'api_endpoint': 'https://fapi.binance.com',
    'rate_limit': 1200,
}

# ========== TIMEFRAMES ==========
TIMEFRAMES = ['5m', '15m', '30m', '45m', '1h']
PRIMARY_TF = '5m'
TREND_TF = '1h'
MACRO_TF = '4h'

# Pesos para coherencia ponderada (más peso a timeframes cortos)
COHERENCE_WEIGHTS = {
    '5m': 0.35,
    '15m': 0.25,
    '30m': 0.20,
    '45m': 0.12,
    '1h': 0.08,
}

# ========== INDICADORES ==========
ATR_PERIOD = 14
ADX_PERIOD = 14
KER_PERIOD = 10
HURST_PERIOD = 20
EMA_FAST = 20
EMA_MID = 50
EMA_SLOW = 200
RSI_PERIOD = 14
VWAP_PERIOD = 20
VOLUME_DELTA_PERIOD = 14

# ========== UMBRALES (optimizados con Bayesian Optimization) ==========
MIN_SCORE = 0.12              # Reducido para capturar más señales
ADX_THRESHOLD = 6             # Reducido para mayor sensibilidad
KER_THRESHOLD = 0.15
REGIME_ALLOWED = ['Tendencia_Fuerte', 'Tendencia_Débil', 'Expansión', 'Normal']

# ========== RIESGO ==========
MAX_LEVERAGE = 5
RISK_PER_TRADE = 0.02
MAX_POSITIONS = 3
COMMISSION = 0.0004
SLIPPAGE = 0.0005
INITIAL_CAPITAL = 50.0

# ========== TP/SL/TRAILING (optimizados) ==========
TAKE_PROFIT_MULT = 2.8
STOP_LOSS_MULT = 1.0
TRAIL_ACTIVATION = 0.0045
TRAIL_DISTANCE = 1.0
BREAK_EVEN_ACTIVATION = 0.0035
BREAK_EVEN_BUFFER = 0.001

# ========== COHERENCIA ==========
MIN_COHERENCE = 0.60
COHERENCE_THRESHOLD = 0.80

# ========== BUCKETS ==========
VELOCITY_BUCKETS = {
    'inminente': (0, 5),
    'corto': (5, 15),
    'medio': (15, 30),
    'largo': (30, 45),
    'muy_largo': (45, 60),
}
MIN_VELOCITY_SCORE = 0.45

# Penalización temporal (reducción de score por bucket)
TEMPORAL_PENALTY = {
    'inminente': 1.0,
    'corto': 0.95,
    'medio': 0.85,
    'largo': 0.70,
    'muy_largo': 0.50,
}

# ========== RANKING ==========
TOP_N = 3
RANKING_WEIGHTS = {
    'oc_score': 0.40,
    'coherence': 0.20,
    'velocity': 0.15,
    'win_rate': 0.10,
    'profit_factor': 0.10,
    'temporal_bonus': 0.05,
}

# ========== OPTIMIZACIÓN ==========
WALK_FORWARD_ITERATIONS = 5
WALK_FORWARD_TRAIN = 0.70
WALK_FORWARD_TEST = 0.30
MONTE_CARLO_SIMULATIONS = 10000
BAYESIAN_SAMPLES = 10000
MARKOV_SIMULATIONS = 10000

# ========== DIRECTORIOS ==========
CACHE_DIR = 'data/cache'
RESULTS_DIR = 'results'
for d in [CACHE_DIR, RESULTS_DIR]:
    os.makedirs(d, exist_ok=True)
