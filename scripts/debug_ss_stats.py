import requests

def debug_stats(match_id, player_id):
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = f"https://api.sofascore.com/api/v1/event/{match_id}/player/{player_id}/statistics"
    print(f"Requesting stats for match {match_id}, player {player_id}: {url}")
    resp = requests.get(url, headers=headers)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print("Stats found!")
        # print(resp.json())
    else:
        print(f"Stats NOT found (404/Error)")

if __name__ == "__main__":
    # Match: Urawa vs Lee Man (11544905)
    # Player: Henri Anier (50909)
    debug_stats(11544905, 50909)
    # Player: Jose Angel (129473)
    debug_stats(11544905, 129473)
