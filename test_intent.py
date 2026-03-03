import asyncio
from src.core.intent_analyzer import IntentAnalyzer
async def main():
    analyzer = IntentAnalyzer()
    res = await analyzer.analyze("Please fix this bug", [])
    print(res)
asyncio.run(main())
