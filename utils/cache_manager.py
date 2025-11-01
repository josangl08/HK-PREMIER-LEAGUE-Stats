# ABOUTME: Advanced caching manager with TTL, invalidation, and metrics caching
# ABOUTME: Optimizes performance for expensive data operations and computations

"""
Advanced Cache Manager for HK Premier League Dashboard.

Features:
- Time-to-live (TTL) for cache entries
- Automatic cache invalidation
- Metrics caching (tactical, efficiency, percentiles)
- Cache statistics (hit rate, miss rate)
- Memory-efficient caching
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
import pandas as pd
from functools import wraps

logger = logging.getLogger(__name__)


class CacheEntry:
    """
    Represents a single cache entry with TTL support.
    """

    def __init__(self, data: Any, ttl_seconds: int = 3600):
        """
        Initialize cache entry.

        Args:
            data: The cached data
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        self.data = data
        self.created_at = datetime.now()
        self.ttl_seconds = ttl_seconds
        self.last_accessed = datetime.now()
        self.access_count = 0

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl_seconds == -1:  # Never expire
            return False
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiry_time

    def access(self) -> Any:
        """Access the cached data and update stats."""
        self.last_accessed = datetime.now()
        self.access_count += 1
        return self.data

    def get_age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return (datetime.now() - self.created_at).total_seconds()


class AdvancedCacheManager:
    """
    Advanced cache manager with TTL and invalidation logic.
    """

    def __init__(self):
        """Initialize cache manager."""
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'invalidations': 0
        }

    def get(
        self,
        key: str,
        default: Any = None
    ) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        if key not in self._cache:
            self._stats['misses'] += 1
            return default

        entry = self._cache[key]

        # Check if expired
        if entry.is_expired():
            logger.debug(f"Cache entry expired: {key}")
            del self._cache[key]
            self._stats['evictions'] += 1
            self._stats['misses'] += 1
            return default

        self._stats['hits'] += 1
        return entry.access()

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 3600
    ) -> None:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
                        Use -1 for no expiration
        """
        self._cache[key] = CacheEntry(value, ttl_seconds)
        logger.debug(
            f"Cache set: {key} (TTL: {ttl_seconds}s)"
        )

    def invalidate(self, key: str) -> bool:
        """
        Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate

        Returns:
            True if key was invalidated, False if not found
        """
        if key in self._cache:
            del self._cache[key]
            self._stats['invalidations'] += 1
            logger.debug(f"Cache invalidated: {key}")
            return True
        return False

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries matching a pattern.

        Args:
            pattern: Pattern to match (e.g., "season_2024-25_*")

        Returns:
            Number of entries invalidated
        """
        keys_to_delete = [
            key for key in self._cache.keys()
            if pattern in key
        ]

        for key in keys_to_delete:
            del self._cache[key]

        count = len(keys_to_delete)
        self._stats['invalidations'] += count
        logger.info(
            f"Cache pattern invalidated: {pattern} ({count} entries)"
        )
        return count

    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        self._stats['invalidations'] += count
        logger.info(f"Cache cleared ({count} entries)")

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of entries removed
        """
        keys_to_delete = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]

        for key in keys_to_delete:
            del self._cache[key]

        count = len(keys_to_delete)
        self._stats['evictions'] += count
        logger.debug(f"Expired entries cleaned: {count}")
        return count

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (
            self._stats['hits'] / total_requests
            if total_requests > 0 else 0
        )

        return {
            'total_entries': len(self._cache),
            'total_requests': total_requests,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate': f"{hit_rate * 100:.2f}%",
            'evictions': self._stats['evictions'],
            'invalidations': self._stats['invalidations']
        }

    def get_entry_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific cache entry.

        Args:
            key: Cache key

        Returns:
            Dictionary with entry info or None if not found
        """
        if key not in self._cache:
            return None

        entry = self._cache[key]
        return {
            'key': key,
            'created_at': entry.created_at.isoformat(),
            'last_accessed': entry.last_accessed.isoformat(),
            'access_count': entry.access_count,
            'age_seconds': entry.get_age_seconds(),
            'ttl_seconds': entry.ttl_seconds,
            'is_expired': entry.is_expired()
        }

    def get_all_keys(self) -> list:
        """Get list of all cache keys."""
        return list(self._cache.keys())


# Global cache instance
_global_cache = AdvancedCacheManager()


def get_cache() -> AdvancedCacheManager:
    """Get the global cache instance."""
    return _global_cache


def cached(ttl_seconds: int = 3600, key_prefix: str = ""):
    """
    Decorator for caching function results.

    Args:
        ttl_seconds: Time-to-live for cache entry
        key_prefix: Prefix for cache key

    Example:
        @cached(ttl_seconds=1800, key_prefix="league")
        def get_league_stats(season):
            # expensive computation
            return stats
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = "_".join(filter(None, key_parts))

            # Try to get from cache
            cache = get_cache()
            result = cache.get(cache_key)

            if result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return result

            # Compute result
            logger.debug(f"Cache miss: {cache_key}")
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(cache_key, result, ttl_seconds)

            return result
        return wrapper
    return decorator


def invalidate_cache_for_season(season: str) -> int:
    """
    Invalidate all cache entries for a specific season.

    Args:
        season: Season to invalidate (e.g., "2024-25")

    Returns:
        Number of entries invalidated
    """
    cache = get_cache()
    return cache.invalidate_pattern(f"season_{season}")


def warm_cache(
    data_manager,
    seasons: list,
    include_tactical: bool = True
) -> Dict[str, int]:
    """
    Warm cache with commonly used data.

    Args:
        data_manager: HongKongDataManager instance
        seasons: List of seasons to warm
        include_tactical: Include tactical analysis in warming

    Returns:
        Dictionary with warming stats
    """
    stats = {
        'seasons_warmed': 0,
        'entries_created': 0,
        'errors': 0
    }

    for season in seasons:
        try:
            # Load season data
            data_manager.refresh_data(season)

            # Warm league-level data
            data_manager.get_league_overview()
            stats['entries_created'] += 1

            # Warm team-level data
            teams = data_manager.get_available_teams()
            for team in teams:
                data_manager.get_team_overview(team)
                stats['entries_created'] += 1

            if include_tactical:
                # Warm tactical data
                data_manager.get_chart_data('league')
                stats['entries_created'] += 1

            stats['seasons_warmed'] += 1
            logger.info(f"Cache warmed for season: {season}")

        except Exception as e:
            logger.error(f"Error warming cache for {season}: {e}")
            stats['errors'] += 1

    return stats
