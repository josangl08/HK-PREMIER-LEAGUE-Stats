import requests

def debug_lineup_ratings(match_id):
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = f"https://api.sofascore.com/api/v1/event/{match_id}/lineups"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return
    
    data = resp.json()
    for team in ["home", "away"]:
        players = data.get(team, {}).get("players", [])
        print(f"\n{team.upper()} Players:")
        for p in players:
            name = p.get("player", {}).get("name")
            rating = p.get("statistics", {}).get("rating")
            print(f"- {name}: {rating}")

if __name__ == "__main__":
    debug_lineup_ratings(11544905)
