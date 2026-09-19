import sys
from pathlib import Path
import asyncio

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langchain_mcp_adapters.client import MultiServerMCPClient
from config import settings

python_exe = sys.executable
openweather_script = ROOT_DIR / "mcp_servers" / "openweather_mcp_server.py"

client = MultiServerMCPClient(
    {
        'weather': {
            'transport': 'stdio',
            'command': str(python_exe),
            'args': [str(openweather_script)],
            'cwd': str(ROOT_DIR),
            'env': {
                'OPENWEATHER_API_KEY': settings.OPENWEATHER_API_KEY
            }
        }
    }
)

async def main():
    print("Loading OpenWeather tools...")
    tools = await client.get_tools()
    print("\nAvailable Weather MCP Tools:")
    for tool in tools:
        print(f" - {tool.name}")

if __name__ == '__main__':
    asyncio.run(main())