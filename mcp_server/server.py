
from app import mcp

import tools.flight_tools
import tools.booking_tools
import tools.compensation_tools
import tools.report_tools
import resources ,sampling
if __name__ == "__main__":
    #mcp.run()
    mcp.run(transport="sse", host="127.0.0.1", port=8000)