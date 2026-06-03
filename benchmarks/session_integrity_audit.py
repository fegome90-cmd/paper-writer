import subprocess
import sys
from pathlib import Path

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
        except:
            pass
    
    # Audit for constitutional violations (subprocess in production)
    # Exclude benchmarks, tests, build, and hidden directories
    audit_cmd = "grep -r \"subprocess.run\" . --exclude-dir=benchmarks --exclude-dir=tests --exclude-dir=build --exclude-dir=.venv --exclude-dir=.git"
    audit_res = subprocess.run(audit_cmd, shell=True, capture_output=True, text=True)
    
    # Ignore mentions in docs and context pack (non-code)
    clean_lines = [line for line in audit_res.stdout.split("\n") if line.strip() and not line.startswith("./docs/") and not line.startswith("./_ctx/") and not line.startswith("./openspec/")]
    
    constitutional = 1 if not clean_lines else 0
    if constitutional:
        passed_suites += 1

    # Specific check for the trifecta-mcp skill update
    skill_path = Path("skills/local/trifecta-mcp/SKILL.md")
    skill_governed = 0
    if skill_path.exists():
        skill_content = skill_path.read_text().lower()
        if "gentle ai governance" in skill_content:
            skill_governed = 1
            passed_suites += 1
    
    # Final Metric: Number of passed checks (max 5)
    # 1. Functional parity (25/25)
    # 2. Skill alignment (5/5)
    # 3. Agent guide coverage (30/30)
    # 4. Constitutional (no subprocess in production)
    # 5. Universal Skill Governance rules
    print(passed_suites)

if __name__ == "__main__":
    main()
