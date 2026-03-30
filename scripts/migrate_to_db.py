# ABOUTME: ETL script to migrate data from CSV/JSON to SQLAlchemy database.
# ABOUTME: Enriches data with TheSportsDB API and fetches full ICS history for fixtures.
# ABOUTME: COMPREHENSIVE Chinese-to-English mapping for Teams, Stadiums, and Competitions.

import json
import os
import logging
import pandas as pd
import requests
import time
import re
from datetime import datetime, timezone, date
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import select

# Importar modelos y motor
from models.db_models import (
    Base, Role, User, Season, Team, Player, PlayerSeasonStat, 
    Injury, MatchHistory, CardTemplate, AIModelRegistry, SystemSyncLog, TeamAlias, Fixture,
    UserPlayerLink
)
from utils.db_engine import SessionFactory, init_db
from data.extractors.ics_extractor import ICSExtractor
from utils.competition_helpers import normalize_competition, get_competition_logo

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Rutas de origen
DATA_DIR = Path("data")
CACHE_DIR = DATA_DIR / "cache"
HISTORICAL_DIR = DATA_DIR / "historical_records"
TEMPLATES_DIR = Path("assets/templates")
MODELS_REGISTRY = Path("models/registry.json")
USERS_FILE = DATA_DIR / "users.json"
PLAYER_INDEX = DATA_DIR / "player_index.json"

# Mapeos de Identidad
TM_ID_MAP = {
    "148891": "160182",  # José Ángel
    "125040": "146608",  # Manuel Bleda
    "355333": "339749",  # Felipe Sá
}

TSDB_NAME_MAP = {
    "hong_kong_football_club": "Hong Kong FC",
    "rangers": "Hong Kong Rangers",
    "eastern": "Eastern SC",
    "southern_district": "Southern District",
    "lee_man": "Lee Man",
    "kitchee": "Kitchee",
    "tai_po": "Tai Po",
    "north_district": "North District",
    "kowloon_city": "Kowloon City",
    "eastern_district": "Eastern District",
    "pegasus": "Hong Kong Pegasus",
    "south_china": "South China",
    "yuen_long": "Yuen Long",
    "happy_valley": "Happy Valley",
    "sham_shui_po": "Sham Shui Po",
    "resources_capital": "Resources Capital FC",
    "hk_u23": "HK U23",
}

