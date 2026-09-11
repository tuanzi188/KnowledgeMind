from openai import AsyncOpenAI
from app.config import DEEPSEEK_CONFIG

api_key = DEEPSEEK_CONFIG["primary"]["api_key"]
base_url = DEEPSEEK_CONFIG["primary"]["base_url"]

print(f"api_key: {api_key[:10]}...")
print(f"base_url: {base_url}")

client = AsyncOpenAI(api_key=api_key, base_url=base_url)

import asyncio
async def test():
    r = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role":"user", "content":"Hi"}],
        max_tokens=50
    )
    print("OK:", r.choices[0].message.content)

asyncio.run(test())