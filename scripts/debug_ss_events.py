import requests
import json
from datetime import datetime

def debug_ss(player_id):
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    url = f"https://api.sofascore.com/api/v1/player/{player_id}/events/last/0"
    print(f"Requesting: {url}")
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code}")
        return
    
    data = resp.json()
    events = data.get("events", [])
    print(f"Found {len(events)} events in first page")
    
    for event in events:
        ts = event.get("startTimestamp")
        dt = datetime.fromtimestamp(ts)
        comp = event.get("tournament", {}).get("name", "")
        home = event.get("homeTeam", {}).get("name", "")
        away = event.get("awayTeam", {}).get("name", "")
        print(f"[{dt.strftime('%Y-%m-%d')}] {comp} | {home} vs {away}")

if __name__ == "__main__":
    debug_ss(129473)
