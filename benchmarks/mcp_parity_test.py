import socket
import json
import sys
import subprocess
from pathlib import Path

SOCKET_PATH = "/tmp/trifecta_f1_0a9954b40438.sock"
REPO_PATH = "/Users/felipe_gonzalez/Developer/paper-writer"

TEST_MATRIX = [
    ("ctx_health", {}, ["status", "--repo", REPO_PATH, "--json"]),
    ("ctx_graph", {"action": "overview"}, ["graph", "overview", "--segment", ".", "--json"]),
    ("ctx_graph", {"action": "callers", "symbol": "Orchestrator.execute"}, ["graph", "callers", "--symbol", "Orchestrator.execute", "--json"]),
    ("ctx_search", {"query": "ManuscriptState"}, ["ctx", "search", "-q", "ManuscriptState", "-s", "."]),
    ("ast_analyze", {"path": "harness/domain/state.py"}, ["ast", "symbols", "sym://python/mod/harness.domain.state", "-s", "."]),
]

def run_mcp_tool(name, args):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": args},
    }
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(5)
            client.connect(SOCKET_PATH)
            client.sendall((json.dumps(payload) + "\n").encode())
            data = b""
            while True:
                chunk = client.recv(4096)
                if not chunk: break
                data += chunk
                if b"\n" in data: break
            response = json.loads(data.decode())
            if "error" in response: return None, response["error"]["message"]
            text = response["result"]["content"][0]["text"]
            try: return json.loads(text), None
            except: return text, None
    except Exception as e: return None, str(e)

def run_cli_cmd(args):
    cmd = ["uv", "run", "trifecta"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0: return None, f"Exit {result.returncode}"
    try:
        stdout = result.stdout
        start = stdout.find("{")
        if start == -1: start = stdout.find("[")
        if start == -1: return stdout.strip(), None
        return json.loads(stdout[start:]), None
    except Exception as e: return result.stdout.strip(), None

def main():
    passed = 0
    for tool, params, cli in TEST_MATRIX:
        mcp_res, mcp_err = run_mcp_tool(tool, params)
        cli_res, cli_err = run_cli_cmd(cli)
        if not mcp_err and not cli_err:
            passed += 1
    print(passed)

if __name__ == "__main__":
    main()
