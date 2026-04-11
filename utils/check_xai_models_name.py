import os
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

# Set path relative to this script
current_dir = Path(__file__).parent
# Look for .env in the project root
env_path = current_dir.parent / ".env"
load_dotenv(dotenv_path=env_path)

# API Configuration
api_key = os.getenv("XAI_API_KEY")
if not api_key:
    load_dotenv()
    api_key = os.getenv("XAI_API_KEY")

if not api_key:
    print("Error: XAI_API_KEY not found in .env file.")
    exit(1)

# Initialize xAI client (OpenAI compatible)
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1"
)

print("--- Fetching xAI (Grok) Models ---")

try:
    # Retrieve model list from xAI
    models = client.models.list()
    
    # Extract and sort model IDs
    model_list = sorted([m.id for m in models.data])
    
    for name in model_list:
        print(f"Found: {name}")

    # Save output within the utilitys folder
    output_file = current_dir / "available_XAI_list.txt"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Auto-generated model list for config/models.py\n\n")
        f.write("XAI_MODELS = [\n")
        for i, name in enumerate(model_list):
            comma = "," if i < len(model_list) - 1 else ""
            f.write(f"    '{name}'{comma}  # {i}\n")
        f.write("]\n")

    print(f"\n--- Success ---")
    print(f"Generated: {output_file}")

except Exception as e:
    print(f"API Error: {str(e)}")