# Mapping: Traditional Chinese (ICS) → English
TEAM_MAPPING: dict[str, str] = {
    "傑志": "Kitchee", "東方龍獅": "Eastern", "東方": "Eastern", "理文": "Lee Man",
    "標準流浪": "Rangers", "流浪": "Rangers", "冠忠南區": "Southern District", "南區": "Southern District",
    "大埔": "Tai Po", "和富大埔": "Tai Po", "九龍城": "Kowloon City", "均業北區": "North Dt.",
    "高力北區": "North Dt.", "北區": "North Dt.", "港會": "Hong Kong Football Club",
    "香港足球會": "Hong Kong Football Club", "深水埗": "Sham Shui Po", "香港U23": "HK U23",
    "晉峰": "Resources Capital", "天水圍飛馬": "Pegasus", "香港飛馬": "Pegasus", "飛馬": "Pegasus",
    "晨曦": "Morning Star", "南華": "South China", "愉園": "Happy Valley", "富力R&F": "R&F",
    "富力 R&F": "R&F", "R&F 富力": "R&F", "R & F 富力": "R&F", "R&F富力": "R&F",
    "夢想FC": "Dreams FC", "夢想駿其": "Dreams Metro Gallery", "灝天黃大仙": "Wong Tai Sin", "黃大仙": "Wong Tai Sin",
    "凱景": "Hoi King", "元朗": "Yuen Long", "佳聯元朗": "Yuen Long", "陽光元朗": "Yuen Long",
    "九巴元朗": "Yuen Long", "東區": "Eastern Dt.", "灣仔": "Wan Chai", "公和屠場": "Kwong Wah",
    "理工大學體育會": "Hong Kong Polytechnic University",
    "香港": "Hong Kong", "柬埔寨": "Cambodia", "老撾": "Laos", "巴林": "Bahrain", "泰國": "Thailand",
    "南韓": "South Korea", "中華台北": "Chinese Taipei", "關島": "Guam", "約旦": "Jordan",
    "土庫曼": "Turkmenistan", "伊朗": "Iran", "澳門": "Macau", "朝鮮": "North Korea",
    "新加坡": "Singapore", "文萊": "Brunei", "所羅門群島": "Solomon Islands", "斐濟": "Fiji",
    "蒙古": "Mongolia", "菲律賓": "Philippines", "毛里求斯": "Mauritius", "中國香港": "Hong Kong, China",
    "馬里士他卡沙": "Balestier Khalsa", "標準灝天": "BC Glory Sky", "柔佛DT": "Johor DT",
    "理文流浪": "Lee Man Rangers", "水原三星藍翼": "Suwon Samsung Bluewings", "廣東": "Guangdong",
    "拉迪恩": "New Radiant", "仰光聯": "Yangon United", "莫亨巴根": "Mohun Bagan", "卡雅": "Kaya FC",
    "馬茲亞": "Maziya", "蒙通聯": "Muangthong United", "FC 首爾": "FC Seoul", "FC首爾": "FC Seoul",
    "川崎前鋒": "Kawasaki Frontale", "廣州恒大": "Guangzhou Evergrande", "河內 FC": "Hanoi FC",
    "南定": "Nam Dinh", "淡濱尼流浪": "Tampines Rovers", "曼谷聯": "Bangkok United", "列支敦士登": "Liechtenstein",
    "FC悉尼": "Sydney FC", "廣島三箭": "Sanfrecce Hiroshima", "山東魯能泰山": "Shandong Luneng",
    "奧克蘭城": "Auckland City", "香港經典選手隊": "Hong Kong Classic XI", "經典外援選手隊": "Classic Foreign XI",
    "香港聯賽選手隊": "Hong Kong League XI", "香港代表隊": "Hong Kong National Team",
    "香港女足80": "Hong Kong Women 80s", "香港女足90": "Hong Kong Women 90s", "黎明SC": "April 25 SC",
    "尼泊爾武警部隊": "Nepal APF",
    "(待定)": "TBD", "SS01勝方": "Winner SS01", "SS02勝方": "Winner SS02", "LC01勝方": "Winner LC01"
}

# Mapping: Traditional Chinese stadium names → English
STADIUM_MAPPING: dict[str, str] = {
    "旺角大球場": "Mong Kok Stadium",
    "香港大球場": "Hong Kong Stadium",
    "沙田運動場": "Sha Tin Sports Ground",
    "將軍澳運動場": "Tseung Kwan O Sports Ground",
    "元朗大球場": "Yuen Long Stadium",
    "天水圍運動場": "Tin Shui Wai Sports Ground",
    "深水埗運動場": "Sham Shui Po Sports Ground",
    "小西灣運動場": "Siu Sai Wan Sports Ground",
    "青衣運動場": "Tsing Yi Sports Ground",
    "北區運動場": "North District Sports Ground",
    "大埔運動場": "Tai Po Sports Ground",
    "香港足球會": "Hong Kong Football Club Stadium",
    "九龍灣公園": "Kowloon Bay Park",
    "廣州燕子崗體育場": "Yanzigang Stadium, Guangzhou",
    "香港仔運動場": "Aberdeen Sports Ground",
    "海外作客": "Away / Overseas",
    "將軍澳足球訓練中心1號場": "FTC Field 1, TKO",
    "將軍澳足球訓練中心2號場": "FTC Field 2, TKO",
    "作客 / 海外": "Away / Overseas",
    "澳門科技大學運動場": "MUST Stadium, Macau",
    "啟德青年運動場": "Kai Tak Youth Sports Ground",
    "斧山道運動場": "Hammer Hill Road Sports Ground",
    "屯門鄧肇堅運動場": "Tuen Mun Tang Shiu Kin Sports Ground",
    "西貢鄧肇堅運動場": "Sai Kung Tang Shiu Kin Sports Ground",
}

TM_TO_PLAYER_ID = {v: k for k, v in TM_ID_MAP.items()}
_teams_cache = {}
_seasons_added = set()
_tsdb_teams = {}

