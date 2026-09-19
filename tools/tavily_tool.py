from tavily import TavilyClient
from config import settings


client = TavilyClient(
    api_key =settings.TAVILY_API_KEY
)

def tavily_search(query: str):
    response = client.search(
        query=query,
        max_results=5
    )

    results = []

    for result in response.get("results", []):
        results.append({
            "title": result.get("title", "Unknown"),
            "url": result.get("url", ""),
            "content": result.get("content", "").strip(),
        })

    return results