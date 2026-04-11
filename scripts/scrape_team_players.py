import cloudscraper
from bs4 import BeautifulSoup
import re

def scrape_team(team_slug):
    scraper = cloudscraper.create_scraper()
    url = f"https://www.besoccer.com/team/{team_slug}"
    print(f"\n--- Scraping team page: {url} ---")
    try:
        resp = scraper.get(url)
        if resp.status_code != 200:
            print(f"Error: {resp.status_code}")
            return
        
        soup = BeautifulSoup(resp.content, "html.parser")
        player_links = soup.select("a[href*='/player/']")
        
        seen_hrefs = set()
        for link in player_links:
            href = link.get("href")
            if href in seen_hrefs: continue
            seen_hrefs.add(href)
            
            name = link.get_text(strip=True)
            if any(target in name.lower() or target in href.lower() for target in ["jose", "angel", "felipe", "sa"]):
                print(f"Match: {name} -> {href}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape_team("lee-man-warriors")
    scrape_team("eastern-sc")
