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
aviation_dir = ROOT_DIR / "aviationstack-mcp"
aviation_python = aviation_dir / ".venv" / "Scripts" / "python.exe"
if not aviation_python.exists():
    aviation_python = aviation_dir / ".venv" / "bin" / "python"
if not aviation_python.exists():
    aviation_python = Path(python_exe)

client = MultiServerMCPClient(
    {
        'aviationstack': {
            'transport': 'stdio',
            'command': str(aviation_python),
            'args': [
                '-m',
                'aviationstack_mcp',
            ],
            'cwd': str(aviation_dir),
            'env': {
                'AVIATION_STACK_API_KEY': settings.AVIATIONSTACK_API_KEY
            }
        }
    }
)

async def main():
    tools = await client.get_tools()
    print("\nAvailable Aviationstack MCP Tools:")
    for tool in tools:
        print(f" - {tool.name}")

if __name__ == '__main__':
    asyncio.run(main())
