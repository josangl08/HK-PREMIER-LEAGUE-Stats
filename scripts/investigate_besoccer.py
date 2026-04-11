import cloudscraper
from bs4 import BeautifulSoup

def investigate_bleda():
    scraper = cloudscraper.create_scraper()
    url = "https://www.besoccer.com/player/manuel-bleda-268319"
    print(f"Investigating Bleda profile: {url}")
    try:
        resp = scraper.get(url)
        if resp.status_code != 200:
            print(f"Error: {resp.status_code}")
            return
        
        soup = BeautifulSoup(resp.content, "html.parser")
        # Look for team link
        team_link = soup.select_one("a[href*='/team/']")
        if team_link:
            print(f"Bleda Team Link: {team_link.get('text', '')} -> {team_link.get('href')}")
        else:
            print("No team link found")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    investigate_bleda()