def fetch_tsdb_data():
    global _tsdb_teams
    url_league = "https://www.thesportsdb.com/api/v1/json/3/search_all_teams.php?l=Hong-Kong+Premier+League"
    try:
        resp = requests.get(url_league, timeout=10)
        teams = resp.json().get("teams") or []
        for t in teams: _tsdb_teams[t["strTeam"].lower()] = t
    except: pass
    for tsdb_name in TSDB_NAME_MAP.values():
        if tsdb_name.lower() not in _tsdb_teams:
            try:
                url_search = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={tsdb_name.replace(' ', '+')}"
                resp = requests.get(url_search, timeout=10)
                found = resp.json().get("teams") or []
                for ft in found:
                    if ft.get("strLocation") == "Hong Kong" or ft.get("strLeague") == "Hong-Kong Premier League":
                        _tsdb_teams[tsdb_name.lower()] = ft
                        break
                time.sleep(0.1)
            except: pass

def get_season_from_date(dt: datetime) -> str:
    year, month = dt.year, dt.month
    return f"{year}-{str(year+1)[-2:]}" if month >= 8 else f"{year-1}-{str(year)[-2:]}"

def _clean_chinese_name(name: str) -> str:
    if not name: return name
    name = re.sub(r"^\((改期|補賽|賽事延期|賽事取消|賽事延期至[^)]*)\)\s*", "", name)
    name = re.sub(r"^【(補賽|賽事延期)】\s*", "", name)
    name = re.sub(r"^\[賽事取消\]\s*", "", name)
    name = re.sub(r"^改期\s+", "", name)
    name = re.sub(r"\s*\((\d+|女子|新加坡|馬爾代夫|緬甸|印度|菲律賓|韓國|新西蘭|中國|越南|朝鮮)\)$", "", name)
    name = re.sub(r"\*$", "", name)
    return name.strip()

def get_or_create_team(session: Session, name: str) -> Team:
    if not name: return None
    cleaned_zh = _clean_chinese_name(name)
    name_en = TEAM_MAPPING.get(cleaned_zh, cleaned_zh)
    if re.search(r'[\u4e00-\u9fff]', name_en):
        for zh_key, en_val in TEAM_MAPPING.items():
            if zh_key in name_en:
                name_en = en_val
                break
    team_slug = name_en.lower().strip().replace(" ", "_").replace("&", "n")
    if team_slug in _teams_cache: return _teams_cache[team_slug]
    team = session.get(Team, team_slug)
    if not team:
        tsdb_name = TSDB_NAME_MAP.get(team_slug, name_en)
        tsdb_data = _tsdb_teams.get(tsdb_name.lower()) or _tsdb_teams.get(name_en.lower())
        team = Team(id=team_slug, name=name_en)
        if tsdb_data:
            team.tsdb_id = int(tsdb_data.get("idTeam")) if tsdb_data.get("idTeam") else None
            team.stadium_name = tsdb_data.get("strStadium")
            team.stadium_id = int(tsdb_data.get("idVenue")) if tsdb_data.get("idVenue") else None
            team.website, team.instagram = tsdb_data.get("strWebsite"), tsdb_data.get("strInstagram")
            team.logo_url = tsdb_data.get("strBadge") or tsdb_data.get("strTeamBadge")
        session.add(team)
        session.flush()
    _teams_cache[team_slug] = team
    return team

def _normalize_competition(raw: str) -> str:
    if not raw: return raw
    if raw in STADIUM_MAPPING: return STADIUM_MAPPING[raw]
    
    # Use central normalization helper
    norm = normalize_competition(raw)
    if norm != raw:
        return norm

    for key, val in sorted(STADIUM_MAPPING.items(), key=lambda x: len(x[0]), reverse=True):
        if key in raw: return val
    return raw

def _normalize_stadium(raw: str) -> str:
    if not raw: return raw
    raw_clean = re.sub(r'<[^>]*>', '', raw).strip()
    
    # Use central normalization helper
    norm = normalize_competition(raw_clean)
    if norm != raw_clean:
        return norm

    if raw_clean in STADIUM_MAPPING: return STADIUM_MAPPING[raw_clean]
    for key, val in sorted(STADIUM_MAPPING.items(), key=lambda x: len(x[0]), reverse=True):
        if key in raw_clean: return val
    return raw_clean

