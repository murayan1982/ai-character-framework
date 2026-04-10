# main.py

import sys
import datetime
import re
import asyncio
from pathlib import Path

# --- User-defined Modules ---
from llm.gemini_engine import GeminiEngine
from tts.voice_engine import VoiceEngine
from live2d.vts_client import VTSClient
from utils.security import SecurityManager
from stt.stt_engine import STTEngine
from config.settings import INPUT_VOICE_ENABLED, OUTPUT_VOICE_ENABLED 

# Async helper for keyboard input to prevent blocking
async def ainput(prompt: str = ""):
    return await asyncio.to_thread(input, prompt)

async def main():
    # 1. Initialize environment (directories, .gitignore)
    SecurityManager.ensure_safe_environment()

    # 2. Log file setup
    log_dir = Path("output")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"log_{datetime.datetime.now().strftime('%y%m%d_%H%M')}.txt"
    
    # Load flags from settings.py
    use_stt = INPUT_VOICE_ENABLED
    use_tts = OUTPUT_VOICE_ENABLED

    # 3. Load system prompt from text file
    try:
        with open("prompts/system_base.txt", "r", encoding="utf-8") as f:
            system_instruction = f.read()
    except FileNotFoundError:
        print("Error: prompts/system_base.txt not found.")
        return

    # 4. Initialize Core Components
    llm = GeminiEngine(system_instruction)
    vts = VTSClient()
    stt = STTEngine() if use_stt else None
    tts = VoiceEngine() if use_tts else None
    
    await vts.connect()

    print(f"\n--- System Active ---")
    print(f"Input Mode:  {'Voice (STT)' if use_stt else 'Keyboard (Text)'}")
    print(f"Output Mode: {'Voice (TTS)' if use_tts else 'Text Only'}")
    
    # Cleaner for terminal control sequences
    ansi_cleaner = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')

    while True:
        try:
            user_input = ""

            # --- INPUT PHASE ---
            if use_stt:
                # Hybrid input: Listen for both Voice and Keyboard
                stt_task = asyncio.create_task(stt.listen())
                kb_task = asyncio.create_task(ainput("\n[Keyboard or Speak]: "))
                
                done, pending = await asyncio.wait(
                    [stt_task, kb_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in done:
                    result = task.result()
                    if result:
                        user_input = str(result).strip()
                
                # Cancel the remaining task (e.g., stop listening if typed)
                for task in pending:
                    task.cancel()
            else:
                # Standard text input
                user_input = await ainput("\nUser: ")
                user_input = user_input.strip()

            if not user_input: 
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("System shutting down...")
                break

            # --- LLM & RESPONSE PHASE ---
            print(f"\n  AI: ", end="", flush=True)
            full_log_text = ""
            start_ts = datetime.datetime.now().strftime("%H:%M:%S")

            # Stream processing for real-time interaction
            for clean_chunk, emotions in llm.ask_stream(user_input):
                # Apply Live2D expressions
                if emotions:
                    full_log_text += "".join([f"[{e}]" for e in emotions])
                    for emotion in emotions:
                        asyncio.create_task(vts.change_expression(emotion))
                
                # Output text and voice
                if clean_chunk:
                    display_text = ansi_cleaner.sub('', clean_chunk)
                    if display_text:
                        print(display_text, end="", flush=True)
                        full_log_text += display_text
                        if use_tts:
                            tts.speak(display_text)
            
            print() # End of response line

            # --- POST-RESPONSE PHASE ---
            if use_tts:
                tts.flush()
                # Wait until audio playback is finished
                while tts.is_speaking_active:
                    await asyncio.sleep(0.1)
            
            # Save interaction to log file
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{start_ts}] User: {user_input}\n[{start_ts}] AI: {full_log_text}\n\n")

        except KeyboardInterrupt: 
            break
        except Exception as e: 
            print(f"\n[Main Error]: {e}")
            await asyncio.sleep(1)
            continue
    
    await vts.close()

if __name__ == "__main__":
    asyncio.run(main())