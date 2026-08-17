
from mcp_server.app import mcp
import mcp_server.tools.flight_tools
import mcp_server.tools.booking_tools
import mcp_server.tools.compensation_tools
import mcp_server.tools.report_tools
import mcp_server.resources
import mcp_server.sampling 

if __name__ == "__main__":
    mcp.run()