def _extract_streaming_url(description: str) -> str:
    if not description: return None
    pattern = re.compile(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be|facebook\.com|fb\.com|on\.cc|tv\.on\.cc|now\.com)\S+")
    match = pattern.search(description)
    if match: return match.group(0).rstrip('"').rstrip('&').split('?')[0]
    return None

def migrate_roles_and_users(session: Session):
    roles_map = {}
    for name in ["Admin", "Player", "Agent"]:
        role = session.execute(select(Role).where(Role.name == name)).scalar_one_or_none()
        if not role:
            role = Role(name=name, description=f"Rol de {name}")
            session.add(role)
            session.flush()
        roles_map[name] = role.id
    if USERS_FILE.exists():
        with open(USERS_FILE, "r") as f:
            for username, data in json.load(f).items():
                if not session.execute(select(User).where(User.username == username)).scalar_one_or_none():
                    role_name = data.get("role", "Player").capitalize()
                    profile_data = {
                        "player_profile": data.get("player_profile", {}),
                        "agent_profile": data.get("agent_profile", {}),
                        "managed_players": data.get("managed_players", []),
                        "synced_at": data.get("synced_at")
                    }
                    new_user = User(
                        id=str(data.get("id", username)), username=username, 
                        email=data.get("email", f"{username}@example.com"), 
                        password_hash=data.get("password_hash"), 
                        role_id=roles_map.get(role_name, roles_map["Player"]), 
                        created_at=datetime.utcnow(),
                        profile_data=profile_data
                    )
                    session.add(new_user)
                    session.flush()
                    p_id = data.get("player_id")
                    if p_id:
                        session.add(UserPlayerLink(user_id=new_user.id, player_id=str(p_id)))
                    m_players = data.get("managed_players", [])
                    if m_players:
                        for pid in m_players:
                            p_obj = session.get(Player, str(pid))
                            if p_obj: new_user.managed_players.append(p_obj)

def migrate_seasons(session: Session):
    for yr in range(2015, 2026):
        sid = f"{yr}-{str(yr+1)[-2:]}"
        if not session.get(Season, sid):
            session.add(Season(id=sid, is_current=(sid == "2025-26")))

def migrate_players(session: Session):
    logger.info("Migrando Jugadores con detalles completos...")
    if PLAYER_INDEX.exists():
        with open(PLAYER_INDEX, "r") as f:
            index_data = json.load(f)
            players = index_data.get("by_id", {k: v for k, v in index_data.items() if k != "_meta"})
            for pid, d in players.items():
                player = session.get(Player, pid)
                team_name = d.get("team")
                team = get_or_create_team(session, team_name or "Unknown")
                tm_id = d.get("tm_id") or TM_ID_MAP.get(pid)
                fingerprint = d.get("fingerprint", {})
                
                birth_date = None
                bd_str = d.get("birth_date") or fingerprint.get("birth_date")
                if bd_str:
                    try:
                        birth_date = datetime.fromisoformat(bd_str.replace("Z", ""))
                    except: pass

                if not player:
                    player = Player(
                        id=pid, 
                        name=d.get("canonical_name", pid), 
                        tm_id=int(tm_id) if tm_id and str(tm_id).isdigit() else None, 
                        current_team_id=team.id if team else None, 
                        nationality=d.get("nationality") or fingerprint.get("birth_country"), 
                        birth_country=fingerprint.get("birth_country"),
                        position_main=d.get("position") or fingerprint.get("position"),
                        foot=d.get("foot") or fingerprint.get("foot"),
                        height=int(d.get("height", 0)) if d.get("height") and int(d.get("height")) > 0 else int(fingerprint.get("height", 0)) if fingerprint.get("height") and int(fingerprint.get("height")) > 0 else None,
                        birth_date=birth_date
                    )
                    session.add(player)
                else:
                    # Enrich existing player if fields are empty
                    if not player.tm_id and tm_id and str(tm_id).isdigit():
                        player.tm_id = int(tm_id)
                    if not player.current_team_id and team:
                        player.current_team_id = team.id
                    if (not player.nationality or player.nationality == ""):
                        player.nationality = d.get("nationality") or fingerprint.get("birth_country")
                    if (not player.birth_country or player.birth_country == ""):
                        player.birth_country = fingerprint.get("birth_country")
                    if (not player.position_main or player.position_main == ""):
                        player.position_main = d.get("position") or fingerprint.get("position")
                    if (not player.foot or player.foot == ""):
                        player.foot = d.get("foot") or fingerprint.get("foot")
                    if (not player.height or player.height == 0):
                        h = int(d.get("height", 0)) if d.get("height") and int(d.get("height")) > 0 else int(fingerprint.get("height", 0)) if fingerprint.get("height") and int(fingerprint.get("height")) > 0 else None
                        if h: player.height = h
                    if not player.birth_date and birth_date:
                        player.birth_date = birth_date

