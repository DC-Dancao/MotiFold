import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

async def test_pure_http_stream():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = "http://host.docker.internal:8317/v1"
            
    url = f"{base_url}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": os.getenv("OPENAI_MODEL_PRO", "gpt-4o"),
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": "Generate the final blackboard blocks for: 鱼香肉丝的做法"
            }
        ],
        "stream": True
    }
    
    print(f"Calling {url} with model {payload['model']} and stream=True...")
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, headers=headers, json=payload, timeout=60.0) as response:
            print(f"Status: {response.status_code}")
            async for chunk in response.aiter_text():
                print(chunk, end="")

if __name__ == "__main__":
    asyncio.run(test_pure_http_stream())
