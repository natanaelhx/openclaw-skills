"""
_base_cex.py — Base para clientes CEX.
Herda BaseAPIClient e adiciona método fetch() padrão.
"""
from .base_client import BaseAPIClient


class BaseCEXClient(BaseAPIClient):
    """Base para todos os clientes de corretoras centralizadas."""

    def fetch(self, data_type: str, **kwargs) -> dict:
        raise NotImplementedError(
            f"{self.__class__.__name__} não implementou fetch('{data_type}')"
        )
