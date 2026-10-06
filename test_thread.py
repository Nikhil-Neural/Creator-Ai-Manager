import time
import requests

# 👇 Yahan apna current valid 60-day token aur User ID daal de
ACCESS_TOKEN = "THAAeP4KKjdaJBYmJya2NUSXh6R19uWlpPYmZAiV0prVFJ5cS1OOUNFcVFxX0hFQXZAMWEQ5c2YwM1FXZAFVIWGFiYW5idVR1Y3RwcGlESnhzejVNczZADbjlUMHFFNUd0bVYzYXItdDNkaUV1SDhoVmljcWZAfMmc0MlM0eXhCQWV0Q09pUQZDZD"
USER_ID = "27348247644837717" # Tera neuralanalyst wala ID
BASE_URL = "https://graph.threads.net/v1.0"
AUTH_PARAMS = {"access_token": ACCESS_TOKEN}

print("🚀 Starting Isolation Test...")

# --- PART 1: ROOT POST ---
print("📦 Creating Root Post...")
payload_1 = {"text": "Test Thread Part 1: Hello from API! 🤖", "media_type": "TEXT"}
res_1 = requests.post(f"{BASE_URL}/{USER_ID}/threads", params=AUTH_PARAMS, json=payload_1).json()

if "error" in res_1:
    print(f"❌ Root Error: {res_1}")
    exit()

creation_id_1 = res_1["id"]
print("🚀 Publishing Root Post...")
pub_1 = requests.post(f"{BASE_URL}/{USER_ID}/threads_publish", params=AUTH_PARAMS, json={"creation_id": creation_id_1}).json()
root_id = pub_1["id"]
print(f"✅ Root Published! ID: {root_id}")

# --- DELAY FOR SYNC ---
print("⏳ Waiting 30 seconds for Meta to sync...")
time.sleep(30)

# --- PART 2: THE REPLY (CHAINING) ---
print("📦 Creating Reply Post (Chaining)...")
payload_2 = {
    "text": "Test Thread Part 2: Reply successful! 🔗", 
    "media_type": "TEXT",
    "reply_to_id": str(root_id)
}
res_2 = requests.post(f"{BASE_URL}/{USER_ID}/threads", params=AUTH_PARAMS, json=payload_2).json()

if "error" in res_2:
    print(f"❌ REPLY CRASHED! EXACT ERROR: {res_2}")
else:
    creation_id_2 = res_2["id"]
    print("🚀 Publishing Reply...")
    pub_2 = requests.post(f"{BASE_URL}/{USER_ID}/threads_publish", params=AUTH_PARAMS, json={"creation_id": creation_id_2}).json()
    print(f"✅ CHAIN SUCCESSFUL! Reply ID: {pub_2.get('id')}")