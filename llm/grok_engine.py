# llm/grok_engine.py
import re
from openai import OpenAI
from config.settings import XAI_API_KEY, ACTIVE_LLM_MODEL, TARGET_LANGUAGE

class GrokEngine:
    def __init__(self, system_instruction: str):
        # Initialize xAI client with OpenAI compatibility
        self.client = OpenAI(
            api_key=XAI_API_KEY,
            base_url="https://api.x.ai/v1"
        )
        self.model_id = ACTIVE_LLM_MODEL
        # Set localized instruction for the AI character
        self.base_instruction = f"{system_instruction}\n\n[IMPORTANT]\nPlease always respond in {TARGET_LANGUAGE}."
        
        # Session management variables
        self.turn_count = 0
        self.current_mood = "Normal"
        self.history = [] # Stores conversation turns: {"role": "...", "content": "..."}

    def ask_stream(self, text: str):
        self.turn_count += 1
        
        # Refresh session every 10 turns to save tokens and maintain performance
        if self.turn_count > 10:
            self._refresh_session_with_mood()
            self.turn_count = 1

        # Build message list for the current request
        messages = [{"role": "system", "content": self.base_instruction}]
        
        # Inject mood context if it is the first turn after a reset
        if self.turn_count == 1 and self.current_mood != "Normal":
            messages.append({"role": "system", "content": f"Context: Current atmosphere is '{self.current_mood}'"})
        
        # Append existing history and the new user input
        messages.extend(self.history)
        messages.append({"role": "user", "content": text})

        try:
            # Execute streaming request
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                stream=True
            )

            buffer = ""
            full_response_text = ""
            tag_pattern = re.compile(r'\[([a-zA-Z0-9_]+)\]')

            for chunk in response:
                # Extract text content from the stream delta
                content = chunk.choices[0].delta.content
                if content:
                    buffer += content
                    full_response_text += content
                    
                    # Parse emotion tags for Live2D synchronization
                    if "[" in buffer and "]" in buffer:
                        emotions = tag_pattern.findall(buffer)
                        clean_text = tag_pattern.sub('', buffer)
                        yield clean_text, emotions
                        buffer = ""
                    elif len(buffer) > 60:
                        yield buffer, []
                        buffer = ""
            
            # Final yield for remaining text
            if buffer:
                yield buffer, []

            # Save this turn to the history list
            self.history.append({"role": "user", "content": text})
            self.history.append({"role": "assistant", "content": full_response_text})

        except Exception as e:
            print(f"[Grok Engine Error]: {e}")
            yield f"Error: {str(e)}", []

    def _refresh_session_with_mood(self):
        """Summarize current mood and clear history to restart session"""
        try:
            # Ask the AI to summarize the relationship based on the history
            mood_messages = self.history + [
                {"role": "user", "content": "Summarize our current relationship atmosphere in one short English sentence. (e.g., 'Friendly and casual')"}
            ]
            res = self.client.chat.completions.create(
                model=self.model_id,
                messages=mood_messages
            )
            self.current_mood = res.choices[0].message.content.strip()
        except:
            self.current_mood = "Normal"
        
        # Reset the history list to keep the context window clean
        self.history = []