# ABOUTME: Competition normalization and logo registry for deterministic football-domain lookups.
# ABOUTME: Keeps competition naming rules in the data layer instead of generic utils.

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

COMPETITION_LOGO_MAP = {
    "HK Premier League": "/assets/competition_logos/hong_kong_premier_league.png",
    "HKFA Cup": "/assets/competition_logos/hong_kong_fa_cup.png",
    "Sapling Cup": "/assets/competition_logos/hong_kong_sapling_cup___15__25.png",
    "Senior Shield": "/assets/competition_logos/hong_kong_senior_challenge_shield.png",
    "AFC Champions League Two": "/assets/competition_logos/afc_champions_league_two.png",
    "AFC Champions League-Qualification (- 2024)": "/assets/competition_logos/afc_champions_league_qualification____2024.png",
    "AFC Champions League": "/assets/competition_logos/afc_champions_league_qualification____2024.png",
}

COMPETITION_DISPLAY_LONG_MAP = {
    "HK Premier League": "Hong Kong Premier League",
    "HKFA Cup": "Hong Kong FA Cup",
    "Sapling Cup": "Hong Kong Sapling Cup",
    "Senior Shield": "Hong Kong Senior Shield",
    "League Cup": "Hong Kong League Cup",
}

COMPETITION_DISPLAY_SHORT_EXACT_MAP = {
    "Hong Kong Premier League": "Premier League",
    "HK Premier League": "Premier League",
    "Hong Kong FA Cup": "FA Cup",
    "Hong Kong FA Cup Junior Division": "FA Cup J.",
    "HKFA Cup": "HKFA Cup",
    "Hong Kong Sapling Cup ('15-'25)": "Spaling Cup",
    "Sapling Cup": "Spaling Cup",
    "Hong Kong Senior Challenge Shield": "Senior Shield",
    "Senior Shield": "Senior Shield",
    "World Cup qualification Europe": "World Cup q.",
    "World Cup qualification Oceania": "World Cup q.",
    "AFC Challenge League Qualifying": "AFC Cup q.",
    "AFC Champions League (- 2024)": "ACL",
    "AFC Champions League Elite": "ACL II",
    "AFC Champions League Two": "ACL II",
    "AFC Champions League-Qualification (- 2024)": "ACL q.",
    "AFC Cup-Clasificación (- 2024)": "AFC Cup",
    "AFC U17 Asian Cup Qualification": "Asian Cup U17 q.",
    "AFC U20 Asian Cup qualification": "Asian Cup U20 q.",
    "AFC U23 Asian Cup Qualification": "Asian Cup U23 q.",
    "Africa Cup of Nations Qualification": "Africa Cup q.",
    "Asian Cup qualification": "Asian Cup q.",
    "Clasificación Copa de Asia": "Asian Cup q.",
    "Clasificación Mundial Asia": "Asian Cup q.",
    "Copa de la AFC (- 2024)": "AFC Cup",
    "Play-off/out Primavera": "Spring P_O",
    "UEFA Nations League Play-off": "Nations League P_O",
}

COMPETITION_DISPLAY_LONG_EXACT_MAP = {
    "Hong Kong Premier League": "Hong Kong Premier League",
    "HK Premier League": "Hong Kong Premier League",
    "Hong Kong FA Cup": "Hong Kong FA Cup",
    "Hong Kong FA Cup Junior Division": "Hong Kong FA Cup Junior",
    "HKFA Cup": "Hong Kong FA Cup",
    "Hong Kong Sapling Cup ('15-'25)": "Hong Kong Spaling Cup",
    "Sapling Cup": "Hong Kong Spaling Cup",
    "Hong Kong Senior Challenge Shield": "Hong Kong Senior Shield",
    "Senior Shield": "Hong Kong Senior Shield",
    "World Cup qualification Europe": "World Cup Quali",
    "World Cup qualification Oceania": "World Cup Quali",
    "AFC Challenge League Qualifying": "AFC Quali",
    "AFC Champions League (- 2024)": "AFC Champions League",
    "AFC Champions League Elite": "AFC Champions League Two",
    "AFC Champions League Two": "AFC Champions League Two",
    "AFC Champions League-Qualification (- 2024)": "AFC Champions League Two Quali",
    "AFC Cup-Clasificación (- 2024)": "AFC Cup Quali",
    "AFC U17 Asian Cup Qualification": "AFC Asian Cup U17 Quali",
    "AFC U20 Asian Cup qualification": "AFC Asian Cup U20 Quali",
    "AFC U23 Asian Cup Qualification": "AFC Asian Cup U23 Quali",
    "Africa Cup of Nations Qualification": "Africa Cup Quali",
    "Asian Cup qualification": "Asian Cup Quali",
    "Clasificación Copa de Asia": "Asian Cup Quali",
    "Clasificación Mundial Asia": "Asian Cup Quali",
    "Copa de la AFC (- 2024)": "AFC Cup",
    "Play-off/out Primavera": "Spring P_O",
    "UEFA Nations League Play-off": "Nations League Play Off",
}


def normalize_competition(raw: str) -> str:
    """Normalize a competition name to its standard English form."""
    if not raw:
        return raw

    if raw in COMPETITION_MAPPING:
        return COMPETITION_MAPPING[raw]

    for key in sorted(COMPETITION_MAPPING, key=len, reverse=True):
        if key in raw:
            return COMPETITION_MAPPING[key]

    return raw


def get_competition_logo(competition_name: str) -> str | None:
    """Return the local asset path for a competition logo when available."""
    normalized = normalize_competition(competition_name)

    if normalized in COMPETITION_LOGO_MAP:
        return COMPETITION_LOGO_MAP[normalized]

    if competition_name in COMPETITION_LOGO_MAP:
        return COMPETITION_LOGO_MAP[competition_name]

    for key, path in COMPETITION_LOGO_MAP.items():
        if key in competition_name or key in normalized:
            return path

    return None


def get_competition_display_name(competition_name: str, long_form: bool = False) -> str:
    """Return a consistent display label for a competition."""
    if not competition_name:
        return competition_name
    exact_map = COMPETITION_DISPLAY_LONG_EXACT_MAP if long_form else COMPETITION_DISPLAY_SHORT_EXACT_MAP
    if competition_name in exact_map:
        return exact_map[competition_name]
    normalized = normalize_competition(competition_name)
    if long_form:
        return COMPETITION_DISPLAY_LONG_EXACT_MAP.get(
            normalized,
            COMPETITION_DISPLAY_LONG_MAP.get(normalized, normalized),
        )
    return normalized
