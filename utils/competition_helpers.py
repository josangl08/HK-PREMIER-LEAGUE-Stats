# ABOUTME: Helper utilities for competition name normalization and logo mapping.
# ABOUTME: Consolidates mappings used in migration scripts and UI components.

import logging

logger = logging.getLogger(__name__)

# Mapping: Traditional Chinese competition names → English (Standardized)
COMPETITION_MAPPING = {
    "中銀人壽香港超級聯賽": "HK Premier League",
    "香港超級聯賽": "HK Premier League",
    "BOC Life Hong Kong Premier League": "HK Premier League",
    "Hong Kong Premier League": "HK Premier League",
    "足總盃": "HKFA Cup",
    "Hong Kong FA Cup": "HKFA Cup",
    "賽馬會菁英盃": "Sapling Cup",
    "菁英盃": "Sapling Cup",
    "Hong Kong Sapling Cup": "Sapling Cup",
    "聯賽盃": "League Cup",
    "高級組銀牌": "Senior Shield",
    "銀牌": "Senior Shield",
    "Hong Kong Senior Challenge Shield": "Senior Shield",
    "賀歲盃": "Lunar New Year Cup",
    "NIKE丁酉賀歲盃": "Nike Lunar New Year Cup",
    "亚洲足協盃": "AFC Cup",
    "亞協盃": "AFC Cup",
    "國際友誼賽": "International Friendly",
    "國際足球友誼賽": "International Friendly",
    "國際A級友誼賽": "International A Friendly",
    "友誼賽": "Friendly",
    "季後附加賽": "Season Play-off",
    "亞冠盃": "AFC Champions League",
    "亞冠盃2": "AFC Champions League Two",
    "省港盃": "Guangdong-Hong Kong Cup",
    "東亞足球錦標賽": "EAFF E-1 Football Championship",
    "社區盃": "Community Cup",
    "港澳埠際賽": "Hong Kong–Macau Interport",
    "世界杯外圍分組賽": "World Cup Qualifier",
    "世界盃外圍賽分組賽": "World Cup Qualifier",
}

# Mapping: Normalized English name → Local Asset Path
COMPETITION_LOGO_MAP = {
    "HK Premier League": "/assets/competition_logos/hong_kong_premier_league.png",
    "HKFA Cup": "/assets/competition_logos/hong_kong_fa_cup.png",
    "Sapling Cup": "/assets/competition_logos/hong_kong_sapling_cup___15__25.png",
    "Senior Shield": "/assets/competition_logos/hong_kong_senior_challenge_shield.png",
    "AFC Champions League Two": "/assets/competition_logos/afc_champions_league_two.png",
    "AFC Champions League-Qualification (- 2024)": "/assets/competition_logos/afc_champions_league_qualification____2024.png",
    "AFC Champions League": "/assets/competition_logos/afc_champions_league_qualification____2024.png",
}

def normalize_competition(raw: str) -> str:
    """
    Normalizes a competition name to its standard English form.
    
    Args:
        raw (str): Raw competition name (Chinese or English)
        
    Returns:
        str: Normalized English name
    """
    if not raw:
        return raw
    
    # Exact match first
    if raw in COMPETITION_MAPPING:
        return COMPETITION_MAPPING[raw]
    
    # Substring match (longest key first)
    for key in sorted(COMPETITION_MAPPING, key=len, reverse=True):
        if key in raw:
            return COMPETITION_MAPPING[key]
            
    return raw

def get_competition_logo(competition_name: str) -> str:
    """
    Returns the local asset path for a competition logo.
    
    Args:
        competition_name (str): Raw or normalized competition name
        
    Returns:
        str: Path to the logo asset or None
    """
    normalized = normalize_competition(competition_name)
    
    # Try exact match on normalized name
    if normalized in COMPETITION_LOGO_MAP:
        return COMPETITION_LOGO_MAP[normalized]
    
    # Fallback: check if the raw name itself is a key in the logo map
    if competition_name in COMPETITION_LOGO_MAP:
        return COMPETITION_LOGO_MAP[competition_name]
        
    # Final fallback: substring match in logo map (e.g. "HK Premier League" inside a longer name)
    for key, path in COMPETITION_LOGO_MAP.items():
        if key in competition_name or key in normalized:
            return path
            
    return None
