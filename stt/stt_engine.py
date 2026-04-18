import speech_recognition as sr
import asyncio


class STTEngine:
    def __init__(self, language_code: str = "ja"):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.language_code = language_code

        # Sensitivity adjustment for silence
        self.recognizer.pause_threshold = 1.0

    async def listen(self):
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

            print("\r[STT Waiting...] ", end="", flush=True)
            try:
                audio = await asyncio.to_thread(
                    self.recognizer.listen,
                    source,
                    timeout=5,
                    phrase_time_limit=8,
                )

                print("\r[STT] Recognizing...          ", end="", flush=True)

                text = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.recognizer.recognize_google,
                        audio,
                        language=self.language_code,
                    ),
                    timeout=7.0,
                )

                if text:
                    print(f"\nUser (Voice): {text}")
                    return text

            except asyncio.TimeoutError:
                print("\r[STT] Recognition timed out.       ", end="", flush=True)
                return ""
            except (sr.WaitTimeoutError, sr.UnknownValueError):
                return ""
            except Exception as e:
                print(f"\n[STT Error]: {type(e).__name__}: {e}")
                return ""

        return ""