import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient

from config import settings


client = MultiServerMCPClient(
    {
        'aviationstack':{
            'transport':'stdio',
            'command':r"D:\Multi_agent_with_MCP\aviationstack-mcp\.venv\Scripts\python.exe",
            'args':[
                '-m',
                'aviationstack_mcp',
            ],
            'cwd': r"D:\Multi_agent_with_MCP\aviationstack-mcp",
            'env':{
                'AVIATION_STACK_API_KEY':settings.AVIATIONSTACK_API_KEY
            }
        }
    }
)


async def main():
    tools =await client.get_tools()
    
    print("\n Available MCP Tools\n")
    for tool in tools:
        print(tool.name)


asyncio.run(main())

