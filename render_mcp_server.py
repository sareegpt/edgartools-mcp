"""
EdgarTools MCP Server - HTTP deployment for Render.com

Run locally:
    python render_mcp_server.py

Deploy on Render:
    Build command: pip install -e ".[ai]" && pip install starlette uvicorn
    Start command: python render_mcp_server.py
    Environment variable: EDGAR_IDENTITY=sari kassar@umich.edu
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from mcp.server import Server
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


def create_mcp_server() -> Server:
    from edgar.ai.mcp.tools import company, search, filing, compare, ownership  # noqa
    from edgar.ai.mcp.tools.base import TOOLS, call_tool_handler
    from mcp import Tool
    from mcp.types import TextContent

    mcp = Server("edgartools")

    @mcp.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=info["name"],
                description=info["description"],
                inputSchema=info["schema"]
            )
            for info in TOOLS.values()
        ]

    @mcp.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
        if arguments is None:
            arguments = {}
        result = await call_tool_handler(name, arguments)
        return [TextContent(type="text", text=result.to_json())]

    return mcp


setup_identity()
mcp_server = create_mcp_server()
session_manager = StreamableHTTPSessionManager(
    app=mcp_server,
    event_store=None,
    json_response=False,
    stateless=True,
)


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
        Mount("/mcp", app=session_manager.handle_request),
    ],
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
