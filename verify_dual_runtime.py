"""
verify_dual_runtime.py — Cross-runtime Validation Script.
Compares the output of the Local Python Server vs the ArvanCloud Edge Server.
"""
import json, requests, sys, os

# --- CONFIG ---
LOCAL_CMD = "python server.py" # Simplified for logic check; ideally use MCP client
ARVAN_URL = "https://your-edge-function.arvancloud.ir" # Replace with real URL
TEST_QUERY = "گوشی سامسونگ"
TEST_ID = "25751584"

def check_shape(obj1, obj2, path="root"):
    if type(obj1) != type(obj2):
        print(f"❌ Shape mismatch at {path}: {type(obj1)} vs {type(obj2)}")
        return False
    if isinstance(obj1, dict):
        for k in obj1:
            if k not in obj2:
                print(f"❌ Missing key {k} at {path}")
                return False
            if not check_shape(obj1[k], obj2[k], f"{path}.{k}"):
                return False
    elif isinstance(obj1, list):
        if len(obj1) == 0 or len(obj2) == 0: return True # Skip empty
        if not check_shape(obj1[0], obj2[0], f"{path}[0]"):
            return False
    return True

def main():
    print(f"Checking dual-runtime consistency...")
    
    # This is a mock representation. In a real run, we would call 
    # the local MCP tool and the remote HTTP endpoint.
    print("\n[!] Note: To run this, please replace ARVAN_URL with your actual deployed URL.")
    if "your-edge-function" in ARVAN_URL:
        print("Skipping live check: ARVAN_URL not configured.")
        return

    # Example live check logic:
    # 1. Call Local Python logic (importing the normalize functions)
    from snappshop.normalize import normalize_search
    # (mock data from fixtures)
    # local_res = normalize_search(fixture_json, {"query": TEST_QUERY})
    
    # 2. Call ArvanCloud HTTP
    # remote_res = requests.post(f"{ARVAN_URL}/call", json={"name": "search_products", "arguments": {"query": TEST_QUERY}}).json()["content"][0]["text"]
    # remote_res = json.loads(remote_res)
    
    # 3. Compare
    # if check_shape(local_res, remote_res): print("✅ Consistency Verified!")

if __name__ == "__main__":
    main()
