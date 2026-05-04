"""Ponto de entrada do servidor MCP Yahoo Finance.

Este arquivo faz quatro coisas principais:
1) Instancia o servidor FastMCP.
2) Registra as ferramentas (tools) expostas ao cliente.
3) Configura métricas e runtime.
4) Exporta um objeto ASGI chamado `app` para uso com Uvicorn.

O erro original do container era:
`Attribute "app" not found in module "app.main"`.
A correção é garantir que este módulo exponha explicitamente `app`.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from prometheus_client import start_http_server

from app.config import settings
from app.service import YahooFinanceService

# Instância principal do servidor MCP.
mcp = FastMCP(
    "yahoo-finance-mcp",
    host=settings.mcp_host,
    port=settings.mcp_port,
    streamable_http_path=settings.mcp_path,
)

# Camada de serviço com lógica de negócio e cache.
service = YahooFinanceService()

# Controle interno para não subir métricas duas vezes.
_metrics_started = False


def _configure_runtime() -> None:
    """Sincroniza parâmetros runtime e inicia endpoint de métricas."""
    global _metrics_started

    mcp.settings.host = settings.mcp_host
    mcp.settings.port = settings.mcp_port
    mcp.settings.streamable_http_path = settings.mcp_path

    if not _metrics_started:
        start_http_server(settings.metrics_port, addr=settings.metrics_host)
        _metrics_started = True


def _assert_api_key(api_key: str) -> None:
    """Valida API key obrigatória para uso das ferramentas."""
    if not settings.app_api_key:
        raise ValueError("APP_API_KEY não configurada no ambiente (.env).")
    if api_key != settings.app_api_key:
        raise PermissionError("API key inválida.")


@mcp.tool()
def yahoo_cash_flow(symbol: str, api_key: str) -> dict:
    """Tool MCP para consultar cash flow anual."""
    _assert_api_key(api_key)
    return service.get_cash_flow(symbol)


@mcp.tool()
def yahoo_income_statement(symbol: str, api_key: str) -> dict:
    """Tool MCP para consultar income statement anual."""
    _assert_api_key(api_key)
    return service.get_income_statement(symbol)


@mcp.tool()
def yahoo_balance_sheet(symbol: str, api_key: str) -> dict:
    """Tool MCP para consultar balance sheet anual."""
    _assert_api_key(api_key)
    return service.get_balance_sheet(symbol)


@mcp.tool()
def yahoo_quote(symbol: str, api_key: str) -> dict:
    """Tool MCP para consultar cotação intradiária."""
    _assert_api_key(api_key)
    return service.get_quote(symbol)


# --- Correção principal ---
# Exporta explicitamente o app ASGI esperado por: uvicorn app.main:app
_configure_runtime()
app = mcp.streamable_http_app()


if __name__ == "__main__":
    if settings.mcp_transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http")
