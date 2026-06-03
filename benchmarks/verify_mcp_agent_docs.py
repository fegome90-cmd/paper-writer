import re
import sys
from pathlib import Path

DOC_PATH = Path("docs/trifecta-mcp-agent-guide.md")

EXPECTED_TOOLS = [
    "ctx_search", "ctx_get", "ctx_oracle", "ctx_calibrate", "ctx_init",
    "ast_analyze", "ctx_health", "ctx_graph", "ctx_graph_metrics",
    "ctx_reindex_graph", "ctx_oracle_health", "ctx_validate", "ctx_reset",
    "ctx_plan", "ast_hover"
]

def main():
    if not DOC_PATH.exists():
        print(0)
        return

    content = DOC_PATH.read_text().lower()
    score = 0
    
    for tool in EXPECTED_TOOLS:
        # Check if the tool is mentioned
        if tool.lower() in content:
            score += 1
            # Check for a specific 'when to use' or 'scenario' section for this tool
            # To be simple, we just look for something like "when to use {tool}" or
            # the tool being in a header
            if re.search(r"when to use.*" + tool.lower(), content) or \
               re.search(r"#" + r".*" + tool.lower(), content):
                score += 1

    print(score)

if __name__ == "__main__":
    main()
