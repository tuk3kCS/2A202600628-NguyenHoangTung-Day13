import json
import random
import time
import sys
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000"
QUERIES_PATH = Path("data/sample_queries.jsonl")

# Extra fallback queries in case the file isn't found
FALLBACK_QUERIES = [
    {"user_id": "u01", "session_id": "s01", "feature": "qa", "message": "What is your refund policy?"},
    {"user_id": "u02", "session_id": "s02", "feature": "qa", "message": "Explain why metrics traces and logs work together"},
    {"user_id": "u03", "session_id": "s03", "feature": "summary", "message": "Summarize the monitoring policy for production logging"},
    {"user_id": "u04", "session_id": "s04", "feature": "qa", "message": "Can I get help with policy and monitoring?"},
    {"user_id": "u05", "session_id": "s05", "feature": "qa", "message": "What should not appear in app logs?"},
    {"user_id": "u06", "session_id": "s06", "feature": "summary", "message": "Give me a short summary of the observability workflow"},
]

def load_queries():
    if not QUERIES_PATH.exists():
        return FALLBACK_QUERIES
    try:
        lines = [line for line in QUERIES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [json.loads(line) for line in lines]
    except Exception:
        return FALLBACK_QUERIES

def main():
    print("=========================================")
    print("   AI AGENT LIVE TRAFFIC GENERATOR       ")
    print("=========================================")
    print(f"Targeting: {BASE_URL}/chat")
    print("Press Ctrl+C to stop the traffic generator.\n")
    
    queries = load_queries()
    
    # Store sent messages to intentionally trigger cache hits sometimes
    sent_messages = []
    
    # Pre-populate some messages for cache hits
    for q in queries:
        sent_messages.append(q["message"])
        
    with httpx.Client(timeout=10.0) as client:
        count = 0
        while True:
            try:
                count += 1
                # 20% chance of selecting directly from cache
                # 80% chance of a new message (possibly mutated to trigger miss)
                use_cache_hit = len(sent_messages) > 0 and random.random() < 0.2
                
                if use_cache_hit:
                    # Choose a random sent message
                    msg = random.choice(sent_messages)
                    # Use a random sample query configuration but with the cached message
                    base_query = random.choice(queries)
                    payload = {
                        "user_id": base_query["user_id"],
                        "session_id": base_query["session_id"],
                        "feature": base_query["feature"],
                        "message": msg
                    }
                else:
                    # Create a new message or mutate a sample one
                    base_query = random.choice(queries)
                    msg = base_query["message"]
                    
                    # 80% chance of mutating the message to trigger a cache miss
                    if random.random() < 0.8:
                        suffixes = ["", " Thanks!", " Please advise.", " (urgent)", "!", " - thanks.", "?"]
                        suffix = random.choice(suffixes)
                        # Avoid duplicating existing cached messages
                        mutated_msg = f"{msg}{suffix}"
                        if mutated_msg not in sent_messages:
                            msg = mutated_msg
                    
                    # Randomize user and session to simulate multiple users
                    user_num = random.randint(1, 20)
                    session_num = random.randint(1, 50)
                    
                    payload = {
                        "user_id": f"u{user_num:02d}",
                        "session_id": f"s{session_num:02d}",
                        "feature": base_query["feature"],
                        "message": msg
                    }
                    sent_messages.append(msg)
                
                start_time = time.perf_counter()
                r = client.post(f"{BASE_URL}/chat", json=payload)
                client_latency_ms = (time.perf_counter() - start_time) * 1000
                
                if r.status_code == 200:
                    res_json = r.json()
                    cid = res_json.get("correlation_id", "N/A")
                    cost = res_json.get("cost_usd", 0.0)
                    cache_hit = res_json.get("cache_hit", False)
                    cache_status = "CACHE HIT (EXPECTED)" if cache_hit else "CACHE MISS (NEW)"
                    server_latency_ms = float(res_json.get("latency_ms", 0.0))
                    print(f"[{count:03d}] [200 OK] {cid} | {payload['feature']} | {cache_status} | Latency (Server/Client): {server_latency_ms:.1f}ms / {client_latency_ms:.1f}ms | Cost: ${cost:.6f}")
                    
                    try:
                        client.post(f"{BASE_URL}/api/client-latency", json={
                            "correlation_id": cid,
                            "client_latency_ms": client_latency_ms
                        })
                    except Exception:
                        pass
                else:
                    print(f"[{count:03d}] [{r.status_code} Error] Payload: {payload}")
                    
            except httpx.ConnectError:
                print(f"[{count:03d}] Connection Error: Is the FastAPI server running at {BASE_URL}?")
            except Exception as e:
                print(f"[{count:03d}] Error occurred: {e}")
                
            # Random delay between 1.5 to 4.0 seconds
            delay = random.uniform(1.5, 4.0)
            time.sleep(delay)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTraffic generator stopped by user.")
        sys.exit(0)
