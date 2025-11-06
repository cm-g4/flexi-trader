"""Rate limiting service for Telegram messages and channel operations."""

from datetime import date, datetime, timezone, timedelta
from typing import Dict, Optional, Tuple
from collections import defaultdict

from app.exceptions import RateLimitError
from app.logging_config import logger

class RateLimiterService:
    """
    Rate limiting service for message processing.
    
    Supports:
    - Global rate limiting (all messages)
    - Per-channel rate limiting
    - Per-user rate limiting
    - Configurable time windows
    
    Uses in-memory tracking with sliding window algorithm.
    """

    def __init__(
        self,
        global_rate_limit: int = 60,
        channel_rate_limit: int = 30,
        user_rate_limit: int = 100,
        window_size_seconds: int = 60,
    ):
        """
        Initialize rate limiter.
        
        Args:
            global_rate_limit: Messages per window globally
            channel_rate_limit: Messages per window per channel
            user_rate_limit: Messages per window per user
            window_size_seconds: Time window in seconds
        """
        self.global_rate_limit = global_rate_limit
        self.channel_rate_limit = channel_rate_limit
        self.user_rate_limit = user_rate_limit
        self.window_size_seconds = window_size_seconds

        self.global_timestamps = list[datetime] = []
        self.channel_timestamps = Dict[str, list[datetime]] = defaultdict(list)
        self.user_timestamps = Dict[str, list[datetime]] = defaultdict(list)


    def _cleanup_old_timestamps(
        self, timestamps: list[datetime], now: datetime
    ) -> None:
        """
        Remove timestamps outside the window.
        
        Args:
            timestamps: List to clean
            now: Current time reference
        """
        cutoff = now - self.window_size
        # Remove entries older than window
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)

    def _is_within_limit(
        self, timestamps: list[datetime], limit: int, now: datetime
    ) -> bool:
        """
        Check if count is within limit.
        
        Args:
            timestamps: List of timestamps
            limit: Rate limit threshold
            now: Current time
            
        Returns:
            True if within limit, False otherwise
        """
        self._cleanup_old_timestamps(timestamps, now)
        return len(timestamps) < limit


    def check_global_rate_limit(self) ->  Tuple[bool, Optional[int]]:
        """
        Check if global rate limit is exceeded.
        
        Args:
            (none)
        
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = datetime.now(timezone.utc)
        
        if self._is_within_limit(
            self.global_timestamps, self.global_rate_limit, now
        ):
            return True, None
        
        # Calculate retry time
        oldest = self.global_timestamps[0] if self.global_timestamps else now
        retry_after = int((oldest + self.window_size - now).total_seconds()) + 1
        
        logger.warning(
            f"Global rate limit exceeded. Retry after {retry_after}s"
        )
        return False, retry_after


    def check_channel_rate_limit(
        self, channel_id: str
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if channel rate limit is exceeded.
        
        Args:
            channel_id: Channel identifier
        
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = datetime.now(timezone.utc)
        timestamps = self.channel_timestamps[channel_id]
        
        if self._is_within_limit(timestamps, self.channel_rate_limit, now):
            return True, None
        
        # Calculate retry time
        oldest = timestamps[0] if timestamps else now
        retry_after = int((oldest + self.window_size - now).total_seconds()) + 1
        
        logger.warning(
            f"Channel rate limit exceeded: {channel_id}. "
            f"Retry after {retry_after}s"
        )
        return False, retry_after
    
    def check_user_rate_limit(
        self, user_id: str
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if user rate limit is exceeded.
        
        Args:
            user_id: User identifier
        
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = datetime.now(timezone.utc)
        timestamps = self.user_timestamps[user_id]
        
        if self._is_within_limit(timestamps, self.user_rate_limit, now):
            return True, None
        
        # Calculate retry time
        oldest = timestamps[0] if timestamps else now
        retry_after = int((oldest + self.window_size - now).total_seconds()) + 1
        
        logger.warning(
            f"User rate limit exceeded: {user_id}. "
            f"Retry after {retry_after}s"
        )
        return False, retry_after

    def check_all_limits(
        self, channel_id: str, user_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check all rate limits at once.
        
        Args:
            channel_id: Channel identifier
            user_id: User identifier (optional)
        
        Returns:
            Tuple of (is_allowed, reason_if_denied)
        """
        # Check global limit
        global_ok, retry_global = self.check_global_rate_limit()
        if not global_ok:
            return False, f"Global rate limit exceeded. Retry in {retry_global}s"
        
        # Check channel limit
        channel_ok, retry_channel = self.check_channel_rate_limit(channel_id)
        if not channel_ok:
            return False, f"Channel rate limit exceeded. Retry in {retry_channel}s"
        
        # Check user limit if provided
        if user_id:
            user_ok, retry_user = self.check_user_rate_limit(user_id)
            if not user_ok:
                return False, f"User rate limit exceeded. Retry in {retry_user}s"
        
        return True, None


    def record_message(
        self, channel_id: str, user_id: Optional[str] = None
    ) -> None:
        """
        Record a message for rate limiting.
        
        Call this after successfully processing a message.
        
        Args:
            channel_id: Channel identifier
            user_id: User identifier (optional)
        """
        now = datetime.now(timezone.utc)
        
        # Record globally
        self.global_timestamps.append(now)
        self._cleanup_old_timestamps(self.global_timestamps, now)
        
        # Record per channel
        self.channel_timestamps[channel_id].append(now)
        self._cleanup_old_timestamps(self.channel_timestamps[channel_id], now)
        
        # Record per user if provided
        if user_id:
            self.user_timestamps[user_id].append(now)
            self._cleanup_old_timestamps(self.user_timestamps[user_id], now)


    def get_remaining_quota(
        self, channel_id: str, user_id: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Get remaining quota for limits.
        
        Args:
            channel_id: Channel identifier
            user_id: User identifier (optional)
        
        Returns:
            Dict with remaining quota for each limit
        """
        now = datetime.now(timezone.utc)
        
        # Cleanup and count
        self._cleanup_old_timestamps(self.global_timestamps, now)
        self._cleanup_old_timestamps(self.channel_timestamps[channel_id], now)
        if user_id:
            self._cleanup_old_timestamps(self.user_timestamps[user_id], now)
        
        result = {
            "global": max(0, self.global_rate_limit - len(self.global_timestamps)),
            "channel": max(
                0,
                self.channel_rate_limit - len(self.channel_timestamps[channel_id]),
            ),
        }
        
        if user_id:
            result["user"] = max(
                0, self.user_rate_limit - len(self.user_timestamps[user_id])
            )
        
        return result

    def reset_channel_limit(self, channel_id: str) -> None:
        """
        Reset rate limit for a specific channel (admin operation).
        
        Args:
            channel_id: Channel identifier
        """
        self.channel_timestamps[channel_id] = []
        logger.info(f"Rate limit reset for channel: {channel_id}")

    def reset_user_limit(self, user_id: str) -> None:
        """
        Reset rate limit for a specific user (admin operation).
        
        Args:
            user_id: User identifier
        """
        self.user_timestamps[user_id] = []
        logger.info(f"Rate limit reset for user: {user_id}")

    def reset_all(self) -> None:
        """
        Reset all rate limits (admin operation).
        
        WARNING: This resets all rate limiting.
        """
        self.global_timestamps = []
        self.channel_timestamps.clear()
        self.user_timestamps.clear()
        logger.warning("All rate limits have been reset")

    def get_stats(self) -> Dict[str, int]:
        """
        Get rate limiting statistics.
        
        Returns:
            Dictionary with stats
        """
        return {
            "tracked_channels": len(self.channel_timestamps),
            "tracked_users": len(self.user_timestamps),
            "global_messages_in_window": len(self.global_timestamps),
            "total_timestamps": (
                len(self.global_timestamps)
                + sum(len(ts) for ts in self.channel_timestamps.values())
                + sum(len(ts) for ts in self.user_timestamps.values())
            ),
        }

# Global singleton instance
_rate_limiter: Optional[RateLimiterService] = None

def get_rate_limiter(
    global_rate: int = 60,
    channel_rate: int = 30,
    user_rate: int = 100,
) -> RateLimiterService:
    """
    Get or create rate limiter singleton.
    
    Args:
        global_rate: Global rate limit
        channel_rate: Per-channel rate limit
        user_rate: Per-user rate limit
    
    Returns:
        RateLimiterService instance
    """
    global _rate_limiter
    
    if _rate_limiter is None:
        _rate_limiter = RateLimiterService(
            global_rate_limit=global_rate,
            channel_rate_limit=channel_rate,
            user_rate_limit=user_rate,
        )
        logger.info(
            f"Rate limiter initialized: "
            f"global={global_rate}, channel={channel_rate}, user={user_rate}"
        )
    
    return _rate_limiter


__all__ = ["RateLimiterService", "get_rate_limiter"]