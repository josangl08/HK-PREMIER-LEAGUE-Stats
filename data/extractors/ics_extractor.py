# ABOUTME: Extractor for HKFA ICS calendar data.
# ABOUTME: Fetches and parses the official public Google Calendar for HK Premier League.

import requests
import logging
from icalendar import Calendar
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ICSFetchError(Exception):
    """Custom exception for errors during ICS fetching or parsing."""
    pass

class ICSExtractor:
    """
    Extractor for HKFA ICS data.
    """
    
    DEFAULT_ICS_URL = "https://calendar.google.com/calendar/ical/a31uq2afcdara8qhjfqpil0jrc@group.calendar.google.com/public/basic.ics"

    def __init__(self, url: Optional[str] = None):
        self.url = url or self.DEFAULT_ICS_URL

    def fetch(self) -> List[Dict[str, Any]]:
        """
        Fetches the ICS file and returns a list of parsed events.
        
        Returns:
            List[Dict]: List of event dictionaries with keys:
                uid, dtstart, summary, location, description
        """
        try:
            logger.info(f"Fetching HKFA ICS from {self.url}")
            response = requests.get(self.url, timeout=15)
            response.raise_for_status()
            
            calendar = Calendar.from_ical(response.content)
            events = []
            
            for component in calendar.walk():
                if component.name == "VEVENT":
                    event = {
                        "uid": str(component.get("uid")),
                        "dtstart": component.get("dtstart").dt if component.get("dtstart") else None,
                        "summary": str(component.get("summary")) if component.get("summary") else None,
                        "location": str(component.get("location")) if component.get("location") else None,
                        "description": str(component.get("description")) if component.get("description") else None,
                    }
                    events.append(event)
            
            logger.info(f"Successfully parsed {len(events)} events from ICS.")
            return events

        except requests.RequestException as e:
            msg = f"Network error fetching ICS: {e}"
            logger.error(msg)
            raise ICSFetchError(msg)
        except Exception as e:
            msg = f"Error parsing ICS content: {e}"
            logger.error(msg)
            raise ICSFetchError(msg)
