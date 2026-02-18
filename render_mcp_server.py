"""
EdgarTools MCP Server - HTTP deployment for Render.com

Uses StreamableHTTP transport so remote MCP clients can connect.

Run locally:
    python render_mcp_server.py

Deploy on Render:
    Build command: pip install -e ".[ai]" && pip install starlette uvicorn
    Start command: python render_mcp_server.py
    Environment variable: EDGAR_IDENTITY=sari kassar@umich.edu
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edgartools-mcp-http")


def setup_identity():
    identity = os.environ.get("EDGAR_IDENTITY")
    if identity:
        from edgar import set_identity
        set_identity(identity)
        logger.info(f"EDGAR identity set: {identity}")
    else:
        logger.warning("EDGAR_IDENTITY not set — SEC requests may be rejected")


def import_tools():
    from edgar.ai.mcp.tools import company, search, filing, compare, ownership  # noqa
    from edgar.ai.mcp.tools.base import TOOLS
    return TOOLS


def create_mcp_server() -> Server:
    from edgar.__about__ import __version__
    from edgar.ai.mcp.tools.base import TOOLS, call_tool_handler
    from mcp import Tool
    from mcp.types import TextContent

    import_tools()
    app = Server("edgartools")

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=info["name"],
                description=info["description"],
                inputSchema=info["schema"]
            )
            for info in TOOLS.values()
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
        if arguments is None:
            arguments = {}
        result = await call_tool_handler(name, arguments)
        return [TextContent(type="text", text=result.to_json())]

    return app


setup_identity()
mcp_server = create_mcp_server()
session_manager = StreamableHTTPSessionManager(
    app=mcp_server,
    event_store=None,
    json_response=False,
    stateless=True,
)


async def handle_mcp(request: Request):
    await session_manager.handle_request(request.scope, request.receive, request._send)


async def health(request: Request):
    from edgar.ai.mcp.tools.base import TOOLS
    return JSONResponse({"status": "ok", "tools": list(TOOLS.keys())})


@asynccontextmanager
async def lifespan(app):
    async with session_manager.run():
        logger.info("EdgarTools MCP HTTP server ready")
        yield


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/health", health),
        Mount("/mcp", app=handle_mcp),
    ],
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
