import os
import requests
from dotenv import load_dotenv
from pathlib import Path

# Path setup
current_dir = Path(__file__).resolve().parent
env_path = current_dir.parent / ".env"
load_dotenv(dotenv_path=env_path)

def check_voice_ids():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    
    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in .env file.")
        return

    print("--- Fetching Available Voices from ElevenLabs ---")
    
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {
        "Accept": "application/json",
        "xi-api-key": api_key.strip()
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        voices_data = response.json()

        output_file = current_dir / "available_voices.txt"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# Copy and paste the following into VOICE_MASTER in models.py\n")
            f.write("VOICE_MASTER = [\n")
            
            voices = voices_data.get('voices', [])
            for i, voice in enumerate(voices):
                name = voice['name']
                v_id = voice['voice_id']
                
                # Format as a Python dictionary with an index comment at the end
                comma = "," if i < len(voices) - 1 else ""
                line = f'    {{"name": "{name}", "id": "{v_id}"}}{comma}  # {i}'
                
                print(line)
                f.write(line + "\n")
            
            f.write("]\n")
                
        print("=" * 50)
        print(f"Success! Python-formatted list with indices saved to: {output_file}")

    except Exception as e:
        print(f"Error fetching voices: {e}")

if __name__ == "__main__":
    check_voice_ids()