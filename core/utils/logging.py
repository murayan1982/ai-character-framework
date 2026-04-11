from pathlib import Path

def append_log(log_file: Path, timestamp: str, user_input: str, ai_text: str) -> None:
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] User: {user_input}\n")
        f.write(f"[{timestamp}] AI: {ai_text}\n\n")