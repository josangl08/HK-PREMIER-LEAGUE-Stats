# ABOUTME: Manager for fixtures using SQLAlchemy database.
# ABOUTME: Handles ICS sync, team enrichment via TheSportsDB, and optimized SQL queries.

import logging
import re
import requests
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.orm import Session

from data.extractors.ics_extractor import ICSExtractor
from data.extractors.hkfa_website_extractor import HKFAWebsiteExtractor
from models.db_models import Fixture, Team, Season
from utils.db_engine import SessionFactory
from utils.common import get_current_season

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

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

COMPETITION_MAPPING: dict[str, str] = {
    # HK Premier League
    "中銀人壽香港超級聯賽": "HK Premier League", "香港超級聯賽": "HK Premier League",
    "BOC Life Hong Kong Premier League": "HK Premier League", "Hong Kong Premier League": "HK Premier League",
    # HKFA Cup
    "足總盃": "HKFA Cup", "Hong Kong FA Cup": "HKFA Cup",
    # Sapling Cup
    "賽馬會菁英盃": "Sapling Cup", "菁英盃": "Sapling Cup", "Hong Kong Sapling Cup": "Sapling Cup",
    # League Cup / Senior Shield
    "聯賽盃": "League Cup", "高級組銀牌": "Senior Shield", "銀牌": "Senior Shield",
    "Hong Kong Senior Challenge Shield": "Senior Shield",
    # New Year Cup (賀歲盃 — all variants)
    "猴年賀歲盃": "New Year Cup", "通海金融賀歲盃": "New Year Cup",
    "NIKE丁酉賀歲盃": "New Year Cup", "Nike 丁酉賀歲盃": "New Year Cup",
    "2018 狗年賀歲盃": "New Year Cup", "FWD富衛保險賀歲盃2026": "New Year Cup",
    "賀歲盃": "New Year Cup",
    # Community Cup (社區盃)
    "香港賽馬會社區盃": "Community Cup", "2016香港賽馬會社區盃": "Community Cup", "社區盃": "Community Cup",
    # Friendly matches
    "國際友誼賽": "Friendly", "國際足球友誼賽": "Friendly", "國際A級友誼賽": "Friendly",
    "友誼賽": "Friendly",
    # Playoff
    "季後附加賽": "Playoff",
    # AFC Cup
    "亞洲足協盃": "AFC Cup", "亞協盃": "AFC Cup", "AFC CupGroup I": "AFC Cup",
    # AFC Champions League
    "亞冠盃": "AFC Champions League",
    # World Cup Qualifiers
    "世界盃外圍賽": "World Cup Qualifiers", "世界杯外圍": "World Cup Qualifiers",
    # HK–Macau Inter-Port / HK–Guangdong Inter-City
    "港澳埠際賽": "HK-Macau Inter-Port",
    "省港盃": "HK-Guangdong Inter-City",
    # EAFF E-1
    "東亞足球錦標賽外圍賽": "EAFF E-1 Championship Qualifiers",
    "東亞足球錦標賽": "EAFF E-1 Championship",
}

STADIUM_MAPPING: dict[str, str] = {
    "旺角大球場": "Mong Kok Stadium", "香港大球場": "Hong Kong Stadium",
    "沙田運動場": "Sha Tin Sports Ground", "將軍澳運動場": "Tseung Kwan O Sports Ground",
    "元朗大球場": "Yuen Long Stadium", "天水圍運動場": "Tin Shui Wai Sports Ground",
    "深水埗運動場": "Sham Shui Po Sports Ground", "小西灣運動場": "Siu Sai Wan Sports Ground",
    "青衣運動場": "Tsing Yi Sports Ground", "北區運動場": "North District Sports Ground",
    "大埔運動場": "Tai Po Sports Ground", "香港足球會": "Hong Kong Football Club Stadium",
    "九龍灣公園": "Kowloon Bay Park", "廣州燕子崗體育場": "Yanzigang Stadium, Guangzhou",
    "香港仔運動場": "Aberdeen Sports Ground", "澳門科技大學運動場": "MUST Stadium, Macau",
    "斧山道運動場": "Hammer Hill Road Sports Ground"
}

