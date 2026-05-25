import os
import requests
from dotenv import load_dotenv
from pathlib import Path

# Path setup: ensure absolute path resolution
current_dir = Path(__file__).resolve().parent
env_path = current_dir.parent / ".env"

# Load the environment file explicitly
load_dotenv(dotenv_path=env_path)

# 1. Check variable presence
key_name = "ELEVENLABS_API_KEY"
api_key = os.getenv(key_name)

print(f"--- Debug Info ---")
print(f"Environment file path: {env_path}")
print(f"File exists: {env_path.exists()}")

if api_key is None:
    print(f"Error: Variable '{key_name}' not found in .env")
    exit(1)

# 2. Check key format (DO NOT PRINT FULL KEY)
# Show only length and first/last characters for safety
key_length = len(api_key)
if key_length > 0:
    print(f"Key loaded: YES (Length: {key_length})")
    print(f"Key starts with: {api_key[:4]}...")
    print(f"Key ends with: ...{api_key[-4:]}")
else:
    print("Error: Key is empty.")
    exit(1)

print("\n--- Fetching ElevenLabs TTS Models ---")

url = "https://api.elevenlabs.io/v1/models"
headers = {
    "Accept": "application/json",
    "xi-api-key": api_key.strip() # Strip whitespace just in case
}

try:
    response = requests.get(url, headers=headers)
    
    if response.status_code == 401:
        print("Error 401: Unauthorized. The key is either invalid or inactive.")
        # Check for common mistakes
        if '"' in api_key or "'" in api_key:
            print("Hint: Found quotes in your API key. Remove them from .env")
        exit(1)
        
    response.raise_for_status()
    models = response.json()

    output_file = current_dir / "available_tts_models.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("TTS_MODEL_MASTER = [\n")
        for i, m in enumerate(models):
            m_id = m.get("model_id")
            comma = "," if i < len(models) - 1 else ""
            f.write(f"    '{m_id}'{comma}  # {i}\n")
        f.write("]\n")

    print(f"\nSuccess: Generated {output_file}")

except Exception as e:
    print(f"API Error: {str(e)}")