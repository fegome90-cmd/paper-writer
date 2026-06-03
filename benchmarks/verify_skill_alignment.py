import os
from pathlib import Path

REF_DIR = Path(".gemini/skills/autoresearch/references")
FILES = ["plan-workflow.md", "debug-workflow.md", "fix-workflow.md", "ship-workflow.md", "security-workflow.md"]

def main():
    aligned = 0
    for f in FILES:
        path = REF_DIR / f
        if not path.exists(): continue
        content = path.read_text().lower()
        if ("gentle ai" in content or "governed" in content) and ("engram" in content or "mem_save" in content):
            aligned += 1
    print(aligned)

if __name__ == "__main__":
    main()
