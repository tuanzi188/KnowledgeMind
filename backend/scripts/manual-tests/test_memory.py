import sys
sys.path.insert(0, "backend")
import asyncio
from app.services.conversation_memory import conversation_memory as mem

async def test():
    cid = "test-conv-123"

    await mem.add_turn(cid, "Hello, my name is Xiaoming", "Nice to meet you Xiaoming!")

    history = await mem.get_history(cid, 5)
    print("History entries:", len(history))
    print("History:", history)

    prompt = await mem.format_history_for_prompt(cid, 5)
    print("Formatted prompt:", repr(prompt))

    await mem.add_turn(cid, "What is my name?", "Your name is Xiaoming!")

    history2 = await mem.get_history(cid, 5)
    print("\nAfter 2 turns - History entries:", len(history2))
    for h in history2:
        print(f"  {h['role']}: {h['content']}")

    await mem.clear(cid)
    history3 = await mem.get_history(cid, 5)
    print("\nAfter clear - History entries:", len(history3))

    print("\nAll tests PASSED!")

asyncio.run(test())