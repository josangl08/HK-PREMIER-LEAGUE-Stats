# ABOUTME: Extractor for enriched match metadata from the official HKFA website.
# ABOUTME: Complements ICS data with VAR, broadcast types (PPV/Free), and real-time status (Delayed).

import requests
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class HKFAWebsiteExtractor:
    """
    Extractor for enriched match metadata from the HKFA website.
    """
    
    BASE_URL = "https://www.hkfa.com/en/competitions/fixtures"
    MAX_PAGES = 5
    
    # Season 2025-2026 Competitions provided by user
    COMPETITIONS = {
        "1945": "Premier League",
        "2030": "Premier League (Championship)",
        "2032": "Premier League (Challenging)",
        "1955": "Senior Shield",
        "1956": "FA Cup",
        "1946": "AFC / Other",
    }

    def __init__(self):
        pass

    def fetch_enriched_data(self) -> List[Dict[str, Any]]:
        """
        Scrapes multiple HKFA competition pages and returns a consolidated list of match metadata.
        """
        all_enriched_matches = []
        seen_ids = set()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        for comp_id, comp_name in self.COMPETITIONS.items():
            empty_pages = 0
            for page in range(1, self.MAX_PAGES + 1):
                url = f"{self.BASE_URL}?year=2025-2026&page={page}&competition={comp_id}"
                try:
                    logger.info(f"Scraping HKFA {comp_name} (ID: {comp_id}) from {url}")
                    response = requests.get(url, headers=headers, timeout=20)
                    response.raise_for_status()

                    response.encoding = 'utf-8'
                    matches = self._parse_html(response.text)
                    if not matches:
                        empty_pages += 1
                        if empty_pages >= 2:
                            break
                        continue

                    empty_pages = 0
                    new_matches = 0
                    for m in matches:
                        if m['hkfa_id'] not in seen_ids:
                            all_enriched_matches.append(m)
                            seen_ids.add(m['hkfa_id'])
                            new_matches += 1

                    if new_matches == 0:
                        break

                except Exception as e:
                    logger.error(f"Error scraping competition {comp_id} page {page}: {e}")
                    break

        logger.info(f"Total unique enriched matches found across all competitions: {len(all_enriched_matches)}")
        return all_enriched_matches

    def _parse_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Parses the HTML content to extract match rows and metadata from the Nuxt state.
        """
        import re
        import json

        enriched_matches = []
        
        # 1. Extract the Nuxt state using regex
        # Use re.DOTALL to handle newlines
        match = re.search(r'window\.__NUXT__=\(function\((?P<args>.*?)\)\{.*?return (?P<obj>.*?)\}\((?P<vals>.*)\)\);', html_content, re.DOTALL)
        if not match:
            logger.warning("Could not find __NUXT__ state in HTML.")
            return []

        args_names_str = match.group('args')
        args_names = [name.strip() for name in args_names_str.split(',')]
        
        raw_vals_str = match.group('vals')
        
        try:
            # Improved argument parsing to handle escaped characters and nested structures
            args_values = []
            current_arg = ""
            depth = 0
            in_string = False
            escape = False
            
            for char in raw_vals_str:
                if char == '\\' and not escape:
                    escape = True
                    current_arg += char
                    continue
                
                if char == '"' and not escape:
                    in_string = not in_string
                
                if char == ',' and depth == 0 and not in_string:
                    args_values.append(current_arg.strip())
                    current_arg = ""
                else:
                    if not in_string:
                        if char in ('[', '{', '('): depth += 1
                        if char in (']', '}', ')'): depth -= 1
                    current_arg += char
                escape = False
            
            args_values.append(current_arg.strip())

            # Create mapping with proper decoding
            mapping = {}
            for i, (name, val) in enumerate(zip(args_names, args_values)):
                if not name: continue
                # Clean up value and decode unicode escapes properly
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    # Replace JS-style unicode escapes (\uXXXX) with Python ones if needed, 
                    # but usually decode('unicode_escape') handles it.
                    try:
                        clean_val = val[1:-1]
                        # Handle double backslashes which are common in JS to Python conversion
                        clean_val = clean_val.replace('\\\\', '\\')
                        mapping[name] = clean_val.encode('utf-8').decode('unicode_escape')
                    except:
                        mapping[name] = val[1:-1]
                elif val == "true": mapping[name] = True
                elif val == "false": mapping[name] = False
                elif val == "null": mapping[name] = None
                else:
                    try:
                        if '.' in val: mapping[name] = float(val)
                        else: mapping[name] = int(val)
                    except:
                        mapping[name] = val

            # Target match objects specifically
            match_pattern = re.compile(r'\{match_time:(?P<time>[^,]+),home_score:(?P<h_score>[^,]+),guest_score:(?P<g_score>[^,]+),match_id:(?P<id>[^,]+),match_date:(?P<date>[^,]+),.*?live_icon:\[(?P<icons>[^\]]*)\]')
            
            for m in match_pattern.finditer(html_content):
                d = m.groupdict()
                
                def resolve(val):
                    if val in mapping: return mapping[val]
                    try:
                        if '.' in val: return float(val)
                        return int(val)
                    except: return val

                match_id = resolve(d['id'])
                m_date = resolve(d['date'])
                m_time = resolve(d['time'])
                
                # Extract icons and other fields near the match
                icon_vars = [v.strip() for v in d['icons'].split(',') if v.strip()]
                icon_values = [resolve(v) for v in icon_vars]
                
                context_start = m.start()
                context_end = html_content.find('}', m.end() + 1500)
                context = html_content[context_start:context_end]
                
                # Ticket prices
                ticket_match = re.search(r'match_ticket:(?P<val>[^,]+)', context)
                ticket_val = resolve(ticket_match.group('val')) if ticket_match else ""
                
                home_name_match = re.search(r'team_home:\{.*?TeamName:(?P<name>[^,}]+)', context)
                guest_name_match = re.search(r'team_guest:\{.*?TeamName:(?P<name>[^,}]+)', context, re.DOTALL)
                
                home_team = resolve(home_name_match.group('name')) if home_name_match else "Unknown"
                away_team = resolve(guest_name_match.group('name')) if guest_name_match else "Unknown"
                
                status_match = re.search(r'matchStatus:(?P<val>[^,]+)', context)
                status_val = resolve(status_match.group('val')) if status_match else ""

                # Final Mapping based on user provided HTML:
                # 1, 15 -> on.cc Free (93293f5-355.png)
                # 2     -> on.cc PPV  (b5fd7db-355.png)
                # 3     -> RTHK (TV)  (8304f2e-316.png)
                # 5     -> VAR        (c410c4f-844.jpeg)
                
                enriched_matches.append({
                    "hkfa_id": match_id,
                    "date": m_date,
                    "time": m_time,
                    "home_team": home_team,
                    "away_team": away_team,
                    "live_icons": icon_values,
                    "status_text": status_val,
                    "ticket_prices": ticket_val,
                    "has_var": any(i in [5, "5"] for i in icon_values),
                    "is_tv": any(i in [3, "3"] for i in icon_values),
                    "broadcast_type": "PPV" if (2 in icon_values or "2" in icon_values) else "Free" if any(i in [1, 15, "1", "15"] for i in icon_values) else None
                })

            return enriched_matches

        except Exception as e:
            logger.error(f"Error parsing HKFA Nuxt state: {e}")
            return []

            logger.info(f"Extracted {len(enriched_matches)} enriched matches from HKFA website.")
            return enriched_matches

        except Exception as e:
            logger.error(f"Error parsing HKFA Nuxt state: {e}")
            import traceback; traceback.print_exc()
            return []
