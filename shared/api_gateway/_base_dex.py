"""
_base_dex.py — Base para clientes DEX.
"""
from .base_client import BaseAPIClient


class BaseDEXClient(BaseAPIClient):
    """Base para todos os clientes de corretoras descentralizadas."""

    def fetch(self, data_type: str, **kwargs) -> dict:
        raise NotImplementedError(
            f"{self.__class__.__name__} não implementou fetch('{data_type}')"
        )
