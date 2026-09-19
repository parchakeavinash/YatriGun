
from config import settings

import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient


client = MultiServerMCPClient(
    {
        'weather':{
            'transport':'stdio',
            'command':r"D:\Multi_agent_with_MCP\.venv\Scripts\python.exe",
            'args':[r"D:\Multi_agent_with_MCP\openweather_mcp_server.py"],
            'env':{
                'OPENWEATHER_API_KEY':settings.OPENWEATHER_API_KEY
            }
        }
    }
)

async def main():
    print("loading tools....")
    tools = await client.get_tools()

    print("Available MCP Tools \n")
    for tool in tools:
        print(tool.name)

if __name__ == '__main__':
    asyncio.run(main())