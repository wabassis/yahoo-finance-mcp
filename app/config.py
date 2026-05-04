"""Configuração centralizada da aplicação.

Este módulo isola toda leitura de variáveis de ambiente.
A vantagem é ter um único ponto de verdade para configuração,
facilitando manutenção, testes e diagnósticos.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Carrega variáveis de um arquivo .env quando ele existe.
# Em produção, normalmente as variáveis vêm do orquestrador.
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Objeto imutável com todas as configurações runtime."""

    app_api_key: str

    metrics_host: str
    metrics_port: int

    redis_host: str
    redis_port: int
    redis_db: int
    redis_password: str | None

    cache_ttl_seconds: int

    # Transporte MCP: 'stdio' para local e 'streamable-http' para ASGI/HTTP.
    mcp_transport: str
    mcp_host: str
    mcp_port: int
    mcp_path: str


settings = Settings(
    app_api_key=os.getenv("APP_API_KEY", ""),
    metrics_host=os.getenv("METRICS_HOST", "0.0.0.0"),
    metrics_port=int(os.getenv("METRICS_PORT", "9100")),
    redis_host=os.getenv("REDIS_HOST", "redis"),
    redis_port=int(os.getenv("REDIS_PORT", "6379")),
    redis_db=int(os.getenv("REDIS_DB", "0")),
    redis_password=os.getenv("REDIS_PASSWORD"),
    cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "300")),
    mcp_transport=os.getenv("MCP_TRANSPORT", "streamable-http"),
    mcp_host=os.getenv("MCP_HOST", "0.0.0.0"),
    mcp_port=int(os.getenv("MCP_PORT", "8000")),
    mcp_path=os.getenv("MCP_PATH", "/mcp"),
)
