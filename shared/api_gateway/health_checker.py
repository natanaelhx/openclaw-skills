"""
health_checker.py — Verifica quais APIs estão online e funcionando.
Executa em paralelo com ThreadPoolExecutor.
"""
import sys
import time
import importlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from .registry import API_REGISTRY


class HealthChecker:
    """
    Verifica quais APIs estão online e funcionando.
    """

    TIMEOUT = 8  # segundos por API

    def check_all(self, verbose: bool = True) -> Dict[str, dict]:
        """Testa TODAS as APIs do registry em paralelo."""
        results = {}
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {
                executor.submit(self._check_one, name): name
                for name in API_REGISTRY
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    results[name] = {"status": "error", "latency_ms": -1, "error": str(e)}
        if verbose:
            self.print_report(results)
        return results

    def check_by_category(self, category: str, verbose: bool = True) -> Dict[str, dict]:
        """Testa apenas uma categoria: 'cex', 'dex', 'aggregators', 'onchain'."""
        targets = {k: v for k, v in API_REGISTRY.items() if v.get("category") == category}
        results = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(self._check_one, name): name
                for name in targets
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    results[name] = {"status": "error", "latency_ms": -1, "error": str(e)}
        if verbose:
            self.print_report(results)
        return results

    def _check_one(self, api_name: str) -> dict:
        """Testa uma única API e retorna status."""
        reg = API_REGISTRY[api_name]
        start = time.time()
        try:
            mod = importlib.import_module(reg["module"])
            cls = getattr(mod, reg["class"])
            client = cls()
            ok = client.is_available()
            latency = int((time.time() - start) * 1000)
            return {
                "status":     "online" if ok else "offline",
                "latency_ms": latency,
                "error":      None,
                "category":   reg.get("category", ""),
                "display":    reg.get("display_name", api_name),
            }
        except ImportError:
            return {
                "status":     "not_implemented",
                "latency_ms": -1,
                "error":      "módulo não implementado",
                "category":   reg.get("category", ""),
                "display":    reg.get("display_name", api_name),
            }
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            return {
                "status":     "offline",
                "latency_ms": latency,
                "error":      str(e)[:80],
                "category":   reg.get("category", ""),
                "display":    reg.get("display_name", api_name),
            }

    def print_report(self, results: Dict[str, dict]):
        """Imprime relatório formatado com status de todas as APIs."""
        categories = {
            "cex":         ("CEX (Corretoras Centralizadas)", []),
            "dex":         ("DEX (Corretoras Descentralizadas)", []),
            "aggregators": ("AGREGADORES", []),
            "onchain":     ("RPC ON-CHAIN", []),
        }

        for name, data in results.items():
            cat = data.get("category", "")
            if cat in categories:
                categories[cat][1].append((name, data))

        width = 62
        border = "═" * width
        print(f"\n╔{border}╗")
        print(f"║{'API GATEWAY — STATUS DAS APIS':^{width}}║")

        total   = len(results)
        online  = sum(1 for d in results.values() if d["status"] == "online")
        offline = total - online

        for cat_key, (cat_name, items) in categories.items():
            if not items:
                continue
            print(f"╠{border}╣")
            print(f"║  {cat_name:<{width-2}}║")
            for name, data in sorted(items, key=lambda x: x[0]):
                status  = data["status"]
                display = data.get("display", name)
                lat     = data["latency_ms"]
                icon    = "✅" if status == "online" else ("⏳" if status == "not_implemented" else "❌")
                lat_str = f"<{lat}ms" if lat >= 0 else "n/a"
                row     = f"  {icon} {display:<20} {status:<16} {lat_str}"
                print(f"║{row:<{width}}║")

        print(f"╠{border}╣")
        summary = f"  TOTAL: {online}/{total} online  |  {offline} offline"
        print(f"║{summary:<{width}}║")
        print(f"╚{border}╝\n")


if __name__ == "__main__":
    hc = HealthChecker()
    hc.check_all()
