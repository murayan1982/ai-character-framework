# tts/voice_engine.py
import os
import subprocess
import threading
import time
import queue
import re
from pathlib import Path
from elevenlabs.client import ElevenLabs
from config.settings import (
    ELEVENLABS_API_KEY,
    VOICE_ID,
    TTS_MODEL_ID,
    require_tts_settings,
)
from config.calibration import (
    VOICE_STABILITY, SIMILARITY_BOOST, VOICE_STYLE, 
    VOICE_SPEED, POST_SPEECH_PAUSE
)

class VoiceEngine:
    """
    ElevenLabs-backed queued TTS playback engine.

    Public boundary used by the runtime pipeline:
    - speak(text): append streaming text and enqueue speakable segments.
    - flush(): enqueue any remaining buffered text at the end of a turn.
    - is_speaking_active: report whether queued or active playback remains.
    - stop(): best-effort stop for queued or active playback.
    - stop_immediately(): local playback cancellation implementation.

    This class currently owns provider-specific TTS generation and local audio
    playback. Provider abstraction and interruption behavior are intentionally
    handled as future runtime milestones.
    """
    def __init__(self, language_code: str = "ja"):
        require_tts_settings()
        self.client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        self.voice_id = VOICE_ID
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
        self.msg_queue = queue.Queue()
        self.is_speaking = False
        self.current_process = None
        self.text_buffer = ""
        self.language_code = language_code
        self.worker_thread = threading.Thread(target=self._queue_worker, daemon=True)
        self.worker_thread.start()

    def speak(self, text: str) -> None:
        """
        Append streaming text and enqueue any complete speakable segments.

        This method is called repeatedly while the LLM stream is being consumed.
        It does not force the remaining buffer to be spoken; call flush() at the
        end of the assistant turn for that.
        """
        if not text:
            return

        self.text_buffer += text

        while True:
            segment = self._extract_speakable_segment(force=False)
            if not segment:
                break
            self._enqueue_segment(segment)

    def flush(self) -> None:
        """
        Enqueue all remaining buffered text for playback.

        The pipeline calls this after the LLM stream ends so the final partial
        sentence is not left in the buffer.
        """
        while True:
            segment = self._extract_speakable_segment(force=False)
            if not segment:
                break
            self._enqueue_segment(segment)

        tail = self._extract_speakable_segment(force=True)
        if tail:
            self._enqueue_segment(tail)

    @property
    def is_speaking_active(self) -> bool:
        """Return True while playback is active or queued audio remains."""
        return self.is_speaking or not self.msg_queue.empty()

    def stop(self) -> None:
        """
        Best-effort stop for queued or active TTS playback.

        This method is the framework-level interruption boundary. It delegates
        to the current local playback cancellation behavior and is safe to call
        even when nothing is playing.
        """
        self.stop_immediately()

    def stop_immediately(self) -> None:
        """
        Stop current playback and clear queued segments.

        This is the current local playback cancellation implementation used by
        the framework-level stop() boundary.
        """
        if self.current_process:
            self.current_process.kill()
            self.current_process = None

        self.text_buffer = ""

        while not self.msg_queue.empty():
            try:
                self.msg_queue.get_nowait()
                self.msg_queue.task_done()
            except queue.Empty:
                break

    def _queue_worker(self) -> None:
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
                        if chunk:
                            f.write(chunk)

                # Play audio via ffplay
                self.current_process = subprocess.Popen([
                    "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                    "-af", f"atempo={VOICE_SPEED}", str(file_path)
                ])
                self.current_process.wait()

                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                print(f"\n[TTS Warning] Playback failed. Continuing without this audio chunk. ({e})")
            finally:
                self.is_speaking = False
                self.msg_queue.task_done()

    def _extract_speakable_segment(self, force: bool = False) -> str:
        """
        Return one speakable segment from the pending text buffer.

        Rules:
        - prefer splitting on strong punctuation
        - allow weak punctuation splits only after some minimum length
        - when force=True, flush the entire remaining buffer
        """
        text = self.text_buffer.strip()
        if not text:
            self.text_buffer = ""
            return ""

        if force:
            self.text_buffer = ""
            return text

        strong_breaks = "。！？.!?\n"
        weak_breaks = "、,;:"

        min_len_for_weak_break = 18
        min_len_without_break = 40

        for i, ch in enumerate(text):
            if ch in strong_breaks:
                segment = text[: i + 1].strip()
                rest = text[i + 1 :].lstrip()
                self.text_buffer = rest
                return segment

        for i, ch in enumerate(text):
            if ch in weak_breaks and i + 1 >= min_len_for_weak_break:
                segment = text[: i + 1].strip()
                rest = text[i + 1 :].lstrip()
                self.text_buffer = rest
                return segment

        if len(text) >= min_len_without_break:
            split_at = text.rfind(" ", 0, min_len_without_break)
            if split_at <= 0:
                split_at = min_len_without_break

            segment = text[:split_at].strip()
            rest = text[split_at:].lstrip()
            self.text_buffer = rest
            return segment

        return ""

    def _enqueue_segment(self, text: str) -> None:
        """Queue one normalized text segment for TTS playback."""
        cleaned = (text or "").strip()
        if not cleaned:
            return
        self.msg_queue.put(cleaned)