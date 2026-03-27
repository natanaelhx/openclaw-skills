"""
base_client.py — Cliente base para todos os clientes de API do OpenClaw.
Fornece: retry automático, cache em disco, rate limiting, logging.
"""
import requests
import time
import json
import os
import hashlib
from datetime import datetime, timezone
from typing import Optional, Any


class RateLimiter:
    """Controla rate limit por API usando token bucket algorithm."""

    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = calls_per_minute
        self.calls = []

    def wait_if_needed(self):
        now = time.time()
        self.calls = [t for t in self.calls if now - t < 60]
        if len(self.calls) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        self.calls.append(now)


class CacheManager:
    """Cache em disco para dados com TTL configurável."""

    CACHE_DIR = os.path.expanduser("~/.moltbot/cache")

    def __init__(self, ttl_seconds: int = 1800):
        self.ttl = ttl_seconds
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    def _key_to_path(self, key: str) -> str:
        h = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.CACHE_DIR, f"{h}.json")

    def get(self, key: str) -> Optional[Any]:
        path = self._key_to_path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            if time.time() - data["timestamp"] > self.ttl:
                os.remove(path)
                return None
            return data["value"]
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def set(self, key: str, value: Any):
        path = self._key_to_path(key)
        try:
            with open(path, "w") as f:
                json.dump({"timestamp": time.time(), "value": value}, f)
        except OSError:
            pass

    def invalidate(self, key: str):
        path = self._key_to_path(key)
        if os.path.exists(path):
            os.remove(path)

    def clear_all(self):
        for fname in os.listdir(self.CACHE_DIR):
            if fname.endswith(".json"):
                try:
                    os.remove(os.path.join(self.CACHE_DIR, fname))
                except OSError:
                    pass


class BaseAPIClient:
    """
    Cliente base que TODOS os clientes de API herdam.
    Fornece: retry automático, cache, rate limiting, logging.
    """

    # Subclasses DEVEM definir esses atributos:
    NAME          = "base"
    BASE_URL      = ""
    CALLS_PER_MIN = 30
    CACHE_TTL     = 1800
    REQUIRES_KEY  = False
    FREE_TIER     = True
    SUPPORTS      = []

    def __init__(self, api_key: str = None, cache_ttl: int = None):
        self.api_key      = api_key
        self.rate_limiter = RateLimiter(self.CALLS_PER_MIN)
        self.cache        = CacheManager(cache_ttl or self.CACHE_TTL)
        self.session      = requests.Session()
        self.session.headers.update({
            "User-Agent": "OpenClaw/1.0 (moltbot)",
            "Accept":     "application/json",
        })
        if api_key:
            self._set_auth_header(api_key)

    def _set_auth_header(self, key: str):
        """Subclasses sobrescrevem para definir o header de auth correto."""
        pass

    def get(self, endpoint: str, params: dict = None,
            use_cache: bool = True, cache_key: str = None) -> dict:
        """Método GET com retry automático (3x), cache e rate limit."""
        url = self.BASE_URL + endpoint
        key = cache_key or f"{url}:{json.dumps(params or {}, sort_keys=True)}"

        if use_cache:
            cached = self.cache.get(key)
            if cached is not None:
                return cached

        self.rate_limiter.wait_if_needed()

        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if use_cache:
                    self.cache.set(key, data)
                return data
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    wait = (2 ** attempt) * 5
                    print(f"  ⚠️ Rate limit em {self.NAME}, aguardando {wait}s...")
                    time.sleep(wait)
                elif e.response.status_code in [502, 503, 504]:
                    time.sleep(2 ** attempt)
                else:
                    raise
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout):
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    raise

        raise Exception(f"Falha após 3 tentativas em {self.NAME}: {url}")

    def post(self, endpoint: str, body: dict = None) -> dict:
        """POST sem cache (para GraphQL e endpoints que precisam de body)."""
        self.rate_limiter.wait_if_needed()
        url = self.BASE_URL + endpoint
        resp = self.session.post(url, json=body, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def graphql(self, query: str, variables: dict = None,
                cache_key: str = None) -> dict:
        """Query GraphQL com cache."""
        body = {"query": query, "variables": variables or {}}
        key  = cache_key or hashlib.md5(
            json.dumps(body, sort_keys=True).encode()
        ).hexdigest()
        cached = self.cache.get(key)
        if cached:
            return cached
        self.rate_limiter.wait_if_needed()
        resp = self.session.post(self.BASE_URL, json=body, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        self.cache.set(key, data)
        return data

    def is_available(self) -> bool:
        """Testa se a API está online."""
        try:
            self._health_check()
            return True
        except Exception:
            return False

    def _health_check(self):
        """Subclasses sobrescrevem com endpoint de ping da API."""
        self.session.get(self.BASE_URL, timeout=5).raise_for_status()

    def _now_utc(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
