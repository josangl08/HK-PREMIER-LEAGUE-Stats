import requests

def debug_career(player_id):
    headers = {'User-Agent': 'Mozilla/5.0'}
    # Try different potential endpoints for career/season stats
    endpoints = [
        f"player/{player_id}/statistics/seasons",
        f"player/{player_id}/characteristics",
        f"player/{player_id}/summary"
    ]
    
    for ep in endpoints:
        url = f"https://api.sofascore.com/api/v1/{ep}"
        resp = requests.get(url, headers=headers)
        print(f"Endpoint: {url} -> Status: {resp.status_code}")
        if resp.status_code == 200:
            print("  Data found!")
            # print(resp.json())

if __name__ == "__main__":
    debug_career(129473)
