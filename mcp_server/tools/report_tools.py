from mcp_server.app import mcp
from mcp_server.database import get_connection
from fastmcp import Context
import asyncio




@mcp.tool()
async def generate_disruption_report(
    ctx: Context
):

    """
    Generate today's disruption report.
    """

    connection = get_connection()
    cursor = connection.cursor()

    ####################################################
    # MCP Progress 10%
    ####################################################

    await ctx.report_progress(
    progress=10,
    total=100
)

    cursor.execute("""
        SELECT COUNT(*)
        FROM Flights
        WHERE status='Delayed'
    """)

    delayed = cursor.fetchone()[0]

    ####################################################
    # MCP Progress 30%
    ####################################################

    await ctx.report_progress(
        progress=30,
        total=100
    )

    cursor.execute("""
        SELECT COUNT(*)
        FROM Flights
        WHERE status='Cancelled'
    """)

    cancelled = cursor.fetchone()[0]

    ####################################################
    # MCP Progress 60%
    ####################################################

    await ctx.report_progress(
            progress=60,
            total=100
        )

    cursor.execute("""
        SELECT AVG(delay_minutes)
        FROM Flights
        WHERE status='Delayed'
    """)

    avg_delay = cursor.fetchone()[0]

    ####################################################
    # MCP Progress 90%
    ####################################################

    await ctx.report_progress(
        progress=90,
        total=100
    )

    cursor.execute("""
        SELECT COUNT(*)
        FROM Bookings b
        JOIN Flights f
        ON b.flight_id=f.flight_id
        WHERE
            f.status IN ('Delayed','Cancelled')
    """)

    affected = cursor.fetchone()[0]

    connection.close()

    ####################################################
    # MCP Progress 100%
    ####################################################

    await ctx.report_progress(
        progress=100,
        total=100
    )

    return {
        "delayed_flights": delayed,
        "cancelled_flights": cancelled,
        "average_delay": avg_delay,
        "affected_passengers": affected
    }