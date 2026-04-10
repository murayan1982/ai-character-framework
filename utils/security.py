import os
import speech_recognition as sr

class SecurityManager:
    """Class to ensure the safety and environment setup of the project."""
    @staticmethod
    def ensure_safe_environment():
        # 1. Create necessary directories
        os.makedirs("config/tokens", exist_ok=True)
        
        # 2. Check and update .gitignore for security
        ignore_content = "\n# VTube Studio Tokens\n**/tokens/*.json\n"
        if not os.path.exists(".gitignore"):
            with open(".gitignore", "w") as f:
                f.write(ignore_content)
        else:
            with open(".gitignore", "r") as f:
                if "**/tokens/*.json" not in f.read():
                    with open(".gitignore", "a") as f:
                        f.write(ignore_content)

class STTEngine:
    """Class handled for voice input (STT)."""
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

    async def listen(self):
        # Display status without cluttering the VSCode terminal
        print("\r[Status] Listening...", end="", flush=True)
        
        with self.microphone as source:
            # Adjust for ambient noise
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = self.recognizer.listen(source)

        try:
            print("\r[Status] Recognizing...", end="", flush=True)
            # Recognize speech using Google Web Speech API (default: ja-JP)
            text = self.recognizer.recognize_google(audio, language="ja-JP")
            print(f"\rUser (Voice): {text}")
            return text
        except Exception:
            return None