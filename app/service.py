"""Camada de serviço Yahoo Finance com cache e métricas.

Responsabilidades deste módulo:
1) Consultar dados no Yahoo Finance via yfinance.
2) Aplicar cache (Redis + memória) para reduzir latência e custo.
3) Expor métricas de volume e latência para observabilidade.
"""

from __future__ import annotations

import json
from typing import Any

import redis
import yfinance as yf
from cachetools import TTLCache
from prometheus_client import Counter, Histogram

from app.config import settings

# Cache local em memória para fallback quando Redis não estiver disponível.
_memory_cache = TTLCache(maxsize=1_000, ttl=settings.cache_ttl_seconds)

# Métricas Prometheus para contagem e latência por tipo de recurso.
YAHOO_REQUESTS_TOTAL = Counter(
    "yahoo_requests_total",
    "Total de chamadas ao Yahoo Finance por tipo de recurso.",
    ["resource"],
)

YAHOO_REQUEST_DURATION_SECONDS = Histogram(
    "yahoo_request_duration_seconds",
    "Tempo de resposta das consultas ao Yahoo Finance.",
    ["resource"],
)


class YahooFinanceService:
    """Serviço de leitura de dados financeiros com cache Redis + memória."""

    def __init__(self) -> None:
        """Inicializa conexão Redis; falha aqui não derruba a aplicação."""
        self.redis_client: redis.Redis | None = None
        try:
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
            self.redis_client.ping()
        except Exception:
            self.redis_client = None

    def _cache_get(self, key: str) -> dict[str, Any] | None:
        """Lê do Redis e, se necessário, faz fallback para cache em memória."""
        if self.redis_client:
            try:
                raw = self.redis_client.get(key)
                if raw:
                    loaded = json.loads(raw)
                    if isinstance(loaded, dict):
                        return loaded
            except Exception:
                pass

        value = _memory_cache.get(key)
        return value if isinstance(value, dict) else None

    def _cache_set(self, key: str, value: dict[str, Any]) -> None:
        """Escreve no Redis e também na memória para maior resiliência."""
        if self.redis_client:
            try:
                self.redis_client.setex(key, settings.cache_ttl_seconds, json.dumps(value))
            except Exception:
                pass
        _memory_cache[key] = value

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Normaliza ticker para caixa alta e valida entrada vazia."""
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol não pode ser vazio.")
        return normalized

    @staticmethod
    def _normalize_dataframe(dataframe: Any) -> dict[str, Any]:
        """Converte DataFrame em dicionário serializável para resposta MCP."""
        if dataframe is None or getattr(dataframe, "empty", True):
            return {}
        return dataframe.fillna("").to_dict()

    def get_cash_flow(self, symbol: str) -> dict[str, Any]:
        """Retorna fluxo de caixa anual do ticker."""
        normalized_symbol = self._normalize_symbol(symbol)
        cache_key = f"cashflow:{normalized_symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        YAHOO_REQUESTS_TOTAL.labels(resource="cash_flow").inc()
        with YAHOO_REQUEST_DURATION_SECONDS.labels(resource="cash_flow").time():
            data = self._normalize_dataframe(yf.Ticker(normalized_symbol).cashflow)

        result = {"symbol": normalized_symbol, "cash_flow": data}
        self._cache_set(cache_key, result)
        return result

    def get_income_statement(self, symbol: str) -> dict[str, Any]:
        """Retorna demonstrativo de resultados anual."""
        normalized_symbol = self._normalize_symbol(symbol)
        cache_key = f"income:{normalized_symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        YAHOO_REQUESTS_TOTAL.labels(resource="income_statement").inc()
        with YAHOO_REQUEST_DURATION_SECONDS.labels(resource="income_statement").time():
            data = self._normalize_dataframe(yf.Ticker(normalized_symbol).financials)

        result = {"symbol": normalized_symbol, "income_statement": data}
        self._cache_set(cache_key, result)
        return result

    def get_balance_sheet(self, symbol: str) -> dict[str, Any]:
        """Retorna balanço patrimonial anual."""
        normalized_symbol = self._normalize_symbol(symbol)
        cache_key = f"balance:{normalized_symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        YAHOO_REQUESTS_TOTAL.labels(resource="balance_sheet").inc()
        with YAHOO_REQUEST_DURATION_SECONDS.labels(resource="balance_sheet").time():
            data = self._normalize_dataframe(yf.Ticker(normalized_symbol).balance_sheet)

        result = {"symbol": normalized_symbol, "balance_sheet": data}
        self._cache_set(cache_key, result)
        return result

    def get_quote(self, symbol: str) -> dict[str, Any]:
        """Retorna cotação intradiária mais recente."""
        normalized_symbol = self._normalize_symbol(symbol)
        cache_key = f"quote:{normalized_symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        YAHOO_REQUESTS_TOTAL.labels(resource="quote").inc()
        with YAHOO_REQUEST_DURATION_SECONDS.labels(resource="quote").time():
            try:
                history = yf.Ticker(normalized_symbol).history(period="1d", interval="1m")
            except Exception as exc:
                result = {"symbol": normalized_symbol, "quote": {}, "error": f"quote_unavailable: {exc}"}
                self._cache_set(cache_key, result)
                return result

        if history is None or getattr(history, "empty", True):
            result = {"symbol": normalized_symbol, "quote": {}}
            self._cache_set(cache_key, result)
            return result

        last_row = history.tail(1).iloc[0]
        result = {
            "symbol": normalized_symbol,
            "quote": {
                "timestamp": str(history.index[-1]),
                "open": float(last_row["Open"]),
                "high": float(last_row["High"]),
                "low": float(last_row["Low"]),
                "close": float(last_row["Close"]),
                "volume": int(last_row["Volume"]),
            },
        }
        self._cache_set(cache_key, result)
        return result
