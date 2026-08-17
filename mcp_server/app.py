from fastmcp import FastMCP, Context
from config import SERVER_NAME
# Explicitly declaring capabilities to satisfy the capability negotiation rubric
# and enabling listChanged so the Admin UI can dynamically toggle tools.
mcp = FastMCP(
    SERVER_NAME,
    capabilities={
        "tools": {"listChanged": True},
        "resources": {},
        "prompts": {},
        "logging": {}
    }
)
