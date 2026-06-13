import asyncio
import httpx
from mcp.client.streamable_http import streamable_http_client
from mcp.client.session import ClientSession
import traceback

async def main():
    url = "https://mcp.consensus.app/mcp"
    print(f"Connecting to {url}...")
    try:
        async with httpx.AsyncClient() as http_client:
            async with streamable_http_client(url, http_client=http_client) as streams:
                print("Streamable HTTP connection established.")
                read_stream, write_stream = streams[0], streams[1]
                async with ClientSession(read_stream, write_stream) as session:
                    print("Initializing MCP session...")
                    init_result = await session.initialize()
                    print(f"Initialized server: {init_result.serverInfo.name} v{init_result.serverInfo.version}")
                    
                    print("Calling 'search' tool with query='machine learning'...")
                    result = await session.call_tool("search", arguments={"query": "machine learning"})
                    if result.content:
                        content_type = type(result.content[0]).__name__
                        print(f"Response content type: {content_type}")
                        if content_type == 'TextContent':
                            import json
                            raw = json.loads(result.content[0].text)
                            print(f"Total results: {raw.get('total_results', 'N/A')}")
                            papers = raw.get('papers', [])
                            print(f"Returned papers count: {len(papers)}")
                            if papers:
                                print(f"First paper keys: {list(papers[0].keys())}")
                                print(f"First paper title: {papers[0].get('title')}")
                    else:
                        print("No content returned.")
    except Exception as e:
        print(f"Spike failed with exception:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