def migrate_stats(session: Session):
    logger.info("Migrando Estadísticas de CSVs...")
    if CACHE_DIR.exists():
        # Sort CSVs by name (season) to process them chronologically
        csv_files = sorted(list(CACHE_DIR.glob("hong_kong_*.csv")))
        for csv_path in csv_files:
            parts = csv_path.stem.split("_")
            if len(parts) < 4: continue
            season_id = f"{parts[2]}-{parts[3]}"
            season_start_year = int(parts[2])
            df = pd.read_csv(csv_path)
            count = 0
            for _, row in df.iterrows():
                player_name = row.get("Player")
                
                # Robustly get Wyscout ID from row
                raw_id = row.get("Wyscout id")
                wyscout_id = None
                if pd.notnull(raw_id):
                    try:
                        wyscout_id = str(int(float(raw_id)))
                    except:
                        wyscout_id = str(raw_id)
                
                if not player_name and not wyscout_id: continue
                
                # TRY MATCH BY ID FIRST, THEN BY NAME
                player = None
                if wyscout_id:
                    player = session.get(Player, wyscout_id)
                
                if not player and player_name:
                    player = session.execute(select(Player).where(Player.name == player_name)).scalars().first()
                
                if not player: continue

                # ENRICH PLAYER DATA FROM CSV IF MISSING
                # Position logic: Primary position > First item in Position list
                primary_pos = row.get("Primary position")
                raw_pos_list = row.get("Position")
                
                final_pos = None
                if pd.notnull(primary_pos) and str(primary_pos).strip() not in ["0", "nan", ""]:
                    final_pos = str(primary_pos).strip()
                elif pd.notnull(raw_pos_list) and str(raw_pos_list).strip() not in ["0", "nan", ""]:
                    # Split by comma and take the first one (e.g., "RB, LB" -> "RB")
                    pos_parts = str(raw_pos_list).split(",")
                    if pos_parts:
                        final_pos = pos_parts[0].strip()

                if (not player.position_main or player.position_main == "") and final_pos:
                    player.position_main = final_pos
                
                # 1. Update Age (always take the latest known)
                csv_age = row.get("Age")
                if pd.notnull(csv_age):
                    try:
                        age_val = int(float(csv_age))
                        if age_val > 0:
                            player.age = age_val
                    except: pass

                # 2. Try REAL Birthday from CSV first
                csv_birthday = row.get("Birthday")
                if not player.birth_date and pd.notnull(csv_birthday):
                    try:
                        bd_str = str(csv_birthday).strip()
                        if "-" in bd_str and bd_str != "nan":
                            player.birth_date = datetime.strptime(bd_str, "%Y-%m-%d")
                    except: pass
                
                # 3. Estimate ONLY if still missing
                if not player.birth_date and pd.notnull(csv_age):
                    try:
                        age_val = int(float(csv_age))
                        if age_val > 0:
                            estimated_year = season_start_year - age_val
                            player.birth_date = datetime(estimated_year, 1, 1)
                    except: pass
                
                csv_birth_country = row.get("Birth country")
                csv_passport_country = row.get("Passport country")
                
                if (not player.birth_country or player.birth_country == ""):
                    if pd.notnull(csv_birth_country) and str(csv_birth_country).strip() not in ["nan", ""]:
                        player.birth_country = str(csv_birth_country).strip()
                    elif pd.notnull(csv_passport_country) and str(csv_passport_country).strip() not in ["nan", ""]:
                        player.birth_country = str(csv_passport_country).strip()
                
                if (not player.height or player.height == 0) and row.get("Height"):
                    try:
                        h = int(float(row.get("Height")))
                        if h > 0: player.height = h
                    except: pass
                
                if (not player.foot or player.foot == "") and row.get("Foot"):
                    foot = str(row.get("Foot")).strip()
                    if foot and foot != "nan" and foot != "":
                        player.foot = foot

                if not session.execute(select(PlayerSeasonStat).where(PlayerSeasonStat.player_id == player.id, PlayerSeasonStat.season_id == season_id)).scalars().first():
                    all_data = row.to_dict()
                    core = {
                        "matches_played": int(all_data.get("Matches played", 0)) if pd.notnull(all_data.get("Matches played")) else 0,
                        "minutes_played": int(all_data.get("Minutes played", 0)) if pd.notnull(all_data.get("Minutes played")) else 0,
                        "goals": int(all_data.get("Goals", 0)) if pd.notnull(all_data.get("Goals")) else 0,
                        "assists": int(all_data.get("Assists", 0)) if pd.notnull(all_data.get("Assists")) else 0,
                        "yellow_cards": int(all_data.get("Yellow cards", 0)) if pd.notnull(all_data.get("Yellow cards")) else 0,
                        "red_cards": int(all_data.get("Red cards", 0)) if pd.notnull(all_data.get("Red cards")) else 0
                    }
                    for k in ["Player", "Matches played", "Minutes played", "Goals", "Assists", "Yellow cards", "Red cards"]:
                        if k in all_data: del all_data[k]
                    all_data = {k: (v if pd.notnull(v) else None) for k, v in all_data.items()}
                    session.add(PlayerSeasonStat(player_id=player.id, season_id=season_id, **core, advanced_stats=all_data))
                    count += 1
            logger.info(f"✓ {count} estadísticas migradas para {season_id}.")

