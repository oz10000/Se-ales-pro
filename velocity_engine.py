# velocity_engine.py
# Motor de velocidad con coherencia ponderada y penalización temporal

import pandas as pd
import numpy as np
from engine import atr, adx, ema, compute_pidelta_score_normalized, coherence_weighted
from config import *

def calculate_velocity_score(df, dfs_extra=None):
    """
    Calcula el score de velocidad con coherencia ponderada y penalización temporal.
    dfs_extra: dict con timeframes adicionales para coherencia.
    """
    if df is None or len(df) < 20:
        return {
            'score': 0.0,
            'time_minutes': 30.0,
            'bucket': 'medio',
            'oc_score': 0.0,
            'temporal_penalty': 1.0,
        }

    close = df['close']
    volume = df['volume']

    # 1. Pendiente
    ema5 = ema(close, 5)
    slope = (ema5.iloc[-1] - ema5.iloc[-5]) / ema5.iloc[-5] if len(ema5) >= 5 else 0
    slope_norm = min(1.0, max(0, slope * 10))

    # 2. ADX
    adx_val = adx(df, 14).iloc[-1] if len(df) >= 14 else 0
    adx_norm = min(1.0, adx_val / 40.0)

    # 3. ATR%
    atr_val = atr(df, 14).iloc[-1] if len(df) >= 14 else 0
    atr_pct = atr_val / close.iloc[-1] * 100
    atr_norm = min(1.0, atr_pct / 3.0)

    # 4. Momentum
    roc = close.pct_change(5).iloc[-1] * 100 if len(close) >= 5 else 0
    mom_norm = min(1.0, abs(roc) / 5.0)

    # 5. Volumen relativo
    vol_ma20 = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else volume.iloc[-1]
    vol_ratio = volume.iloc[-1] / vol_ma20 if vol_ma20 > 0 else 1.0
    vol_norm = min(2.0, vol_ratio) / 2.0

    # 6. Distancia a la entrada
    score = compute_pidelta_score_normalized(df)
    entry_distance = abs(score) / 0.3 if abs(score) > 0 else 0.5
    dist_norm = min(1.0, entry_distance)

    # Score de velocidad base
    velocity_score = (0.25 * slope_norm +
                      0.20 * adx_norm +
                      0.15 * atr_norm +
                      0.15 * mom_norm +
                      0.15 * vol_norm +
                      0.10 * dist_norm)

    # Coherencia (si hay datos)
    coherence = 0.5
    oc_score = 0.0
    if dfs_extra and len(dfs_extra) > 0:
        dfs = {'5m': df, **dfs_extra}
        direction, coherence, dirs, oc_base = coherence_weighted(dfs)
        oc_score = 0.5 * coherence + 0.3 * adx_norm + 0.2 * mom_norm

    # Tiempo estimado
    speed_factor = (slope_norm * 0.5 + adx_norm * 0.3 + vol_norm * 0.2) * 2
    time_minutes = max(1, 30 / (speed_factor + 0.2))

    # Bucket
    if time_minutes <= 5:
        bucket = 'inminente'
    elif time_minutes <= 15:
        bucket = 'corto'
    elif time_minutes <= 30:
        bucket = 'medio'
    elif time_minutes <= 45:
        bucket = 'largo'
    else:
        bucket = 'muy_largo'

    # Penalización temporal
    temporal_penalty = TEMPORAL_PENALTY.get(bucket, 1.0)

    # Score final
    final_score = (0.6 * velocity_score + 0.4 * coherence) * temporal_penalty

    return {
        'score': round(final_score, 3),
        'velocity_score': round(velocity_score, 3),
        'coherence': round(coherence, 3),
        'oc_score': round(oc_score, 3),
        'time_minutes': round(time_minutes, 1),
        'bucket': bucket,
        'temporal_penalty': temporal_penalty,
        'components': {
            'slope': round(slope_norm, 3),
            'adx': round(adx_norm, 3),
            'atr': round(atr_norm, 3),
            'momentum': round(mom_norm, 3),
            'volume': round(vol_norm, 3),
            'distance': round(dist_norm, 3),
        }
    }
