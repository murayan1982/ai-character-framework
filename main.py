# main.py

import sys
import datetime
import re
import asyncio
from pathlib import Path
from llm.gemini_engine import GeminiEngine
from tts.voice_engine import VoiceEngine
from live2d.vts_client import VTSClient
from utils.security import SecurityManager
from stt.stt_engine import STTEngine

# Async helper for keyboard input
async def ainput(prompt: str = ""):
    return await asyncio.to_thread(input, prompt)

async def main():
    SecurityManager.ensure_safe_environment()

    # Log file setup
    log_dir = Path("output")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"log_{datetime.datetime.now().strftime('%y%m%d_%H%M')}.txt"
    
    is_voice_mode = "--voice" in sys.argv

    # Load system prompt
    try:
        with open("prompts/system_base.txt", "r", encoding="utf-8") as f:
            system_instruction = f.read()
    except FileNotFoundError:
        print("Error: prompts/system_base.txt not found.")
        return

    # Initialize components
    llm = GeminiEngine(system_instruction)
    tts = VoiceEngine() if is_voice_mode else None
    stt = STTEngine() if is_voice_mode else None
    vts = VTSClient()
    await vts.connect()

    print(f"\n--- System Active: {'Voice' if is_voice_mode else 'Text'} Mode ---")
    
    # ANSI sequence cleaner for logging/display
    ansi_cleaner = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')

    while True:
        try:
            # Stop AI speaking if user starts input
            if is_voice_mode and tts and tts.is_speaking_active:
                tts.stop_immediately()

            user_input = ""

            if is_voice_mode:
                stt_task = asyncio.create_task(stt.listen())
                kb_task = asyncio.create_task(ainput("\n[Keyboard Input or Speak]: "))

                done,pending = await asyncio.wait(
                    [stt_task,kb_task],
                    return_when = asyncio.FIRST_COMPLETED
                )

                for task in done:
                    result = task.result()
                    if result:
                        user_input = str(result).strip()

            else:
                user_input = await ainput("\nUser: ")
                user_input = user_input.strip()

            if not user_input: 
                continue
            if not user_input.strip():
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("System shutting down...")
                break

            print(f"\n  AI: ", end="", flush=True)
            full_log_text = ""
            start_ts = datetime.datetime.now().strftime("%H:%M:%S")

            # Process response stream
            for clean_chunk, emotions in llm.ask_stream(user_input):
                # Apply expressions to Live2D
                if emotions:
                    full_log_text += "".join([f"[{e}]" for e in emotions])
                    for emotion in emotions:
                        asyncio.create_task(vts.change_expression(emotion))
                
                # Print and speak clean text
                if clean_chunk:
                    display_text = ansi_cleaner.sub('', clean_chunk)
                    if display_text:
                        print(display_text, end="", flush=True)
                        full_log_text += display_text
                        if is_voice_mode and tts:
                            tts.speak(display_text)
            
            print() # New line after stream ends

            # Finalize speech
            if is_voice_mode and tts:
                tts.flush()
                while tts.is_speaking_active:
                    await asyncio.sleep(0.1)
            
            # Save history to log
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{start_ts}] User: {user_input}\n[{start_ts}] AI: {full_log_text}\n\n")

        except KeyboardInterrupt: break
        except Exception as e: 
            print(f"\n[Main Error]: {e}")
            await asyncio.sleep(1)
            continue
    
    await vts.close()

if __name__ == "__main__":
    asyncio.run(main())