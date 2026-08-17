from mcp_server.app import mcp
from mcp_server.database import get_connection
import json


@mcp.resource("sql://policies")
def Fetch_resources() -> str:
    """Read-only resource for getting policy table."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT policy_id, title, content
        FROM Policies
    """)
    policies = cursor.fetchall()
    connection.close()

    if not policies:
        return json.dumps([])

    result = []
    for policie in policies:
        result.append({
            "policy_id": str(policie["policy_id"]),
            "title": policie["title"],
            "content": policie["content"],
        })

    return json.dumps(result)