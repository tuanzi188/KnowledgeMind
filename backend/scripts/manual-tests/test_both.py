from openai import AsyncOpenAI
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("DS_API_KEY")
base_url = os.getenv("DS_BASE_URL", "https://api.deepseek.com/v1")

client = AsyncOpenAI(api_key=api_key, base_url=base_url)

async def test_embedding():
    print("Testing chat...")
    chat_r = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role":"user", "content":"Hi"}],
        max_tokens=50
    )
    print("Chat OK:", chat_r.choices[0].message.content)

    print("\nTesting embedding...")
    try:
        embed_r = await client.embeddings.create(
            model="deepseek-embedding",
            input="test"
        )
        print(f"Embedding OK, dimension: {len(embed_r.data[0].embedding)}")
    except Exception as e:
        print(f"Embedding ERROR: {e}")
        print("\nTrying 'text-embedding-ada-002'...")
        try:
            embed_r2 = await client.embeddings.create(
                model="text-embedding-ada-002",
                input="test"
            )
            print(f"Embedding OK (text-embedding-ada-002), dimension: {len(embed_r2.data[0].embedding)}")
        except Exception as e2:
            print(f"Still error: {e2}")

asyncio.run(test_embedding())