# ── FixtureManager ────────────────────────────────────────────────────────────

class FixtureManager:
    """
    Manager for fixtures backed by SQLAlchemy.
    Replaces file-based fixtures.json with a robust relational database.
    """

    def __init__(self):
        self._extractor = ICSExtractor()
        self._web_extractor = HKFAWebsiteExtractor()

    def get_fixtures(self, season: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieves fixtures from the database.
        """
        session = SessionFactory()
        try:
            target_season = season or get_current_season()
            stmt = select(Fixture).where(Fixture.season_id == target_season).order_by(Fixture.date_utc.asc()).limit(limit)
            results = session.execute(stmt).scalars().all()
            return [self._to_dict(f) for f in results]
        finally:
            session.close()

    def get_next_fixtures(self, team_id: str, limit: int = 1) -> List[Dict[str, Any]]:
        """
        Gets upcoming fixtures for a specific team, including those started recently (up to 3h ago).
        """
        session = SessionFactory()
        try:
            # We look back 3 hours to catch matches in progress (LIVE) or recently finished (PENDING)
            threshold = datetime.now(timezone.utc) - timedelta(hours=3)
            stmt = (
                select(Fixture)
                .where(
                    and_(
                        or_(Fixture.home_team_id == team_id, Fixture.away_team_id == team_id),
                        Fixture.date_utc >= threshold
                    )
                )
                .order_by(Fixture.date_utc.asc())
                .limit(limit)
            )
            results = session.execute(stmt).scalars().all()
            return [self._to_dict(f) for f in results]
        finally:
            session.close()

    def get_next_fixture(self, team_id: str) -> Optional[Dict[str, Any]]:
        """Legacy compatibility: returns the single closest fixture (started <3h ago or future)."""
        fixes = self.get_next_fixtures(team_id, limit=1)
        return fixes[0] if fixes else None

    def enrich_fixtures_from_website(self):
        """
        Enriches existing fixtures with metadata scraped from the HKFA website.
        """
        logger.info("Starting fixture enrichment from HKFA website...")
        
        try:
            web_matches = self._web_extractor.fetch_enriched_data()
            if not web_matches:
                logger.warning("No web data found for enrichment.")
                return

            session = SessionFactory()
            try:
                current_season = get_current_season()
                stmt = select(Fixture).where(Fixture.season_id == current_season)
                db_fixtures = session.execute(stmt).scalars().all()
                enriched_count = self._apply_web_enrichment(session, db_fixtures, web_matches)
                
                session.commit()
                logger.info(f"✓ Successfully enriched {enriched_count} fixtures with web metadata.")
                
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error during fixture enrichment: {e}")
            import traceback; traceback.print_exc()

    def refresh_upcoming_fixture_metadata(self, days_ahead: int = 15) -> int:
        """
        Refreshes HKFA metadata only for fixtures in the upcoming window.
        Intended for scheduled runs between full ICS refreshes.
        """
        logger.info(f"Refreshing HKFA metadata for upcoming fixtures in next {days_ahead} days...")

        try:
            web_matches = self._web_extractor.fetch_enriched_data()
            if not web_matches:
                logger.warning("No web data found for incremental fixture refresh.")
                return 0

            session = SessionFactory()
            try:
                now_utc = datetime.now(timezone.utc)
                horizon_utc = now_utc + timedelta(days=days_ahead)
                stmt = (
                    select(Fixture)
                    .where(
                        and_(
                            Fixture.date_utc >= now_utc.replace(tzinfo=None),
                            Fixture.date_utc <= horizon_utc.replace(tzinfo=None),
                        )
                    )
                )
                db_fixtures = session.execute(stmt).scalars().all()
                if not db_fixtures:
                    logger.info("No upcoming fixtures found in the requested refresh window.")
                    return 0

                refreshed_count = self._apply_web_enrichment(session, db_fixtures, web_matches)
                session.commit()
                logger.info(f"✓ Refreshed HKFA metadata for {refreshed_count} upcoming fixtures.")
                return refreshed_count
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error during upcoming fixture metadata refresh: {e}")
            import traceback; traceback.print_exc()
            return 0

    def sync_from_ics(self):
        """
        Performs a full sync from the official ICS to the database.
        """
        logger.info("Starting fixture synchronization from official ICS...")
        session = SessionFactory()
        try:
            events = self._extractor.fetch()
            count = 0
            for ev in events:
                fixture_data = self._parse_event(session, ev)
                if fixture_data:
                    # Check for existing fixture by external_id (UID)
                    existing = session.execute(select(Fixture).where(Fixture.external_id == fixture_data['external_id'])).scalar_one_or_none()
                    
                    if not existing:
                        session.add(Fixture(**fixture_data))
                        count += 1
                    else:
                        # Update existing
                        for key, value in fixture_data.items():
                            setattr(existing, key, value)
            
            session.commit()
            logger.info(f"✓ Sync complete. Processed {len(events)} events, added/updated {count} fixtures.")
            
            # Enrich with web metadata (VAR, Broadcast, etc.)
            self.enrich_fixtures_from_website()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Sync failed: {e}")
        finally:
            session.close()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _to_dict(self, fixture: Fixture) -> Dict[str, Any]:
        """Converts a SQLAlchemy Fixture object to a dictionary for Dash compatibility."""
        k_utc = fixture.date_utc.replace(tzinfo=timezone.utc)
        # HK es UTC+8
        k_hkt = k_utc.astimezone(timezone(timedelta(hours=8)))
        
        return {
            "id": fixture.id,
            "uid": fixture.external_id,
            "date_utc": k_utc,
            "kickoff_utc": k_utc,
            "kickoff_hkt": k_hkt,
            "kickoff_display": k_hkt.strftime("%-d %b %Y, %H:%M HKT"),
            "home_team": fixture.home_team_id,
            "away_team": fixture.away_team_id,
            "stadium": fixture.venue,
            "venue": fixture.venue,
            "competition": fixture.competition_type,
            "streaming_url": fixture.stream_url,
            "stream_url": fixture.stream_url,
            "home_logo_url": fixture.home_team_logo,
            "away_logo_url": fixture.away_team_logo,
            "schedule": {
                "kickoff_utc": k_utc,
                "kickoff_hkt": k_hkt
            },
            "teams": {
                "home": {"name": fixture.home_team_id, "assets": {"badge": fixture.home_team_logo}},
                "away": {"name": fixture.away_team_id, "assets": {"badge": fixture.away_team_logo}}
            },
            "metadata": fixture.metadata_json
        }

    def _parse_event(self, session: Session, ev: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        summary = ev.get("summary") or ""
        parts = summary.split(" - ", 1)
        if len(parts) != 2: return None
        
        match_part, comp_zh = parts[0], parts[1]
        vs = re.split(r"\s+[Vv][Ss]\s+", match_part)
        if len(vs) != 2: return None
        
        home_team_name = vs[0].strip()
        away_team_name = vs[1].strip()
        
        # Helper to get or create team with normalization
        def _get_team(name):
            cleaned = self._clean_name(name)
            name_en = TEAM_MAPPING.get(cleaned, cleaned)
            slug = re.sub(r"[^a-z0-9]", "_", name_en.lower()).strip("_")
            team = session.get(Team, slug)
            if not team:
                team = Team(id=slug, name=name_en)
                session.add(team)
                session.flush()
            return team

        h_team = _get_team(home_team_name)
        a_team = _get_team(away_team_name)
        
        dt = ev.get("dtstart")
        if not dt: return None
        if isinstance(dt, datetime):
            dt_utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        else:
            dt_utc = datetime.combine(dt, datetime.min.time()).replace(tzinfo=timezone.utc)
            
        # Determine Season
        yr, mo = dt_utc.year, dt_utc.month
        sid = f"{yr}-{str(yr+1)[-2:]}" if mo >= 8 else f"{yr-1}-{str(yr)[-2:]}"
        
        # Meta serialization
        meta = {k: (v.isoformat() if isinstance(v, (datetime, date)) else v) for k, v in ev.items()}
        
        return {
            "external_id": ev.get("uid"),
            "season_id": sid,
            "date_utc": dt_utc,
            "home_team_id": h_team.id,
            "away_team_id": a_team.id,
            "venue": self._normalize_stadium(ev.get("location") or ""),
            "competition_type": self._normalize_competition(comp_zh.strip()),
            "stream_url": self._extract_stream(ev.get("description") or ""),
            "home_team_logo": h_team.logo_url,
            "away_team_logo": a_team.logo_url,
            "metadata_json": meta
        }

    def _clean_name(self, name: str) -> str:
        name = re.sub(r"^\((改期|補賽|賽事延期|賽事取消|賽事延期至[^)]*)\)\s*", "", name)
        name = re.sub(r"^【(補賽|賽事延期)】\s*", "", name)
        name = re.sub(r"^\[賽事取消\]\s*", "", name)
        name = re.sub(r"\s*\(\d+\)$", "", name)
        return name.strip()

    def _normalize_competition(self, raw: str) -> str:
        if raw in COMPETITION_MAPPING: return COMPETITION_MAPPING[raw]
        for k, v in sorted(COMPETITION_MAPPING.items(), key=lambda x: len(x[0]), reverse=True):
            if k in raw: return v
        return raw

    def _normalize_stadium(self, raw: str) -> str:
        raw_clean = re.sub(r'<[^>]*>', '', raw).strip()
        if raw_clean in COMPETITION_MAPPING: return COMPETITION_MAPPING[raw_clean]
        if raw_clean in STADIUM_MAPPING: return STADIUM_MAPPING[raw_clean]
        for k, v in sorted(STADIUM_MAPPING.items(), key=lambda x: len(x[0]), reverse=True):
            if k in raw_clean: return v
        return raw_clean

    def _extract_stream(self, desc: str) -> Optional[str]:
        pattern = re.compile(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be|facebook\.com|fb\.com|on\.cc|tv\.on\.cc|now\.com)\S+")
        match = pattern.search(desc)
        return match.group(0).split('?')[0].rstrip('"').rstrip('&') if match else None

    def _parse_web_match_datetime(self, web_match: Dict[str, Any]) -> Optional[datetime]:
        try:
            clean_date = str(web_match["date"]).strip().strip('"').strip("'")
            clean_time = str(web_match["time"]).strip().strip('"').strip("'")
            if clean_time == "--:--":
                clean_time = "00:00"
            web_dt_local = datetime.strptime(f"{clean_date} {clean_time}", "%Y-%m-%d %H:%M")
            return (web_dt_local - timedelta(hours=8)).replace(tzinfo=timezone.utc)
        except Exception as e:
            logger.warning(f"Could not parse web datetime {web_match.get('date')} {web_match.get('time')}: {e}")
            return None

    def _normalize_fixture_team_name(self, name: Any) -> str:
        normalized = str(name).lower()
        for s in [" district", " dt.", " football club", " fc", " athletic", " association", " bc "]:
            normalized = normalized.replace(s, " ")
        return "".join(normalized.split())

    def _find_best_web_match(self, session: Session, db_fixtures: List[Fixture], web_match: Dict[str, Any]) -> Optional[Fixture]:
        web_dt_utc = self._parse_web_match_datetime(web_match)
        if not web_dt_utc:
            return None

        candidates = [
            f for f in db_fixtures
            if abs((f.date_utc.replace(tzinfo=timezone.utc) - web_dt_utc).total_seconds()) <= 7200
        ]
        if not candidates:
            web_date_only = web_dt_utc.date()
            candidates = [f for f in db_fixtures if f.date_utc.date() == web_date_only]
        if not candidates:
            return None

        web_home = str(web_match["home_team"]).strip('"')
        web_away = str(web_match["away_team"]).strip('"')
        web_home_en = TEAM_MAPPING.get(web_home, web_home)
        web_away_en = TEAM_MAPPING.get(web_away, web_away)
        norm_web_h = self._normalize_fixture_team_name(web_home_en)
        norm_web_a = self._normalize_fixture_team_name(web_away_en)

        for cand in candidates:
            home_team = session.get(Team, cand.home_team_id)
            away_team = session.get(Team, cand.away_team_id)
            db_home = home_team.name if home_team else cand.home_team_id
            db_away = away_team.name if away_team else cand.away_team_id
            norm_db_h = self._normalize_fixture_team_name(db_home)
            norm_db_a = self._normalize_fixture_team_name(db_away)
            if (norm_web_h in norm_db_h or norm_db_h in norm_web_h) and \
               (norm_web_a in norm_db_a or norm_db_a in norm_web_a):
                return cand
        return None

    def _apply_web_enrichment(self, session: Session, db_fixtures: List[Fixture], web_matches: List[Dict[str, Any]]) -> int:
        enriched_count = 0
        for web_match in web_matches:
            best_match = self._find_best_web_match(session, db_fixtures, web_match)
            if not best_match:
                continue

            meta = dict(best_match.metadata_json or {})
            meta.update({
                "has_var": web_match.get("has_var", False),
                "broadcast_type": web_match.get("broadcast_type"),
                "hkfa_status": web_match.get("status_text"),
                "hkfa_id": web_match.get("hkfa_id"),
                "ticket_prices": web_match.get("ticket_prices"),
                "is_tv": web_match.get("is_tv", False),
                "last_enriched_at": datetime.now(timezone.utc).isoformat()
            })
            best_match.metadata_json = meta
            enriched_count += 1
        return enriched_count

# ── Legacy Compatibility Helpers ──────────────────────────────────────────────

def _resolve_logo(team_name: str) -> Optional[str]:
    """Helper para obtener el logo de un equipo desde la BD."""
    session = SessionFactory()
    try:
        # Normalizar nombre primero
        from data.managers.fixture_manager import TEAM_MAPPING
        name_en = TEAM_MAPPING.get(team_name, team_name)
        slug = re.sub(r"[^a-z0-9]", "_", name_en.lower()).strip("_")
        team = session.get(Team, slug)
        return team.logo_url if team else None
    finally:
        session.close()

def _resolve_stadium(home_team: str) -> Optional[str]:
    """Helper para obtener el nombre del estadio de un equipo desde la BD."""
    session = SessionFactory()
    try:
        from data.managers.fixture_manager import TEAM_MAPPING
        name_en = TEAM_MAPPING.get(home_team, home_team)
        slug = re.sub(r"[^a-z0-9]", "_", name_en.lower()).strip("_")
        team = session.get(Team, slug)
        return team.stadium_name if team else None
    finally:
        session.close()

def _resolve_fanart(team_name: str) -> Optional[str]:
    """Helper para obtener el fanart de un equipo (si existe)."""
    # Por ahora devolvemos None o implementamos lógica similar a logo
    return None

def _resolve_stadium_thumb(home_team: str) -> Optional[str]:
    """Helper para obtener la miniatura del estadio desde la BD."""
    session = SessionFactory()
    try:
        from data.managers.fixture_manager import TEAM_MAPPING
        name_en = TEAM_MAPPING.get(home_team, home_team)
        slug = re.sub(r"[^a-z0-9]", "_", name_en.lower()).strip("_")
        team = session.get(Team, slug)
        return team.stadium_thumb if team else None
    finally:
        session.close()

# ── Singleton ─────────────────────────────────────────────────────────────────

_instance = None
def get_fixture_manager() -> FixtureManager:
    global _instance
    if _instance is None: _instance = FixtureManager()
    return _instance
