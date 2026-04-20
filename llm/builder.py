from llm.factory import create_llm
from llm.fallback_llm import FallbackLLM
from llm.router_llm import RouterLLM
from registry.llm import LLM_CATALOG, LLM_ROUTES

def _resolve_llm_config(llm_name: str) -> dict:
    if llm_name not in LLM_CATALOG:
        raise ValueError(f"Unknown LLM catalog entry: {llm_name}")
    return LLM_CATALOG[llm_name]


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
    chat_llm = _build_fallback_llm(
        route_config=LLM_ROUTES["chat"],
        system_instruction=system_instruction,
    )

    code_llm = _build_fallback_llm(
        route_config=LLM_ROUTES["code"],
        system_instruction=system_instruction,
    )

    return RouterLLM(chat_llm, code_llm)