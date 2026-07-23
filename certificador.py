#!/usr/bin/env python3
"""
Certificador Universal de Conectividad - Golden Capital Engine
Verifica automáticamente la disponibilidad de endpoints públicos
para OKX, Binance, Bybit, Bitget y Kraken.
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

EXCHANGES = {
    'okx': {
        'base_url': 'https://www.okx.com',
        'instruments': '/api/v5/public/instruments?instType=FUTURES',
        'tickers': '/api/v5/market/tickers?instType=FUTURES',
        'candles': '/api/v5/market/candles?instId=BTC-USDT&bar=5m&limit=10',
        'symbol_format': 'BTC-USDT',
    },
    'binance': {
        'base_url': 'https://api.binance.com',
        'instruments': '/api/v3/exchangeInfo',
        'tickers': '/api/v3/ticker/24hr',
        'candles': '/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=10',
        'symbol_format': 'BTCUSDT',
    },
    'bybit': {
        'base_url': 'https://api.bybit.com',
        'instruments': '/v5/market/instruments-info?category=linear',
        'tickers': '/v5/market/tickers?category=linear',
        'candles': '/v5/market/kline?category=linear&symbol=BTCUSDT&interval=5&limit=10',
        'symbol_format': 'BTCUSDT',
    },
    'bitget': {
        'base_url': 'https://api.bitget.com',
        'instruments': '/api/mix/v1/market/contracts?productType=USDT-FUTURES',
        'tickers': '/api/mix/v1/market/tickers?productType=USDT-FUTURES',
        'candles': '/api/v3/market/candles?category=USDT-FUTURES&symbol=BTCUSDT&interval=5m&limit=10',
        'symbol_format': 'BTCUSDT',
    },
    'kraken': {
        'base_url': 'https://api.kraken.com',
        'instruments': '/0/public/AssetPairs',
        'tickers': '/0/public/Ticker?pair=XBTUSD',
        'candles': '/0/public/OHLC?pair=XBTUSD&interval=5',
        'symbol_format': 'XBTUSD',
    }
}

def test_endpoint(exchange: str, endpoint_type: str, url: str) -> Dict:
    """Prueba un endpoint y retorna métricas."""
    start = time.time()
    result = {
        'exchange': exchange,
        'endpoint': endpoint_type,
        'url': url,
        'status': 'unknown',
        'response_time': 0,
        'error': None,
        'data_count': 0,
    }
    
    try:
        response = requests.get(url, timeout=10)
        result['response_time'] = round((time.time() - start) * 1000, 2)
        result['status'] = 'success' if response.status_code == 200 else 'error'
        result['status_code'] = response.status_code
        
        if response.status_code == 200:
            data = response.json()
            result['data_count'] = len(str(data))  # Aproximación
        else:
            result['error'] = response.text[:200]
            
    except requests.exceptions.Timeout:
        result['status'] = 'timeout'
        result['error'] = 'Timeout after 10s'
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)[:200]
    
    return result

def run_certification():
    """Ejecuta la certificación completa."""
    print("=" * 80)
    print(f"CERTIFICADOR UNIVERSAL DE CONECTIVIDAD")
    print(f"Fecha: {datetime.now().isoformat()}")
    print("=" * 80)
    
    results = []
    for exchange, endpoints in EXCHANGES.items():
        print(f"\n🔍 Probando {exchange.upper()}...")
        for endpoint_type in ['instruments', 'tickers', 'candles']:
            url = endpoints['base_url'] + endpoints[endpoint_type]
            result = test_endpoint(exchange, endpoint_type, url)
            results.append(result)
            
            status_icon = "✅" if result['status'] == 'success' else "❌"
            print(f"  {status_icon} {endpoint_type}: {result['status']} "
                  f"({result['response_time']}ms)")
            if result.get('error'):
                print(f"     Error: {result['error'][:100]}")
    
    # Generar reporte
    report = {
        'timestamp': datetime.now().isoformat(),
        'results': results,
        'summary': {
            'total': len(results),
            'success': sum(1 for r in results if r['status'] == 'success'),
            'errors': sum(1 for r in results if r['status'] == 'error'),
            'timeouts': sum(1 for r in results if r['status'] == 'timeout'),
        }
    }
    
    with open('certification_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print("\n" + "=" * 80)
    print("RESUMEN")
    print("=" * 80)
    print(f"✅ Exitosos: {report['summary']['success']}")
    print(f"❌ Errores: {report['summary']['errors']}")
    print(f"⏰ Timeouts: {report['summary']['timeouts']}")
    print(f"\n📄 Reporte guardado en certification_report.json")

if __name__ == '__main__':
    run_certification()
