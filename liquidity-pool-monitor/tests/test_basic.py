#!/usr/bin/env python3
"""
test_basic.py — Testes básicos do Liquidity Pool Monitor.
Uso: py -3 -m pytest tests/ -v
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
# shared/ pode estar em ../../shared ou ../../../shared dependendo do contexto
for _candidate in [
    Path(__file__).parent.parent.parent / "shared",
    Path(__file__).parent.parent.parent.parent / "shared",
]:
    if _candidate.exists():
        sys.path.insert(0, str(_candidate))
        break


def test_config_yaml():
    """config.yaml deve carregar com campos obrigatórios."""
    import yaml
    cfg_file = Path(__file__).parent.parent / "config.yaml"
    assert cfg_file.exists(), "config.yaml não encontrado"
    with open(cfg_file) as f:
        config = yaml.safe_load(f)
    assert "chains" in config
    assert "filters" in config
    assert config["filters"]["min_tvl"] > 0
    assert config["filters"]["min_apr"] >= 0
    assert config["filters"]["max_apr"] > config["filters"]["min_apr"]


def test_pool_normalizer_defillama():
    """Normalizer deve converter pool DefiLlama corretamente."""
    from api_gateway.normalizer import DataNormalizer
    raw = {
        "pool":        "test-uuid-123",
        "chain":       "Ethereum",
        "project":     "uniswap-v3",
        "symbol":      "USDC-WETH",
        "tvlUsd":      5000000.0,
        "apy":         12.5,
        "apyBase":     10.0,
        "apyReward":   2.5,
        "volumeUsd24h": 500000.0,
        "il7d":        -0.3,
    }
    pool = DataNormalizer._pool_from_defillama(raw)
    assert pool["pool_id"]    == "test-uuid-123"
    assert pool["protocol"]   == "uniswap-v3"
    assert pool["chain"]      == "Ethereum"
    assert pool["tvl_usd"]    == 5000000.0
    assert pool["apr_total"]  == 12.5
    assert pool["apr_base"]   == 10.0
    assert pool["apr_reward"] == 2.5
    assert pool["source"]     == "defillama"


def test_risk_score_baixo():
    """Pool grande em protocolo confiável deve ter risco BAIXO."""
    from api_gateway.normalizer import _risk_score
    assert _risk_score(15.0, 5_000_000, "uniswap-v3") == "BAIXO"


def test_risk_score_alto():
    """TVL muito baixo deve gerar risco ALTO."""
    from api_gateway.normalizer import _risk_score
    assert _risk_score(50.0, 50_000, "unknown") == "ALTO"


def test_safe_tokens_in_config():
    """Tokens seguros devem estar no config."""
    import yaml
    cfg_file = Path(__file__).parent.parent / "config.yaml"
    with open(cfg_file) as f:
        config = yaml.safe_load(f)
    safe = config.get("safe_tokens", [])
    assert "USDC" in safe
    assert "WETH" in safe
    assert "DAI"  in safe


def test_pool_sort_by_tvl():
    """Lista de pools deve poder ser ordenada por TVL."""
    pools = [
        {"symbol": "A/B", "tvl_usd": 1_000_000, "apr_total": 10.0},
        {"symbol": "C/D", "tvl_usd": 5_000_000, "apr_total":  8.0},
        {"symbol": "E/F", "tvl_usd":   500_000, "apr_total": 20.0},
    ]
    sorted_pools = sorted(pools, key=lambda x: x["tvl_usd"], reverse=True)
    assert sorted_pools[0]["symbol"] == "C/D"
    assert sorted_pools[-1]["symbol"] == "E/F"


if __name__ == "__main__":
    tests = [
        test_config_yaml,
        test_pool_normalizer_defillama,
        test_risk_score_baixo,
        test_risk_score_alto,
        test_safe_tokens_in_config,
        test_pool_sort_by_tvl,
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
