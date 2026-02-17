import requests
import sqlite3
import json

print("=" * 70)
print("DATABASE SCHEMA CHECK")
print("=" * 70)
conn = sqlite3.connect("data/sunlight.db")
c = conn.cursor()
c.execute("PRAGMA table_info(contracts)")
columns = c.fetchall()
print("Columns in contracts table:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")
conn.close()

print("\n" + "=" * 70)
print("API RESPONSE TEST")
print("=" * 70)

url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
payload = {
    "filters": {
        "award_type_codes": ["A", "B", "C", "D"],
        "award_amounts": [{"lower_bound": 10000000}],
        "time_period": [{"start_date": "2020-01-01", "end_date": "2025-12-31"}]
    },
    "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Start Date", "Description"],
    "limit": 5,
    "page": 1,
    "sort": "Award Amount",
    "order": "desc"
}

try:
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    print(f"Status: {response.status_code}")
    print(f"Response keys: {list(data.keys())}")
    
    results = data.get('results', [])
    print(f"Number of results: {len(results)}")
    
    if results:
        print("\nFIRST CONTRACT (raw):")
        print(json.dumps(results[0], indent=2))
        
        print("\nFIELD MAPPING TEST:")
        print(f"  Award ID: {results[0].get('Award ID')}")
        print(f"  Award Amount: {results[0].get('Award Amount')}")
        print(f"  Recipient Name: {results[0].get('Recipient Name')}")
        
except Exception as e:
    print(f"Error: {e}")
