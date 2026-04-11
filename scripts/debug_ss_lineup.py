import requests

def debug_lineup(match_id):
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = f"https://api.sofascore.com/api/v1/event/{match_id}/lineups"
    print(f"Requesting lineup for match {match_id}: {url}")
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code}")
        return
    
    data = resp.json()
    # Check both teams
    for team in ["home", "away"]:
        players = data.get(team, {}).get("players", [])
        print(f"\nPlayers in {team} team:")
        for p in players:
            p_obj = p.get("player", {})
            name = p_obj.get("name")
            p_id = p_obj.get("id")
            print(f"- {name} (ID: {p_id})")

if __name__ == "__main__":
    # Urawa vs Lee Man
    debug_lineup(11544905)