def update_current_teams(session: Session):
    logger.info("Actualizando equipos actuales de los jugadores desde las estadísticas más recientes...")
    session.flush()
    latest_stats_stmt = select(PlayerSeasonStat).where(PlayerSeasonStat.season_id == "2025-26")
    stats = session.execute(latest_stats_stmt).scalars().all()
    count = 0
    for s in stats:
        team_name = s.advanced_stats.get("Team")
        if team_name:
            team = get_or_create_team(session, team_name)
            if team:
                player = session.get(Player, s.player_id)
                if player:
                    player.current_team_id = team.id
                    count += 1
    logger.info(f"✓ {count} jugadores actualizados con su equipo actual (2025-26).")

def migrate_fixtures_from_ics(session: Session):
    logger.info("Migrando Fixtures directamente desde el ICS oficial...")
    try:
        ext = ICSExtractor()
        events = ext.fetch()
        count = 0
        for ev in events:
            summary = ev.get("summary") or ""
            parts = summary.split(" - ", 1)
            if len(parts) != 2: continue
            match_part, comp_zh = parts[0], parts[1]
            vs = re.split(r"\s+[Vv][Ss]\s+", match_part)
            if len(vs) != 2: continue
            home_team, away_team = get_or_create_team(session, vs[0].strip()), get_or_create_team(session, vs[1].strip())
            if not home_team or not away_team: continue
            dt = ev.get("dtstart")
            if not dt: continue
            if isinstance(dt, datetime): dt_utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            else: dt_utc = datetime.combine(dt, datetime.min.time()).replace(tzinfo=timezone.utc)
            season_id = get_season_from_date(dt_utc)
            if not session.get(Season, season_id): session.add(Season(id=season_id, is_current=(season_id == "2025-26")))
            stream = _extract_streaming_url(ev.get("description") or "")
            comp_en, venue_en = _normalize_competition(comp_zh.strip()), _normalize_stadium(ev.get("location") or "")
            meta = {k: (v.isoformat() if isinstance(v, (datetime, date)) else v) for k, v in ev.items()}
            session.add(Fixture(external_id=ev.get("uid"), season_id=season_id, date_utc=dt_utc, home_team_id=home_team.id, away_team_id=away_team.id, venue=venue_en, stadium_id=str(home_team.stadium_id) if home_team.stadium_id else None, competition_type=comp_en, stream_url=stream, home_team_logo=home_team.logo_url, away_team_logo=away_team.logo_url, metadata_json=meta))
            count += 1
        logger.info(f"✓ {count} fixtures migrados.")
    except Exception as e: logger.error(f"Error ICS: {e}")

