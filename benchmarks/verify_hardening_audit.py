import sys
from pathlib import Path

def main():
    passed = 0
    
    # 1. Check Crossref for T0 and lambda
    cr_path = Path("clients/crossref.py")
    cr_content = cr_path.read_text()
    if "_last_request_at" in cr_content and "lambda: setattr" in cr_content:
        passed += 1
        
    # 2. Check S2 for T0 and lambda
    s2_path = Path("clients/semantic_scholar.py")
    s2_content = s2_path.read_text()
    if "_last_request_at" in s2_content and "lambda: setattr" in s2_content:
        passed += 1
        
    # 3. Check for specific log format in both
    if "Request failed: {type(e).__name__}: {e}" in cr_content and "Request failed: {type(e).__name__}: {e}" in s2_content:
        passed += 1
        
    # 4. Check for URLError handling in public methods
    if "except urllib.error.URLError" in cr_content and "except urllib.error.URLError" in s2_content:
        passed += 1
        
    print(passed)

if __name__ == "__main__":
    main()
