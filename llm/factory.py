from llm.gemini_engine import GeminiEngine
from llm.grok_engine import GrokEngine
from config.settings import LLM_PROVIDER

def create_llm(system_instruction: str):
    if LLM_PROVIDER == "google":
        return GeminiEngine(system_instruction)
    elif LLM_PROVIDER == "xai":
        return GrokEngine(system_instruction)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")