def migrate_transfermarkt_data(session: Session):
    logger.info("Migrando Historial detallado de Transfermarkt...")
    if HISTORICAL_DIR.exists():
        count = 0
        for jf in HISTORICAL_DIR.glob("*.json"):
            player = session.execute(select(Player).where(Player.tm_id == int(jf.stem) if jf.stem.isdigit() else 0)).scalars().first()
            if not player:
                mapped = TM_TO_PLAYER_ID.get(jf.stem)
                if mapped: player = session.get(Player, mapped)
            if not player: continue
            with open(jf, "r") as f:
                data = json.load(f)
                for s_key, s_content in data.get("seasons", {}).items():
                    for m in s_content.get("matches", []):
                        try:
                            if "date" not in m: continue
                            
                            comp_raw = m.get("competition")
                            comp_name = normalize_competition(comp_raw)
                            
                            # Logo assignment: 1. JSON, 2. Helper mapping, 3. None
                            comp_logo = m.get("competition_logo")
                            if not comp_logo or comp_logo == "":
                                comp_logo = get_competition_logo(comp_raw)

                            session.add(MatchHistory(
                                player_id=player.id, 
                                date=datetime.strptime(m["date"], "%d/%m/%Y"), 
                                competition_name=comp_name, 
                                competition_logo=comp_logo, 
                                opponent=m.get("opponent"), 
                                result=m.get("result"), 
                                minutes_played=m.get("minutes_played") or m.get("minutes") or 0, 
                                goals=m.get("goals", 0), 
                                assists=m.get("assists", 0), 
                                yellow_cards=m.get("yellow_cards", 0), 
                                red_cards=m.get("red_cards", 0), 
                                position=m.get("position"), 
                                status=m.get("status", "Jugado"), 
                                raw_data=m
                            ))
                            count += 1
                        except: continue
        logger.info(f"✓ {count} registros de historial detallado migrados.")

def migrate_system_data(session: Session):
    if TEMPLATES_DIR.exists():
        for cfg in TEMPLATES_DIR.glob("*_config.json"):
            with open(cfg, "r") as f:
                d = json.load(f)
                if not session.get(CardTemplate, cfg.stem): session.add(CardTemplate(id=cfg.stem, name=d.get("name", cfg.stem), config=d))
    if MODELS_REGISTRY.exists():
        with open(MODELS_REGISTRY, "r") as f:
            for mk, mi in json.load(f).items():
                for v in mi.get("versions", []):
                    vn = v.get("version", 1)
                    if not session.execute(select(AIModelRegistry).where(AIModelRegistry.model_name == mk, AIModelRegistry.version == vn)).scalars().first():
                        session.add(AIModelRegistry(model_name=mk, version=vn, path=v.get("path", ""), model_type=v.get("model_type"), metrics=v.get("metrics"), features=v.get("features")))

def migrate_sync_logs(session: Session):
    ts_file = CACHE_DIR / "update_timestamps.json"
    if ts_file.exists():
        with open(ts_file, "r") as f:
            for task, ts in json.load(f).items():
                try:
                    if not session.get(SystemSyncLog, task): session.add(SystemSyncLog(task_name=task, last_run=datetime.fromisoformat(ts), status="SUCCESS"))
                except: pass

def run_migration():
    logger.info("=== INICIANDO MIGRACIÓN DEFINITIVA TOTAL ===")
    fetch_tsdb_data()
    init_db()
    session = SessionFactory()
    try:
        migrate_roles_and_users(session)
        migrate_seasons(session)
        session.commit()
        migrate_players(session)
        session.commit()
        migrate_stats(session)
        update_current_teams(session)
        migrate_fixtures_from_ics(session)
        migrate_transfermarkt_data(session)
        migrate_system_data(session)
        migrate_sync_logs(session)
        session.commit()
        logger.info("=== MIGRACIÓN COMPLETADA CON ÉXITO ===")
    except Exception as e:
        session.rollback()
        logger.error(f"Error: {e}")
        import traceback; traceback.print_exc()
    finally: session.close()

if __name__ == "__main__": run_migration()
