import datetime
from pathlib import Path
from live2d.vts_client import VTSClient
from stt.stt_engine import STTEngine
from tts.voice_engine import VoiceEngine
from utils.security import SecurityManager
from llm.builder import build_llm
from plugins.manager import PluginManager
from plugins.builtin import ConsoleLoggerPlugin

LANGUAGE_NAMES = {
    "ja": "Japanese",
    "en": "English",
}

def create_log_file() -> Path:
    log_dir = Path("output")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%y%m%d_%H%M")
    return log_dir / f"log_{timestamp}.txt"

def print_system_status(use_stt: bool, use_tts: bool, vts, llm) -> None:
    input_mode = "Voice (STT)" if use_stt else "Keyboard (Text)"
    output_mode = "Voice (TTS)" if use_tts else "Text Only"
    live2d_mode = "Enabled" if vts is not None else "Disabled"

    print("\n--- System Active ---")
    print(f"Input Mode:  {input_mode}")
    print(f"Output Mode: {output_mode}")
    print(f"Live2D:      {live2d_mode}")
    print(f"LLM:         {llm.provider_name} / {llm.model_name}")

async def initialize_components(config) -> dict:
    SecurityManager.ensure_safe_environment()

    runtime = {}
    runtime["config"] = config
    use_stt = config.input_voice_enabled
    use_tts = config.output_voice_enabled

    base_system_prompt = config.system_prompt.strip()
    output_language_name = LANGUAGE_NAMES.get(
        config.output_language_code, "English"
    )

    language_instruction = (
        f"You MUST write your entire response in {output_language_name}. "
        f"All explanations, headings, bullet points, and sentences must be in "
        f"{output_language_name}. "
        f"You are NOT allowed to output any other language. "
        f"If you generate content in another language, you must immediately rewrite it in "
        f"{output_language_name}. "
        f"Keep only code, commands, file paths, URLs, and proper nouns unchanged."
    )

    if base_system_prompt:
        system_instruction = f"{language_instruction}\n\n{base_system_prompt}"
    else:
        system_instruction = language_instruction

    llm = build_llm(system_instruction)
        
    log_file = create_log_file()

    vts = None
    stt = STTEngine(language_code=config.input_language_code) if use_stt else None
    tts = None
    
    if use_tts:
        if config.tts_provider == "none":
            tts = None
        elif config.tts_provider in ("local", "elevenlabs"):
            tts = VoiceEngine(language_code=config.output_language_code)
        else:
            raise ValueError(f"Unsupported tts_provider: {config.tts_provider}")


    if config.vts_enabled:
        try:
            vts = VTSClient()
            connected = await vts.connect()
            if not connected:
                vts = None
        except Exception as e:
            print(f"[VTS] Disabled due to error: {e}")
            vts = None
    
    print("=== Runtime Config ===")
    print(f"Preset: {config.app_preset}")
    print(f"Character: {config.character_name}")
    print(f"Input Lang: {config.input_language_code}")
    print(f"Output Lang: {config.output_language_code}")
    print(f"Input Voice: {config.input_voice_enabled}")
    print(f"Output Voice: {config.output_voice_enabled}")
    print(f"VTS Enabled: {config.vts_enabled}")
    print(f"TTS Provider: {config.tts_provider}")
    print(f"Emotion Enabled: {config.emotion_enabled}")
    print(f"VTS Emotion Enabled: {config.vts_emotion_enabled}")
    print("======================")
    print(f"STT Lang:     {config.input_language_code}")
    print(f"TTS Lang:     {config.output_language_code}")
    print(f"LLM Output Lang: {config.output_language_code}")
    print("--- Final System Instruction ---")
    print(system_instruction)
    print("--------------------------------")
    print_system_status(use_stt, use_tts, vts, llm)

    runtime.update({
        "use_stt": use_stt,
        "use_tts": use_tts,
        "log_file": log_file,
        "llm": llm,
        "vts": vts,
        "stt": stt,
        "tts": tts,
        "hooks": {
            "on_user_input": [],
            "on_llm_chunk": [],
            "on_llm_complete": [],
            "on_error": [],
        },
    })

    plugin_manager = PluginManager()
    runtime["plugin_manager"] = plugin_manager

    plugin_manager.register(ConsoleLoggerPlugin(), runtime)
    plugin_manager.on_start(runtime)

    return runtime

async def shutdown_components(runtime: dict) -> None:
    vts = runtime.get("vts")
    if vts is not None:
        await vts.close()