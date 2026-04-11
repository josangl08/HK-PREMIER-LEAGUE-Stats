import cloudscraper
from bs4 import BeautifulSoup
import sys
import os

# Add root to path
sys.path.append(os.getcwd())

def debug_competitions(player_tm_id, season_id):
    scraper = cloudscraper.create_scraper()
    url = f"https://www.transfermarkt.es/x/leistungsdatendetails/spieler/{player_tm_id}/saison/{season_id}/plus/1"
    print(f"Scraping: {url}")
    resp = scraper.get(url)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code}")
        return
    
    soup = BeautifulSoup(resp.content, "html.parser")
    boxes = soup.find_all("div", {"class": "box"})
    for box in boxes:
        header = box.find(["h2", "div"], {"class": ["content-box-headline", "table-header"]})
        if not header: continue
        comp_name = header.get_text(strip=True)
        print(f"Found competition: '{comp_name}'")
        
        table = box.find("table")
        if table:
            rows = table.find_all("tr")
            match_count = 0
            for row in rows:
                if row.find("td", {"class": "zentriert"}):
                    match_count += 1
            print(f"  -> Matches in this box: {match_count}")

if __name__ == "__main__":
    # Jose Angel TM ID: 160182
    for s in ["2020", "2021", "2022", "2023"]:
        debug_competitions("160182", s)
        print("-" * 30)
