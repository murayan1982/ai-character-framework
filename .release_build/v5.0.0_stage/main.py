import asyncio
from core.runtime import initialize_components, shutdown_components
from core.session import ChatSession
from config.loader import load_runtime_config


async def main():
    runtime = None
    try:
        config = load_runtime_config()

        print("[Config] Loaded in main.py")
        print(config)

        runtime = await initialize_components(config)

        session = ChatSession(runtime)
        await session.run()

    except Exception as e:
        print(f"\n[Fatal Error] {e}")
    finally:
        if runtime:
            try:
                await shutdown_components(runtime)
            except Exception as e:
                print(f"[Cleanup Error] {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")