# Script to debug Transfermarkt substitution parsing
import requests
from bs4 import BeautifulSoup
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
}

# Manuel Bleda detailed stats 2018/19
url = "https://www.transfermarkt.es/x/leistungsdatendetails/spieler/146608/saison/2018/plus/1"

print(f"Fetching {url}...")
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.content, "html.parser")

boxes = soup.find_all("div", {"class": "box"})
found = False
for box in boxes:
    header = box.find(["h2", "div"], {"class": ["content-box-headline", "table-header"]})
    if not header or "Hong Kong Premier League" not in header.text: continue
    
    rows = box.find_all("tr")
    for row in rows:
        text = row.get_text()
        if "05/05/2019" in text:
            print("Found match on 05/05/2019!")
            found = True
            print("--- ROW HTML ---")
            print(row.prettify())
            print("----------------")

if not found:
    print("Match not found. Check if season or URL is correct.")
