# stt/stt_engine.py

import speech_recognition as sr
import asyncio

class STTEngine:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        # Sensitivity adjustment for silence
        self.recognizer.pause_threshold = 1.0 

    async def listen(self):
        """Capture audio from microphone and convert to text"""
        with self.microphone as source:
            # Calibrate for ambient noise
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            
            print("\r[STT/Text Waiting...] ", end="", flush=True)
            try:
                # Capture voice data asynchronously
                audio = await asyncio.to_thread(
                    self.recognizer.listen, 
                    source, 
                    timeout=10,
                    phrase_time_limit=8
                    )
                
                print("\r[STT] Recognizing...          ", end="", flush=True)
                # Google Web Speech API Recognition
                text = await asyncio.to_thread(
                    self.recognizer.recognize_google, audio, language="ja-JP"
                )
                if text:
                    # Move to next line after successful recognition to keep history
                    print(f"\nUser (Voice): {text}")
                    return text
            
            except (sr.WaitTimeoutError, sr.UnknownValueError):  
                  return ""
            except sr.WaitTimeoutError:
                return ""
            except sr.UnknownValueError:
                return ""
            except Exception as e:
                print(f"\n[STT Error]: {e}")
                return ""
            except Exception:
                return None
        return ""