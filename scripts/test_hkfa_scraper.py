# ABOUTME: Test script for the HKFA website extractor.
# ABOUTME: Fetches live data and prints the enriched match information.

import sys
import os
import logging

# Add root to path
sys.path.append(os.getcwd())

from data.extractors.hkfa_website_extractor import HKFAWebsiteExtractor

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_scraper():
    extractor = HKFAWebsiteExtractor()
    print("--- Starting HKFA Website Scraper Test ---")
    
    matches = extractor.fetch_enriched_data()
    
    if not matches:
        print("❌ No matches extracted. Check logs for errors.")
        return

    print(f"✅ Extracted {len(matches)} matches.")
    
    # Print first 5 matches as sample
    print("\nSample Matches (First 5):")
    for i, m in enumerate(matches[:5]):
        print(f"{i+1}. {m['date']} {m['time']} | {m['home_team']} vs {m['away_team']}")
        print(f"   Status: {m['status_text']} | VAR: {m['has_var']} | Broadcast: {m['broadcast_type']}")
        print(f"   Icons: {m['live_icons']}")
        print("-" * 40)

    # Search for specific features (VAR or PPV)
    var_matches = [m for m in matches if m['has_var']]
    ppv_matches = [m for m in matches if m['broadcast_type'] == "PPV"]
    delayed_matches = [m for m in matches if m['status_text'] == "Delay"]

    print(f"\nSummary of features found:")
    print(f"- Matches with VAR: {len(var_matches)}")
    print(f"- Matches with PPV: {len(ppv_matches)}")
    print(f"- Matches with Delay: {len(delayed_matches)}")

if __name__ == "__main__":
    test_scraper()
