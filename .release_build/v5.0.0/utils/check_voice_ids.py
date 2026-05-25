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
            f.write("# [Copy the ID you like and paste it into your .env file]\n")
            f.write("# Example: ELEVENLABS_VOICE_ID=your_selected_id\n\n")
            f.write("VOICE_MASTER = '[")

            voices = voices_data.get('voices', [])
            for i, voice in enumerate(voices):
                name = voice['name']
                v_id = voice['voice_id']

                comma = "," if i < len(voices) - 1 else ""
                line = f'    {{"name": "{name}", "id": "{v_id}"}}{comma}'

                print(f"Name: {name:<20} | ID: {v_id}")
                f.write(line)
            
            f.write("]'\n")
                
        print("=" * 50)
        print(f"Success! Python-formatted list with indices saved to: {output_file}")

    except Exception as e:
        print(f"Error fetching voices: {e}")

if __name__ == "__main__":
    check_voice_ids()