# ABOUTME: Background worker that intelligently polls Transfermarkt for recent match results.
# ABOUTME: Implements a retry schedule (10m, 30m, 1h...) to capture finished matches as soon as they appear.

import sys
import os
import logging
import time
import argparse
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, and_, or_

# Add root to path
sys.path.append(os.getcwd())

from models.db_models import (
    Fixture,
    MatchHistory,
    MatchUpdateQueue,
    Player,
    PlayerRefreshState,
    UserPlayerLink,
    agent_player_links,
)
from utils.db_engine import SessionFactory, init_db
from data.transfermarkt_data_manager import TransfermarktDataManager
from data.managers.transfermarkt_refresh_manager import TransfermarktRefreshManager
from data.managers.transfermarkt_runtime_manager import TransfermarktRuntimeManager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MatchWatcher")

# Retry intervals (in minutes)
RETRY_INTERVALS = [10, 30, 60, 120, 180, 240, 300, 360, 420, 480, 540, 600] # up to 10h, then hourly

class MatchWatcher:
    def __init__(self):
        self.tm_manager = TransfermarktDataManager(auto_load=False)
        self.runtime = TransfermarktRuntimeManager()
        self.refresh_manager = TransfermarktRefreshManager()

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.utcnow()

    @staticmethod
    def _to_naive_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def _enqueue_job(
        self,
        session,
        *,
        player_id: str,
        next_attempt: datetime,
        job_type: str,
        priority: int,
        source: str,
        reason: str = "",
        fixture_id: int | None = None,
        season_id: str | None = None,
        details: dict | None = None,
    ) -> bool:
        existing_stmt = select(MatchUpdateQueue).where(
            and_(
                MatchUpdateQueue.player_id == player_id,
                MatchUpdateQueue.job_type == job_type,
                MatchUpdateQueue.status.in_(("PENDING", "DEFERRED")),
                MatchUpdateQueue.fixture_id.is_(fixture_id) if fixture_id is None else MatchUpdateQueue.fixture_id == fixture_id,
            )
        )
        existing = session.execute(existing_stmt).scalars().first()
        if existing:
            existing.priority = max(existing.priority or 0, priority)
            existing.next_attempt = min(existing.next_attempt, next_attempt)
            existing.source = source
            existing.reason = reason or existing.reason
            if season_id:
                existing.season_id = season_id
            if details:
                existing.details = details
            return False

        session.add(
            MatchUpdateQueue(
                fixture_id=fixture_id,
                player_id=player_id,
                job_type=job_type,
                priority=priority,
                source=source,
                reason=reason,
                season_id=season_id,
                details=details,
                status="PENDING",
                attempt_count=0,
                next_attempt=next_attempt,
            )
        )
        return True

    def _get_refresh_state(self, session, player_id: str) -> PlayerRefreshState:
        state = session.get(PlayerRefreshState, player_id)
        if state is None:
            state = PlayerRefreshState(player_id=player_id, tm_refresh_status="READY")
            session.add(state)
            session.flush()
        return state

    def _mark_refresh_state(
        self,
        session,
        player_id: str,
        *,
        ok: bool,
        last_match_seen_date: datetime | None = None,
        error: str | None = None,
        defer_until: datetime | None = None,
        include_profile: bool = False,
        status_override: str | None = None,
    ) -> None:
        state = self._get_refresh_state(session, player_id)
        now = self._utcnow()
        if ok:
            state.last_match_history_refresh_at = now
            if include_profile:
                state.last_profile_refresh_at = now
                state.last_season_stats_refresh_at = now
            if last_match_seen_date is not None:
                state.last_match_seen_date = self._to_naive_utc(last_match_seen_date)
            state.tm_refresh_status = "READY"
            state.tm_last_error = None
            state.tm_retry_after = None
        else:
            state.tm_refresh_status = status_override or ("DEFERRED" if defer_until else "FAILED")
            state.tm_last_error = (error or "")[:500] or None
            state.tm_retry_after = self._to_naive_utc(defer_until)

    def enqueue_current_season_bootstrap(self, days_ahead: int = 7) -> int:
        """Queue active current-season squad players, prioritising teams with upcoming fixtures."""
        session = SessionFactory()
        try:
            now = self._utcnow()
            horizon = now + timedelta(days=days_ahead)
            upcoming_fixtures = session.execute(
                select(Fixture).where(and_(Fixture.date_utc >= now, Fixture.date_utc <= horizon))
            ).scalars().all()
            priority_team_ids = {fix.home_team_id for fix in upcoming_fixtures} | {fix.away_team_id for fix in upcoming_fixtures}

            current_season = session.execute(select(Fixture.season_id).order_by(Fixture.date_utc.desc()).limit(1)).scalar_one_or_none()
            active_team_ids = set(
                session.execute(
                    select(Fixture.home_team_id).where(Fixture.season_id == current_season)
                ).scalars().all()
            ) | set(
                session.execute(
                    select(Fixture.away_team_id).where(Fixture.season_id == current_season)
                ).scalars().all()
            )
            if not active_team_ids:
                return 0

            players = session.execute(
                select(Player).where(
                    and_(
                        Player.current_team_id.in_(tuple(active_team_ids)),
                        Player.tm_id.is_not(None),
                    )
                )
            ).scalars().all()

            added = 0
            for player in players:
                state = session.get(PlayerRefreshState, player.id)
                last_refresh = self._to_naive_utc(state.last_match_history_refresh_at) if state else None
                if last_refresh and last_refresh >= now - timedelta(days=7):
                    continue
                priority = 80 if player.current_team_id in priority_team_ids else 40
                if self._enqueue_job(
                    session,
                    player_id=player.id,
                    next_attempt=now,
                    job_type="current_season_bootstrap",
                    priority=priority,
                    source="weekly_refresh",
                    reason="Current-season roster coverage",
                    season_id=current_season,
                ):
                    added += 1
            session.commit()
            return added
        finally:
            session.close()

    def enqueue_upcoming_opponents(self, days_ahead: int = 10) -> int:
        """Queue players from teams with upcoming fixtures for scouting coverage."""
        session = SessionFactory()
        try:
            now = self._utcnow()
            horizon = now + timedelta(days=days_ahead)
            fixtures = session.execute(
                select(Fixture).where(and_(Fixture.date_utc >= now, Fixture.date_utc <= horizon))
            ).scalars().all()
            team_ids = {fix.home_team_id for fix in fixtures} | {fix.away_team_id for fix in fixtures}
            if not team_ids:
                return 0

            players = session.execute(
                select(Player).where(and_(Player.current_team_id.in_(tuple(team_ids)), Player.tm_id.is_not(None)))
            ).scalars().all()
            added = 0
            for player in players:
                state = session.get(PlayerRefreshState, player.id)
                last_refresh = self._to_naive_utc(state.last_match_history_refresh_at) if state else None
                if last_refresh and last_refresh >= now - timedelta(days=5):
                    continue
                if self._enqueue_job(
                    session,
                    player_id=player.id,
                    next_attempt=now,
                    job_type="upcoming_opponent_refresh",
                    priority=90,
                    source="hkfa_upcoming",
                    reason=f"Upcoming fixture window {days_ahead}d",
                ):
                    added += 1
            session.commit()
            return added
        finally:
            session.close()

    def enqueue_user_priority_refresh(self) -> int:
        """Queue refreshes for players linked to users or agents."""
        session = SessionFactory()
        try:
            now = self._utcnow()
            players_stmt = (
                select(Player)
                .outerjoin(UserPlayerLink)
                .outerjoin(agent_player_links)
                .where(
                    and_(
                        Player.tm_id.is_not(None),
                        or_(UserPlayerLink.player_id.is_not(None), agent_player_links.c.player_id.is_not(None)),
                    )
                )
                .distinct()
            )
            players = session.execute(players_stmt).scalars().all()
            added = 0
            for player in players:
                state = session.get(PlayerRefreshState, player.id)
                last_profile_refresh = self._to_naive_utc(state.last_profile_refresh_at) if state else None
                if last_profile_refresh and last_profile_refresh >= now - timedelta(days=3):
                    continue
                if self._enqueue_job(
                    session,
                    player_id=player.id,
                    next_attempt=now,
                    job_type="user_priority_refresh",
                    priority=120,
                    source="weekly_refresh",
                    reason="User/agent priority player refresh",
                ):
                    added += 1
            session.commit()
            return added
        finally:
            session.close()

    def discover_finished_matches(self):
        """
        Looks for fixtures that finished in the last 48 hours but aren't in MatchHistory.
        Adds them to the update queue if not already there.
        """
        session = SessionFactory()
        try:
            now = self._utcnow()
            # Matches that started between 48h ago and 2h ago (assumed finished)
            lookback = now - timedelta(hours=48)
            min_finish = now - timedelta(minutes=115) 
            
            stmt = select(Fixture).where(
                and_(
                    Fixture.date_utc >= lookback,
                    Fixture.date_utc <= min_finish
                )
            )
            finished_fixtures = session.execute(stmt).scalars().all()
            
            new_entries = 0
            for fix in finished_fixtures:
                # Find ONLY players that are users or managed by agents in our app
                players_stmt = (
                    select(Player)
                    .outerjoin(UserPlayerLink)
                    .outerjoin(agent_player_links)
                    .where(
                        and_(
                            or_(Player.current_team_id == fix.home_team_id, Player.current_team_id == fix.away_team_id),
                            or_(UserPlayerLink.player_id.is_not(None), agent_player_links.c.player_id.is_not(None))
                        )
                    )
                    .distinct()
                )
                players = session.execute(players_stmt).scalars().all()
                
                for player in players:
                    if not player.tm_id: continue
                    
                    # Check if match already in history
                    fix_date_str = fix.date_utc.strftime("%Y-%m-%d")
                    history_exists = session.execute(
                        select(MatchHistory).where(
                            and_(
                                MatchHistory.player_id == player.id,
                                MatchHistory.date >= fix.date_utc - timedelta(hours=12),
                                MatchHistory.date <= fix.date_utc + timedelta(hours=12)
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if history_exists: continue
                    
                    # Check if already in queue
                    in_queue = session.execute(
                        select(MatchUpdateQueue).where(
                            and_(
                                MatchUpdateQueue.fixture_id == fix.id,
                                MatchUpdateQueue.player_id == player.id,
                                MatchUpdateQueue.status == "PENDING"
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if not in_queue:
                        # Add to queue
                        if self._enqueue_job(
                            session,
                            fixture_id=fix.id,
                            player_id=player.id,
                            next_attempt=self._to_naive_utc(fix.date_utc) + timedelta(minutes=125),
                            job_type="post_match_history",
                            priority=150,
                            source="watcher",
                            reason="Finished fixture awaiting Transfermarkt history",
                            season_id=fix.season_id,
                        ):
                            new_entries += 1
            
            session.commit()
            if new_entries > 0:
                logger.info(f"Added {new_entries} player-match tasks to the update queue.")
        finally:
            session.close()

    def process_queue(self):
        """
        Finds pending tasks whose next_attempt time has passed and tries to update them.
        """
        if self.runtime.should_skip_automatic_refresh():
            logger.warning("Transfermarkt is currently BLOCKED. Automatic refresh cycle skipped.")
            return
        session = SessionFactory()
        try:
            runtime_status = self.runtime.get_status()
            assisted_active = runtime_status.mode == "ASSISTED_ACTIVE"
            now = self._utcnow()
            base_conditions = and_(
                MatchUpdateQueue.status.in_(("PENDING", "DEFERRED")),
                MatchUpdateQueue.next_attempt <= now,
                or_(MatchUpdateQueue.retry_after.is_(None), MatchUpdateQueue.retry_after <= now),
            )
            task_limit = 1 if assisted_active else 10
            stmt = None
            if assisted_active:
                assisted_priority_stmt = (
                    select(MatchUpdateQueue)
                    .where(
                        and_(
                            base_conditions,
                            MatchUpdateQueue.job_type.in_(("post_match_history", "user_priority_refresh")),
                        )
                    )
                    .order_by(MatchUpdateQueue.priority.desc(), MatchUpdateQueue.next_attempt.asc())
                    .limit(task_limit)
                )
                tasks = session.execute(assisted_priority_stmt).scalars().all()
                if not tasks:
                    stmt = (
                        select(MatchUpdateQueue)
                        .where(
                            and_(
                                base_conditions,
                                MatchUpdateQueue.job_type != "current_season_bootstrap",
                            )
                        )
                        .order_by(MatchUpdateQueue.priority.desc(), MatchUpdateQueue.next_attempt.asc())
                        .limit(task_limit)
                    )
            else:
                stmt = (
                    select(MatchUpdateQueue)
                    .where(base_conditions)
                    .order_by(MatchUpdateQueue.priority.desc(), MatchUpdateQueue.next_attempt.asc())
                    .limit(task_limit)
                )

            if stmt is not None:
                tasks = session.execute(stmt).scalars().all()
            if not tasks:
                return

            logger.info(
                "Processing %s pending refresh tasks%s...",
                len(tasks),
                " in conservative assisted mode" if assisted_active else "",
            )
            
            # To avoid redundant scraping, group by Transfermarkt profile first.
            player_tasks = {}
            for t in tasks:
                player = session.get(Player, t.player_id)
                group_key = str(player.tm_id) if player and player.tm_id else t.player_id
                if group_key not in player_tasks:
                    player_tasks[group_key] = []
                player_tasks[group_key].append(t)
            
            consecutive_hard_blocks = 0
            hard_block_limit = 1 if assisted_active else 3
            for group_key, p_tasks in player_tasks.items():
                seed_task = p_tasks[0]
                p_id = seed_task.player_id
                player = session.get(Player, p_id)
                logger.info(f"Refreshing Transfermarkt for player {p_id} (group={group_key})...")
                job_types = {t.job_type for t in p_tasks}
                if "user_priority_refresh" in job_types:
                    mode = "user_priority_refresh"
                elif "current_season_bootstrap" in job_types:
                    mode = "current_season_bootstrap"
                elif "upcoming_opponent_refresh" in job_types:
                    mode = "upcoming_opponent_refresh"
                else:
                    mode = "post_match_history"
                success = self.refresh_manager.refresh_player(
                    p_id,
                    mode=mode,
                    player_name=player.name if player else "",
                    team=getattr(getattr(player, "current_team", None), "name", "") if player else "",
                )
                hard_http_status = self.refresh_manager.last_http_status
                hard_block_reason = self.refresh_manager.last_block_reason
                fresh_cache_hit = self.refresh_manager.last_result_source == "cache" and self.refresh_manager.last_cache_fresh
                latest_match = session.execute(
                    select(MatchHistory)
                    .where(MatchHistory.player_id == p_id)
                    .order_by(MatchHistory.date.desc())
                    .limit(1)
                ).scalar_one_or_none()
                latest_seen = self._to_naive_utc(latest_match.date) if latest_match else None
                
                # Update task statuses
                for t in p_tasks:
                    if t.job_type == "post_match_history" and t.fixture_id:
                        fix = session.get(Fixture, t.fixture_id)
                        fixture_date_utc = self._to_naive_utc(fix.date_utc) if fix else None
                        history_exists = session.execute(
                            select(MatchHistory).where(
                                and_(
                                    MatchHistory.player_id == t.player_id,
                                    MatchHistory.date >= fixture_date_utc - timedelta(hours=12),
                                    MatchHistory.date <= fixture_date_utc + timedelta(hours=12)
                                )
                            )
                        ).scalar_one_or_none()
                        completed = bool(history_exists)
                    else:
                        completed = bool(success)

                    if completed:
                        t.status = "COMPLETED"
                        t.tm_status = "READY"
                        logger.info(f"✓ Task completed for {t.player_id} ({t.job_type})")
                        self.runtime.record_success(
                            metadata={"player_id": t.player_id, "job_type": t.job_type}
                        )
                        self._mark_refresh_state(
                            session,
                            t.player_id,
                            ok=True,
                            last_match_seen_date=latest_seen,
                            include_profile=t.job_type in {"user_priority_refresh", "season_stats_refresh"},
                        )
                    elif hard_http_status == 405:
                        t.status = "FAILED"
                        t.tm_status = "BLOCKED"
                        t.last_attempt = now
                        t.retry_after = now + timedelta(hours=24)
                        self._mark_refresh_state(
                            session,
                            t.player_id,
                            ok=False,
                            error=hard_block_reason or f"HTTP 405 on {t.job_type}",
                            defer_until=t.retry_after,
                            status_override="BLOCKED",
                        )
                        self.runtime.record_failure(
                            reason=hard_block_reason or f"HTTP 405 on {t.job_type}",
                            hard_block=True,
                        )
                        logger.warning(f"❌ Hard TM failure (405) for {t.player_id} ({t.job_type}); not retrying in this cycle.")
                    elif fresh_cache_hit:
                        t.last_attempt = now
                        t.status = "DEFERRED"
                        t.tm_status = "READY"
                        t.next_attempt = now + timedelta(hours=12)
                        t.retry_after = t.next_attempt
                        self._mark_refresh_state(
                            session,
                            t.player_id,
                            ok=False,
                            error=f"Fresh cache hit for {t.job_type}",
                            defer_until=t.next_attempt,
                            status_override="READY",
                        )
                        logger.info(f"Fresh Transfermarkt cache already checked today for {t.player_id}; deferring until {t.next_attempt}.")
                    else:
                        t.attempt_count += 1
                        t.last_attempt = now
                        
                        if t.attempt_count >= len(RETRY_INTERVALS):
                            t.status = "FAILED"
                            t.tm_status = "FAILED"
                            self._mark_refresh_state(session, t.player_id, ok=False, error=f"Max retries for {t.job_type}")
                            logger.warning(f"❌ Task failed after max retries for {t.player_id}")
                        else:
                            minutes_to_wait = RETRY_INTERVALS[t.attempt_count]
                            t.next_attempt = now + timedelta(minutes=minutes_to_wait)
                            t.status = "DEFERRED"
                            t.tm_status = "DEFERRED"
                            t.retry_after = t.next_attempt
                            self._mark_refresh_state(
                                session,
                                t.player_id,
                                ok=False,
                                error=f"Deferred {t.job_type}",
                                defer_until=t.next_attempt,
                            )
                            logger.info(f"TM data not ready for {t.player_id}. Retry {t.attempt_count} scheduled at {t.next_attempt}")
                
                session.commit()
                if hard_http_status == 405:
                    consecutive_hard_blocks += 1
                    if consecutive_hard_blocks >= hard_block_limit:
                        logger.warning("Transfermarkt circuit breaker opened after %s consecutive hard blocks. Stopping this cycle early.", consecutive_hard_blocks)
                        break
                else:
                    consecutive_hard_blocks = 0
                # Sleep longer during assisted mode to reduce WAF pressure.
                time.sleep(6 if assisted_active else 2)
                
        finally:
            session.close()

    def run_once(self):
        """Single pass of discovery and processing."""
        self.discover_finished_matches()
        self.process_queue()

def main():
    parser = argparse.ArgumentParser(description="Background watcher for recently finished matches.")
    parser.add_argument("--once", action="store_true", help="Run a single discovery/processing cycle and exit.")
    args = parser.parse_args()

    init_db()
    watcher = MatchWatcher()
    logger.info("Match Watcher Daemon started.")

    if args.once:
        watcher.run_once()
        logger.info("Match Watcher single cycle completed.")
        return

    # Simple loop: check every 5 minutes
    try:
        while True:
            watcher.run_once()
            logger.debug("Cycle complete. Sleeping 5 minutes...")
            time.sleep(300)
    except KeyboardInterrupt:
        logger.info("Match Watcher Daemon stopped by user.")

if __name__ == "__main__":
    main()
