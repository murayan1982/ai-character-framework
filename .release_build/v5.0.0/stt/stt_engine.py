import speech_recognition as sr
import asyncio


class STTEngine:
    """
    Google Speech Recognition-backed STT engine.

    Public boundary used by the runtime pipeline:
    - listen(): capture one voice input turn and return recognized text.

    This class currently owns:
    - microphone access
    - ambient noise adjustment
    - speech_recognition provider call
    - STT timeout/error handling

    The runtime pipeline should only depend on listen().
    Provider abstraction is intentionally deferred to a future milestone.
    """

    def __init__(self, language_code: str = "ja"):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.language_code = language_code

        # Sensitivity adjustment for silence
        self.recognizer.pause_threshold = 1.0

    async def listen(self) -> str:
        """
        Capture and recognize one voice input turn.

        Returns:
            Recognized text, or an empty string when no usable input is available.

        This method should not raise provider/runtime STT failures to the
        session loop during normal recognition errors.
        """
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

            try:
                audio = await asyncio.to_thread(
                    self.recognizer.listen,
                    source,
                    timeout=5,
                    phrase_time_limit=8,
                )

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
                return ""
            except (sr.WaitTimeoutError, sr.UnknownValueError):
                return ""
            except Exception as e:
                print(f"\n[STT Error]: {type(e).__name__}: {e}")
                return ""

        return ""