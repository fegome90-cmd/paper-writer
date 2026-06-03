import sys
import os

FILEPATH = "/Users/felipe_gonzalez/Developer/agent_h/trifecta_dope/src/interfaces/mcp/server.py"

def main():
    if not os.path.exists(FILEPATH):
        print(100) # Big error
        return

    with open(FILEPATH, "r") as f:
        content = f.read()

    missing = ["ctx_validate", "ast_hover", "ctx_plan", "ctx_reset"]
    count = 0
    for tool in missing:
        # Check both definition and handler
        if f'"{tool}"' in content and f'elif name == "{tool}":' in content:
            continue
        count += 1
    
    print(count)

if __name__ == "__main__":
    main()
