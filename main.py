import asyncio

from core.runtime import initialize_components, shutdown_components
from core.session import ChatSession

async def main():
    runtime = None
    try:
        runtime = await initialize_components()

        session = ChatSession(runtime)
        await session.run()

    except KeyboardInterrupt:
        print("\nSystem shutting down...")
    except Exception as e:
        print(f"\n[Fatal Error] {e}")
    finally:
        if runtime:
            try:
                await shutdown_components(runtime)
            except Exception as e:
                print(f"[Cleanup Error] {e}")

if __name__ == "__main__":
    asyncio.run(main())