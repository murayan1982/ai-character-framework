import datetime
from pathlib import Path

from config.settings import INPUT_VOICE_ENABLED, OUTPUT_VOICE_ENABLED
from live2d.vts_client import VTSClient
from stt.stt_engine import STTEngine
from tts.voice_engine import VoiceEngine
from utils.security import SecurityManager
from llm.builder import build_llm
from config.settings import ENABLE_VTS

def create_log_file() -> Path:
    log_dir = Path("output")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%y%m%d_%H%M")
    return log_dir / f"log_{timestamp}.txt"

def load_system_prompt() -> str:
    prompt_path = Path("prompts/system_base.txt")
    if not prompt_path.exists():
        raise FileNotFoundError("prompts/system_base.txt not found.")
    return prompt_path.read_text(encoding="utf-8")

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
    use_stt = INPUT_VOICE_ENABLED
    use_tts = OUTPUT_VOICE_ENABLED

    system_instruction = load_system_prompt()
    log_file = create_log_file()

    llm = build_llm(system_instruction)
    vts = None
    stt = STTEngine() if use_stt else None
    tts = VoiceEngine() if use_tts else None

    if ENABLE_VTS:
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
    print("======================")
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

    return runtime

async def shutdown_components(runtime: dict) -> None:
    vts = runtime.get("vts")
    if vts is not None:
        await vts.close()