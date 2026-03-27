#!/usr/bin/env python3
"""
test_basic.py — Testes básicos do Funding Rate Monitor.
Uso: py -3 -m pytest tests/ -v
"""
import json
import sys
import os
from pathlib import Path

# Adiciona scripts/ ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))


def test_format_rate_positive():
    """Taxa positiva alta deve ter ícone vermelho."""
    from format_output import format_rate
    item   = {"platform": "binance", "pair": "BTCUSDT",
               "funding_rate": 0.001, "rate_pct": "0.1000%",
               "mark_price": 65000.0}
    result = format_rate(item)
    assert "BTCUSDT" in result
    assert "0.1000%" in result
    assert "🔴" in result


def test_format_rate_negative():
    """Taxa negativa deve ter ícone verde."""
    from format_output import format_rate
    item   = {"platform": "bybit", "pair": "ETHUSDT",
               "funding_rate": -0.001, "rate_pct": "-0.1000%",
               "mark_price": 3200.0}
    result = format_rate(item)
    assert "🟢" in result


def test_format_rate_error():
    """Item com erro deve mostrar ❌."""
    from format_output import format_rate
    item   = {"platform": "okx", "pair": "SOLUSDT", "error": "timeout"}
    result = format_rate(item)
    assert "❌" in result
    assert "timeout" in result


def test_json_roundtrip():
    """Dados devem sobreviver serialização JSON."""
    sample = [
        {"platform": "binance", "pair": "BTCUSDT",
         "funding_rate": 0.0001, "rate_pct": "0.0100%",
         "mark_price": 65000.0, "timestamp": 1700000000},
    ]
    serialized   = json.dumps(sample)
    deserialized = json.loads(serialized)
    assert deserialized[0]["funding_rate"] == 0.0001
    assert deserialized[0]["pair"] == "BTCUSDT"


def test_config_yaml():
    """config.yaml deve carregar corretamente."""
    import yaml
    cfg_file = Path(__file__).parent.parent / "config.yaml"
    assert cfg_file.exists(), "config.yaml não encontrado"
    with open(cfg_file) as f:
        config = yaml.safe_load(f)
    assert "platform_pairs" in config
    assert "thresholds" in config
    assert config["update_frequency_minutes"] > 0


def test_threshold_check():
    """Alertas devem ser gerados corretamente."""
    from monitor import check_thresholds
    config = {
        "thresholds": {
            "BTCUSDT": {"funding_rate_min": -0.03, "funding_rate_max": 0.08}
        },
        "default_thresholds": {"funding_rate_min": -0.03, "funding_rate_max": 0.08}
    }
    data   = [
        {"pair": "BTCUSDT", "funding_rate": 0.001},   # neutro
        {"pair": "ETHUSDT", "funding_rate": 0.09},    # acima
        {"pair": "SOLUSDT", "funding_rate": -0.04},   # abaixo
    ]
    alerts = check_thresholds(data, config)
    pairs  = [a["pair"] for a in alerts]
    assert "ETHUSDT" in pairs
    assert "SOLUSDT" in pairs
    assert "BTCUSDT" not in pairs


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    tests = [
        test_format_rate_positive,
        test_format_rate_negative,
        test_format_rate_error,
        test_json_roundtrip,
        test_config_yaml,
        test_threshold_check,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  OK  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL {t.__name__}: {e}")
            failed += 1
    print(f"\n  {passed}/{len(tests)} testes passaram")
    sys.exit(0 if failed == 0 else 1)
