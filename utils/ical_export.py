# ABOUTME: Utility to generate iCal (.ics) files from fixture data.
# ABOUTME: Used by the Player Portal Stage actions to "Add to Calendar".

import datetime
import uuid

def build_ical_bytes(fixture: dict) -> bytes:
    """
    Constructs a single-event ICS calendar file from a fixture dict.
    
    Expected fixture fields:
    - home_team, away_team: String
    - kickoff_display: String "YYYY-MM-DD HH:MM" (UTC+8)
    - stadium: String
    - competition: String
    
    Returns:
    - bytes: The raw bytes of the .ics file.
    """
    if not fixture:
        return b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//HK-PREMIER-LEAGUE-Stats//NONSGML v1.0//EN\r\nEND:VCALENDAR\r\n"

    home = fixture.get("home_team", "Home Team")
    away = fixture.get("away_team", "Away Team")
    stadium = fixture.get("stadium", "Unknown Stadium")
    competition = fixture.get("competition", "HK Premier League")
    kickoff_str = fixture.get("kickoff_display")

    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    uid = str(uuid.uuid4())

    dt_start_str = ""
    dt_end_str = ""

    if kickoff_str:
        try:
            # Parse "YYYY-MM-DD HH:MM" assuming UTC+8
            dt_obj = datetime.datetime.strptime(kickoff_str, "%Y-%m-%d %H:%M")
            # Convert UTC+8 to UTC (subtract 8 hours)
            dt_utc = dt_obj - datetime.timedelta(hours=8)
            dt_start_str = dt_utc.strftime("%Y%m%dT%H%M%SZ")
            
            # Duration: 2 hours
            dt_end_utc = dt_utc + datetime.timedelta(hours=2)
            dt_end_str = dt_end_utc.strftime("%Y%m%dT%H%M%SZ")
        except ValueError:
            pass

    # Fallback if parsing failed or kickoff missing
    if not dt_start_str:
        # Use a placeholder (today)
        dt_start_str = now_utc
        dt_end_str = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).strftime("%Y%m%dT%H%M%SZ")

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//HK-PREMIER-LEAGUE-Stats//NONSGML v1.0//EN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now_utc}",
        f"DTSTART:{dt_start_str}",
        f"DTEND:{dt_end_str}",
        f"SUMMARY:{home} vs {away}",
        f"LOCATION:{stadium}",
        f"DESCRIPTION:{competition}",
        "END:VEVENT",
        "END:VCALENDAR",
        ""
    ]

    return "\r\n".join(ics_content).encode("utf-8")
