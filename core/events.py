from collections.abc import Callable
import inspect
import asyncio


async def emit_hooks(hooks: list[Callable], *args, **kwargs) -> None:
    for hook in hooks:
        try:
            result = hook(*args, **kwargs)
            if inspect.isawaitable(result):
                await result
        except Exception as e:
            print(f"[Hook Error] {e}")


async def emit(runtime: dict, event_name: str, *args, **kwargs) -> None:
    hooks = runtime.get("hooks", {}).get(event_name, [])
    await emit_hooks(hooks, *args, **kwargs)