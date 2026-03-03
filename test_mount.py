import asyncio

from src.tui.panels.chat import ChatPanel


async def main():
    try:
        p = ChatPanel()
        for x in p.compose():
            pass
        print("Compose Success")
    except Exception:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
