import subprocess
import json
import sys

REPO_PATH = "/Users/felipe_gonzalez/Developer/paper-writer"
DAEMON_PATH = "/Users/felipe_gonzalez/Developer/agent_h/trifecta_dope/src/interfaces/mcp/server.py"

# Tools to audit for evidence layer
TOOLS = [
    ("ctx_search", {"query": "ManuscriptState"}),
    ("ctx_graph", {"action": "overview"}),
    ("ctx_health", {}),
    ("ast_analyze", {"path": "harness/domain/state.py"}),
]

def run_tool(name, args):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}
    process = subprocess.Popen(
        ["/Users/felipe_gonzalez/Developer/agent_h/trifecta_dope/.venv/bin/python", DAEMON_PATH, "--repo", REPO_PATH, "--mode", "manual"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
    )
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()
    line = process.stdout.readline()
    process.terminate()
    if line and line.strip().startswith("{"):
        res = json.loads(line)
        content_str = res.get("result", {}).get("content", [{}])[0].get("text", "")
        try: return json.loads(content_str)
        except: return content_str
    return None

def main():
    compliant = 0
    for tool, args in TOOLS:
        res = run_tool(tool, args)
        if isinstance(res, dict) and "fidelity" in res and "evidence" in res:
            compliant += 1
        elif isinstance(res, dict) and "node_count" in res: # Current graph format, not yet wrapped
            pass
    print(compliant)

if __name__ == "__main__":
    main()
