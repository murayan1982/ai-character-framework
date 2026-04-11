import os

class SecurityManager:
    @staticmethod
    def ensure_safe_environment():
        os.makedirs("config/tokens", exist_ok=True)

        ignore_content = "\n# VTube Studio Tokens\n**/tokens/*.json\n"
        if not os.path.exists(".gitignore"):
            with open(".gitignore", "w", encoding="utf-8") as f:
                f.write(ignore_content)
        else:
            with open(".gitignore", "r", encoding="utf-8") as f:
                content = f.read()
            if "**/tokens/*.json" not in content:
                with open(".gitignore", "a", encoding="utf-8") as f:
                    f.write(ignore_content)