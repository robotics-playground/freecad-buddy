"""Call one MCP tool on the container proxy: mcp1.py <tool> '<json args>'; prints the result JSON."""
import json, sys
sys.path.insert(0, r"D:\Work\Personal\Sources\fcb-verify-13-5\tests\uat\runner")
from mcp_client import McpClient

with McpClient("http://127.0.0.1:18765/mcp") as c:
    print(json.dumps(c.call(sys.argv[1], json.loads(sys.argv[2])), default=str))
