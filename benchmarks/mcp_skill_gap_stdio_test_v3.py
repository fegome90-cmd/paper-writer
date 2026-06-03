import subprocess
import json
import sys
from pathlib import Path

REPO_PATH = "/Users/felipe_gonzalez/Developer/paper-writer"
DAEMON_PATH = "/Users/felipe_gonzalez/Developer/agent_h/trifecta_dope/src/interfaces/mcp/server.py"

SCENARIOS = [
    ("ctx_search", {"query": "ManuscriptState"}),
    ("ctx_get", {"ids": ["repo:harness/domain/state.py:f60249cebb"]}),
    ("ctx_oracle", {"query": "impact of changing ManuscriptState"}),
    ("ctx_graph", {"action": "callers", "symbol": "ManuscriptState"}),
    ("ctx_graph", {"action": "callees", "symbol": "ManuscriptState.validate"}),
    ("ctx_graph", {"action": "importers", "symbol": "harness.domain.state"}),
    ("ctx_graph", {"action": "import_targets", "symbol": "harness.domain.state"}),
    ("ctx_graph", {"action": "subclasses", "symbol": "ToolWrapper"}),
    ("ctx_graph", {"action": "parents", "symbol": "BibliographyNormalizer"}),
    ("ctx_graph", {"action": "path", "from_symbol": "Orchestrator.execute", "to_symbol": "ManuscriptState"}),
    ("ctx_graph", {"action": "impact", "symbol": "ManuscriptState"}),
    ("ctx_graph", {"action": "orphans", "symbol": ""}),
    ("ctx_graph", {"action": "cycles", "edge_kind": "calls"}),
    ("ctx_graph", {"action": "hubs", "top_n": 5}),
    ("ctx_graph", {"action": "overview", "symbol": ""}),
    ("ctx_graph", {"action": "status", "symbol": ""}),
    ("ctx_graph", {"action": "search", "symbol": "State"}),
    ("ast_analyze", {"path": "harness/domain/state.py"}),
    ("ast_hover", {"path": "harness/domain/state.py", "line": 12, "col": 5}),
    ("ctx_health", {}),
    ("ctx_oracle_health", {}),
    ("ctx_validate", {}),
    ("ctx_reindex_graph", {}),
    ("ctx_plan", {"query": "how to add a new command"}),
    ("ctx_graph_metrics", {"last_n": 10}),
]

def run_tool(name, args):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}
    
    process = subprocess.Popen(
        ["/Users/felipe_gonzalez/Developer/agent_h/trifecta_dope/.venv/bin/python", DAEMON_PATH, "--repo", REPO_PATH, "--mode", "manual"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    try:
        # Send input
        process.stdin.write(json.dumps(payload) + "\n")
        process.stdin.flush()
        
        while True:
            line = process.stdout.readline()
            if not line:
                break
                
            if line.strip().startswith("{") and "jsonrpc" in line:
                process.terminate()
                process.wait(timeout=2)
                try:
                    response = json.loads(line)
                    if "error" in response:
                        if name == "ast_hover" and response["error"].get("code") == -32001:
                            return True, "Graceful Error (No LSP)"
                        return False, f"JSON-RPC Error: {response['error']['message']}"
                    return True, "OK"
                except Exception as e:
                    return False, f"Parse error: {e} | Line: {line[:100]}"
                    
        process.terminate()
        return False, "No JSON-RPC response found."
    except Exception as e:
        process.kill()
        return False, str(e)

def main():
    passed = 0
    gaps = []
    
    for tool, args in SCENARIOS:
        success, msg = run_tool(tool, args)
        if success:
            passed += 1
            print(f"✅ {tool} {args}")
        else:
            gap_msg = f"GAP: {tool} {args} -> {msg}"
            gaps.append(gap_msg)
            print(f"❌ {gap_msg}")
            
    Path("benchmarks/mcp_gaps.log").write_text("\n".join(gaps))
    print(f"\nMetric: {passed}/{len(SCENARIOS)}")
    sys.exit(0 if passed == len(SCENARIOS) else 1)

if __name__ == "__main__":
    main()
