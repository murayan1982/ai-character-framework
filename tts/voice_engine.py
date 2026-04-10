# tts/voice_engine.py
import os
import subprocess
import threading
import time
import queue
import re
from pathlib import Path
from elevenlabs.client import ElevenLabs
from config.settings import ELEVENLABS_API_KEY, VOICE_ID, TTS_MODEL_ID
from config.calibration import (
    VOICE_STABILITY, SIMILARITY_BOOST, VOICE_STYLE, 
    VOICE_SPEED, POST_SPEECH_PAUSE
)

class VoiceEngine:
    def __init__(self):
        self.client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        self.voice_id = VOICE_ID
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
        self.msg_queue = queue.Queue()
        self.is_speaking = False
        self.current_process = None
        self.text_buffer = ""

        self.worker_thread = threading.Thread(target=self._queue_worker, daemon=True)
        self.worker_thread.start()

    def speak(self, partial_text: str):
        self.text_buffer += partial_text
        
        # Buffer logic: Send to queue if punctuation exists and length > 25, or if newline occurs
        if re.search(r'([。！？\n])', self.text_buffer):
            if len(self.text_buffer) > 25 or "\n" in self.text_buffer:
                sentences = re.split(r'([。！？\n])', self.text_buffer)
                # Combine sentence with its punctuation
                for i in range(0, len(sentences)-1, 2):
                    full_sent = sentences[i] + sentences[i+1]
                    if full_sent.strip():
                        self.msg_queue.put(full_sent.strip())
                self.text_buffer = sentences[-1]

    def flush(self):
        """Force send remaining buffer to the queue"""
        if self.text_buffer.strip():
            self.msg_queue.put(self.text_buffer.strip())
            self.text_buffer = ""

    @property
    def is_speaking_active(self):
        """Returns True if processing audio or queue is not empty"""
        return self.is_speaking or not self.msg_queue.empty()

    def stop_immediately(self):
        """Kill the current playback process and clear the queue"""
        if self.current_process:
            self.current_process.kill()
        while not self.msg_queue.empty():
            try:
                self.msg_queue.get_nowait()
                self.msg_queue.task_done()
            except queue.Empty:
                break

    def _queue_worker(self):
        while True:
            text = self.msg_queue.get()
            self.is_speaking = True
            try:
                file_path = self.temp_dir / f"v_{int(time.time()*1000)}.mp3"
                # ElevenLabs API Call
                audio = self.client.text_to_speech.convert(
                    voice_id=self.voice_id,
                    text=text,
                    model_id=TTS_MODEL_ID,
                    voice_settings={
                        "stability": VOICE_STABILITY,
                        "similarity_boost": SIMILARITY_BOOST,
                        "style": VOICE_STYLE,
                        "use_speaker_boost": True
                    }
                )
                with open(file_path, "wb") as f:
                    for chunk in audio:
                        if chunk: f.write(chunk)

                # Play audio via ffplay
                self.current_process = subprocess.Popen([
                    "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                    "-af", f"atempo={VOICE_SPEED}", str(file_path)
                ])
                self.current_process.wait()

                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                print(f"\n[TTS Error]: {str(e)}")
            finally:
                self.is_speaking = False
                self.msg_queue.task_done()