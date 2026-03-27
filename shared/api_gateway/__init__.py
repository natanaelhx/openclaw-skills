"""
api_gateway — OpenClaw API Gateway
Camada de abstração para todas as fontes de dados cripto (CEX + DEX + On-chain + Agregadores).
"""
from .registry import API_REGISTRY
from .base_client import BaseAPIClient, RateLimiter, CacheManager
from .router import APIRouter
from .normalizer import DataNormalizer
from .health_checker import HealthChecker

__all__ = [
    "API_REGISTRY",
    "BaseAPIClient",
    "RateLimiter",
    "CacheManager",
    "APIRouter",
    "DataNormalizer",
    "HealthChecker",
]
