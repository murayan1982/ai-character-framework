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
            f.write("Available ElevenLabs Voices:\n")
            f.write("=" * 50 + "\n")
            
            # Print to console and save to file
            for voice in voices_data.get('voices', []):
                line = f"Name: {voice['name']:<20} | ID: {voice['voice_id']}"
                print(line)
                f.write(line + "\n")
                
        print("=" * 50)
        print(f"Success! List saved to: {output_file}")

    except Exception as e:
        print(f"Error fetching voices: {e}")

if __name__ == "__main__":
    check_voice_ids()