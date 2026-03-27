"""
jupiter.py — Cliente Jupiter Aggregator (Solana) para o OpenClaw API Gateway.
"""
from .._base_dex import BaseDEXClient


class JupiterClient(BaseDEXClient):

    NAME          = "jupiter"
    BASE_URL      = "https://price.jup.ag/v6"
    BASE_QUOTE    = "https://quote-api.jup.ag/v6"
    CALLS_PER_MIN = 60
    CACHE_TTL     = 60
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = ["price", "swap_routes", "token_list"]

    def _health_check(self):
        self.session.get(self.BASE_URL + "/price?ids=SOL", timeout=5).raise_for_status()

    def fetch(self, data_type: str, **kwargs) -> dict:
        if data_type == "price":
            return self._price(kwargs.get("tokens", "SOL"))
        raise ValueError(f"JupiterClient não suporta: {data_type}")

    def _price(self, tokens: str) -> dict:
        data = self.get("/price", params={"ids": tokens})
        result = {}
        for token_id, info in data.get("data", {}).items():
            result[token_id] = {
                "symbol":    info.get("id", token_id),
                "price_usd": float(info.get("price", 0)),
                "source":    "jupiter",
            }
        return {"prices": result, "source": "jupiter"}

    def get_quote(self, input_mint: str, output_mint: str, amount: int) -> dict:
        """Busca melhor rota de swap."""
        import json, requests as _req
        resp = self.session.get(self.BASE_QUOTE + "/quote", params={
            "inputMint":  input_mint,
            "outputMint": output_mint,
            "amount":     amount,
        }, timeout=10)
        resp.raise_for_status()
        return resp.json()
