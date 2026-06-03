import subprocess
import sys

SCRIPTS = [
    "benchmarks/mcp_skill_gap_stdio_test_v3.py",
    "benchmarks/verify_skill_alignment.py",
    "benchmarks/verify_mcp_agent_docs.py"
]

def main():
    passed_suites = 0
    for script in SCRIPTS:
        try:
            res = subprocess.run(["python3", script], capture_output=True, text=True)
            if res.returncode == 0:
                passed_suites += 1
                # print(f"✅ {script} passed")
        except:
            pass
    
    # Audit for constitutional violations (subprocess in production)
    # Exclude benchmarks, tests, and build directories
    audit_cmd = "grep -r \"subprocess.run\" . --exclude-dir=benchmarks --exclude-dir=tests --exclude-dir=build --exclude-dir=.venv"
    audit_res = subprocess.run(audit_cmd, shell=True, capture_output=True, text=True)
    
    constitutional = 1 if not audit_res.stdout.strip() else 0
    if constitutional:
        passed_suites += 1
    
    print(passed_suites)

if __name__ == "__main__":
    main()
