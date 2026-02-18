"""
EdgarTools MCP Server - HTTP deployment for Render.com

Deploy on Render:
    Build command: pip install -e ".[ai]" && pip install uvicorn
    Start command: python render_mcp_server.py
    Environment variable: EDGAR_IDENTITY=sari kassar@umich.edu

Endpoints:
    GET  /health  - health check
    POST /mcp     - MCP protocol
"""

import logging
import os

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edgartools-mcp-http")

# Set up EDGAR identity
identity = os.environ.get("EDGAR_IDENTITY")
if identity:
    from edgar import set_identity
    set_identity(identity)
    logger.info(f"EDGAR identity set: {identity}")
else:
    logger.warning("EDGAR_IDENTITY not set")

# Import edgar tool handlers
from edgar.ai.mcp.tools import company, search, filing, compare, ownership  # noqa
from edgar.ai.mcp.tools.base import TOOLS, call_tool_handler

# Create FastMCP server (path = /mcp by default)
mcp = FastMCP("edgartools", stateless_http=True)

# Register all edgar tools
for tool_name, info in TOOLS.items():
    def make_handler(name):
        async def handler(**kwargs) -> str:
            result = await call_tool_handler(name, kwargs)
            return result.to_json()
        handler.__name__ = name
        return handler

    mcp.add_tool(
        make_handler(tool_name),
        name=tool_name,
        description=info["description"],
    )


async def health(request: Request):
    return JSONResponse({"status": "ok", "tools": list(TOOLS.keys())})


# Add health route to FastMCP's Starlette app
mcp._custom_starlette_routes = [Route("/health", health)]

# Get the complete app (serves /mcp and /health)
app = mcp.streamable_http_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
