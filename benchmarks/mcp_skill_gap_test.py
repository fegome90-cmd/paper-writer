import socket
import json
import subprocess
import time
import sys
from pathlib import Path

SOCKET_PATH = "/tmp/trifecta_f1_0a9954b40438.sock"

# These represent the exact usage patterns instructed by the trifecta-mcp SKILL and Guide.
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
    ("ctx_graph", {"action": "orphans"}),
    ("ctx_graph", {"action": "cycles"}),
    ("ctx_graph", {"action": "hubs"}),
    ("ctx_graph", {"action": "overview"}),
    ("ctx_graph", {"action": "status"}),
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
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(10)
            client.connect(SOCKET_PATH)
            client.sendall((json.dumps(payload) + "\n").encode())
            
            data = b""
            while True:
                chunk = client.recv(4096)
                if not chunk: break
                data += chunk
                if b"\n" in data: break
                
            response = json.loads(data.decode())
            if "error" in response:
                return False, response["error"]["message"]
            
            # Simple success: returned a valid response
            return True, "OK"
    except Exception as e:
        return False, f"Exception: {e}"

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
    # Autoresearch metric: number of passed tools (we want this to equal len(SCENARIOS))
    print(f"\nMetric: {passed}/{len(SCENARIOS)}")
    sys.exit(0 if passed == len(SCENARIOS) else 1)

if __name__ == "__main__":
    main()
