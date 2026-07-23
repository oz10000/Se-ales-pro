# config.py
# Configuración profesional para Golden Capital Engine Ω - Bybit Futures
# Versión completa con todas las constantes necesarias

import os

# ==================== DIRECTORIOS ====================
CACHE_DIR = './cache'
RESULTS_DIR = './results'          # <--- USADO POR report.py y streamlit_app.py
REPORTS_DIR = RESULTS_DIR          # alias para compatibilidad

# Crear directorios automáticamente
for d in [CACHE_DIR, RESULTS_DIR]:
    os.makedirs(d, exist_ok=True)

# ==================== EXCHANGE Y DATOS ====================
MIN_VOLUME_USD = 200_000
MAX_SYMBOLS = 200
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
TOP_N = 3
RANKING_WEIGHTS = {
    'oc_score': 0.40,
    'coherence': 0.20,
    'velocity': 0.15,
    'win_rate': 0.10,
    'profit_factor': 0.10,
    'temporal_bonus': 0.05,
}

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
OPTUNA_TRIALS = 100
BACKTEST_YEARS = 2

# ==================== UMBRALES ADICIONALES ====================
ADX_THRESHOLD = 6
KER_THRESHOLD = 0.15
REGIME_ALLOWED = ['Tendencia_Fuerte', 'Tendencia_Débil', 'Expansión', 'Normal']

# ==================== TP/SL/TRAILING ====================
TAKE_PROFIT_MULT = 2.8
STOP_LOSS_MULT = 1.0
TRAIL_ACTIVATION = 0.0045
TRAIL_DISTANCE = 1.0
BREAK_EVEN_ACTIVATION = 0.0035
BREAK_EVEN_BUFFER = 0.001

# ==================== COHERENCIA ====================
MIN_COHERENCE = 0.60
COHERENCE_THRESHOLD = 0.80

# ==================== BUCKETS ====================
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

# ==================== MONTE CARLO ====================
MONTE_CARLO_SIMULATIONS = 10000
BAYESIAN_SAMPLES = 10000
MARKOV_SIMULATIONS = 10000

# ==================== RIESGO ====================
MAX_LEVERAGE = 5
RISK_PER_TRADE = 0.02
MAX_POSITIONS = 3
