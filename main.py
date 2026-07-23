# main.py
# Punto de entrada principal
import logging
import sys
from engine import BybitDataEngine
from backtester import run_backtest_advanced
from config import MAX_SYMBOLS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def full_pipeline():
    """Ejecuta el pipeline completo: obtener símbolos, backtestear y mostrar resultados."""
    logger.info("🚀 Iniciando pipeline completo...")

    # Inicializar motor de datos
    data_engine = BybitDataEngine()

    # Obtener símbolos (top por volumen)
    symbols = data_engine.get_symbols(max_symbols=MAX_SYMBOLS)
    logger.info(f"📊 Símbolos obtenidos: {len(symbols)}")

    if not symbols:
        logger.error("No se obtuvieron símbolos. Abortando.")
        return

    # Backtestear cada símbolo (limitado a pocos para pruebas)
    results = []
    for sym in symbols[:10]:  # solo top 10 para no sobrecargar
        logger.info(f"🔎 Backtesteando {sym}...")
        res = run_backtest_advanced(sym, data_engine, days=30)  # menos días para prueba rápida
        results.append(res)

    # Ordenar por retorno total (mejores LONG y SHORT)
    long_candidates = sorted([r for r in results if r['total_return'] > 0.01],
                             key=lambda x: x['total_return'], reverse=True)[:3]
    short_candidates = sorted([r for r in results if r['total_return'] < -0.01],
                              key=lambda x: x['total_return'])[:3]

    logger.info(f"✅ TOP 3 LONG: {[(r['symbol'], r['total_return']) for r in long_candidates]}")
    logger.info(f"✅ TOP 3 SHORT: {[(r['symbol'], r['total_return']) for r in short_candidates]}")

    # Aquí podrías añadir lógica de trading real, pero por ahora solo mostramos.

def main():
    try:
        full_pipeline()
    except Exception as e:
        logger.exception(f"❌ Error en pipeline: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
