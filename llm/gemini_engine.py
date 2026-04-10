# llm/gemini_engine.py

from google import genai
import re
from typing import Generator, Tuple, List
from config.calibration import MAX_TOKENS_NORMAL, LLM_TEMPERATURE
from config.settings import ACTIVE_LLM_MODEL, GOOGLE_API_KEY, TARGET_LANGUAGE

class GeminiEngine:
    def __init__(self, system_instruction: str):
        if not GOOGLE_API_KEY:
            raise EnvironmentError("GOOGLE_API_KEY is not defined.")
        localized_instruction = f"{system_instruction}\n\n[IMPORTANT]\nPlease always respond in {TARGET_LANGUAGE}."
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = ACTIVE_LLM_MODEL
        self.turn_count = 0
        self.current_mood = "Normal"
        self.base_instruction = localized_instruction

        # Start initial chat session
        self._start_new_session()

    def _start_new_session(self):
        """Start a fresh chat session with the base instruction"""
        self.chat = self.client.chats.create(
            model=self.model_id,
            config={
                'system_instruction': self.base_instruction,
                'temperature': LLM_TEMPERATURE,
                'max_output_tokens': MAX_TOKENS_NORMAL,
            }
        )

    def ask_stream(self, text: str) -> Generator[Tuple[str, List[str]], None, None]:
        self.turn_count += 1
        
        # Reset history every 10 turns to keep performance and save tokens
        if self.turn_count > 10:
            self._refresh_session_with_mood()
            self.turn_count = 1

        # Inject previous mood context on the first turn after reset
        final_input = text
        if self.turn_count == 1 and self.current_mood != "Normal":
            final_input = f"(Context: Current relationship/mood is '{self.current_mood}')\n{text}"

        try:
            response = self.chat.send_message_stream(final_input)
            tag_pattern = re.compile(r'\[([a-zA-Z0-9_]+)\]')
            buffer = ""
            
            for chunk in response:
                if not chunk.text: continue
                buffer += chunk.text
                
                # Buffer logic: wait for the closing bracket to ensure complete tag parsing
                if "[" in buffer:
                    if "]" in buffer:
                        emotions = tag_pattern.findall(buffer)
                        clean_text = tag_pattern.sub('', buffer)
                        yield clean_text, emotions
                        buffer = ""
                    elif len(buffer) > 100: # Failsafe if closing bracket never arrives
                        yield buffer, []
                        buffer = ""
                else:
                    yield buffer, []
                    buffer = ""
            
            # Yield any remaining text in buffer after the stream ends
            if buffer:
                emotions = tag_pattern.findall(buffer)
                clean_text = tag_pattern.sub('', buffer)
                yield clean_text, emotions

        except Exception as e:
            yield f"Error: {str(e)}", []

    def _refresh_session_with_mood(self):
        """Extract current atmosphere and restart the chat session"""
        try:
            # Silent internal request to capture the mood
            mood_prompt = (
                "Summarize the current relationship atmosphere with the user in one short English sentence. "
                "Example: 'Casual and friendly' or 'Technical and focused'."
            )
            mood_res = self.chat.send_message(mood_prompt)
            self.current_mood = mood_res.text.strip()
        except:
            self.current_mood = "Normal"
        
        self._start_new_session()