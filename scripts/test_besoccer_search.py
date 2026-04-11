import cloudscraper
import logging
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test():
    scraper = cloudscraper.create_scraper()
    # Test www.besoccer.com/search-player?q=
    url = "https://www.besoccer.com/search-player?q=Everton%20Camargo"
    logger.info(f"Testing URL: {url}")
    try:
        resp = scraper.get(url)
        logger.info(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "html.parser")
            print(f"Title: {soup.title.string}")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    test()
