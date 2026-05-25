LLM_PROVIDER_MODULES = {
    "google": ("llm.gemini_engine", "GeminiEngine"),
    "xai": ("llm.grok_engine", "GrokEngine"),
    "openai": ("llm.openai_engine", "OpenAIEngine"),
}


def get_supported_llm_providers() -> set[str]:
    return set(LLM_PROVIDER_MODULES.keys())


def _load_engine_class(provider: str):
    provider_config = LLM_PROVIDER_MODULES.get(provider)
    if provider_config is None:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported providers: {sorted(get_supported_llm_providers())}"
        )

    module_name, class_name = provider_config

    try:
        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name)
    except ImportError as e:
        raise ImportError(
            f"Failed to import LLM provider '{provider}' from {module_name}."
        ) from e
    except AttributeError as e:
        raise ImportError(
            f"LLM provider class '{class_name}' was not found in {module_name}."
        ) from e


def create_llm(provider: str, system_instruction: str, model: str):
    engine_cls = _load_engine_class(provider)

    return engine_cls(
        system_instruction=system_instruction,
        model=model,
    )