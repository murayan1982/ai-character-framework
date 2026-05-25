import os
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path

# Set path relative to this script
current_dir = Path(__file__).parent
# Look for .env in the project root
env_path = current_dir.parent / ".env"
load_dotenv(dotenv_path=env_path)

# API Configuration
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # Final attempt to load .env
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found.")
    exit(1)

genai.configure(api_key=api_key)

print("--- Fetching Gemini Models ---")

model_list = []
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            # Format: remove 'models/' prefix
            clean_name = m.name.replace('models/', '')
            model_list.append(clean_name)
            print(f"Found: {clean_name}")

    # Save output within the utilitys folder
    output_file = current_dir / "available_LLM_list.txt"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Auto-generated model list for config/models.py\n\n")
        f.write("GOOGLE_MODELS = [\n")
        for i, name in enumerate(model_list):
            comma = "," if i < len(model_list) - 1 else ""
            f.write(f"    '{name}'{comma}  # {i}\n")
        f.write("]\n")

    print(f"\n--- Success ---")
    print(f"Generated: {output_file}")

except Exception as e:
    print(f"API Error: {str(e)}")
