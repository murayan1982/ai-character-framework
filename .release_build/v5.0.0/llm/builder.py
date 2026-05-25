from llm.factory import create_llm, get_supported_llm_providers
from llm.fallback_llm import FallbackLLM
from llm.router_llm import RouterLLM
from registry.llm import LLM_CATALOG, LLM_ROUTES


def _resolve_llm_config(llm_name: str) -> dict:
    if llm_name not in LLM_CATALOG:
        raise ValueError(f"Unknown LLM catalog entry: {llm_name}")
    return LLM_CATALOG[llm_name]


def validate_llm_registry() -> None:
    """
    Validate static LLM registry definitions without creating provider clients.

    This check intentionally does not validate API keys or perform network calls.
    Runtime secrets are validated only when a provider is instantiated.
    """
    supported_providers = get_supported_llm_providers()

    if not isinstance(LLM_CATALOG, dict):
        raise TypeError("LLM_CATALOG must be a dict.")

    if not isinstance(LLM_ROUTES, dict):
        raise TypeError("LLM_ROUTES must be a dict.")

    for llm_name, llm_config in LLM_CATALOG.items():
        if not isinstance(llm_name, str) or not llm_name:
            raise ValueError(f"LLM catalog entry name must be a non-empty string: {llm_name!r}")

        if not isinstance(llm_config, dict):
            raise TypeError(f"LLM catalog entry '{llm_name}' must be a dict.")

        provider = llm_config.get("provider")
        model = llm_config.get("model")

        if not isinstance(provider, str) or not provider:
            raise ValueError(f"LLM catalog entry '{llm_name}' must define a non-empty provider.")

        if not isinstance(model, str) or not model:
            raise ValueError(f"LLM catalog entry '{llm_name}' must define a non-empty model.")

        if provider not in supported_providers:
            raise ValueError(
                f"LLM catalog entry '{llm_name}' uses unsupported provider "
                f"'{provider}'. Supported providers: {sorted(supported_providers)}"
            )

    for route_name, route_config in LLM_ROUTES.items():
        if not isinstance(route_name, str) or not route_name:
            raise ValueError(f"LLM route name must be a non-empty string: {route_name!r}")

        if not isinstance(route_config, dict):
            raise TypeError(f"LLM route '{route_name}' must be a dict.")

        primary_name = route_config.get("primary")
        fallback_name = route_config.get("fallback")

        if not isinstance(primary_name, str) or not primary_name:
            raise ValueError(f"LLM route '{route_name}' must define a non-empty primary.")

        if not isinstance(fallback_name, str) or not fallback_name:
            raise ValueError(f"LLM route '{route_name}' must define a non-empty fallback.")

        if primary_name not in LLM_CATALOG:
            raise ValueError(
                f"LLM route '{route_name}' has unknown primary '{primary_name}'. "
                f"Known catalog entries: {sorted(LLM_CATALOG.keys())}"
            )

        if fallback_name not in LLM_CATALOG:
            raise ValueError(
                f"LLM route '{route_name}' has unknown fallback '{fallback_name}'. "
                f"Known catalog entries: {sorted(LLM_CATALOG.keys())}"
            )


def _build_single_llm(llm_name: str, system_instruction: str):
    llm_config = _resolve_llm_config(llm_name)

    return create_llm(
        provider=llm_config["provider"],
        model=llm_config["model"],
        system_instruction=system_instruction,
    )


def _build_fallback_llm(route_config: dict, system_instruction: str):
    primary_name = route_config["primary"]
    fallback_name = route_config["fallback"]

    primary = _build_single_llm(
        llm_name=primary_name,
        system_instruction=system_instruction,
    )

    fallback = _build_single_llm(
        llm_name=fallback_name,
        system_instruction=system_instruction,
    )

    return FallbackLLM(primary, fallback)


def build_llm(system_instruction: str):
    validate_llm_registry()

    chat_llm = _build_fallback_llm(
        route_config=LLM_ROUTES["chat"],
        system_instruction=system_instruction,
    )

    code_llm = _build_fallback_llm(
        route_config=LLM_ROUTES["code"],
        system_instruction=system_instruction,
    )

    return RouterLLM(chat_llm, code_llm)