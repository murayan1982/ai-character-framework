from llm.gemini_engine import GeminiEngine
from llm.grok_engine import GrokEngine

LLM_REGISTRY = {
    "google": GeminiEngine,
    "xai": GrokEngine,
}

def create_llm(provider: str, system_instruction: str, model: str):
    engine_cls = LLM_REGISTRY.get(provider)
    if engine_cls is None:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    return engine_cls(
        system_instruction=system_instruction,
        model=model,
    )