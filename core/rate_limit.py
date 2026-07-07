"""
core/rate_limit.py
Login rate limiting and account lockout for Roleigh QuanTrader.
Prevents brute force attacks by limiting login attempts.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Tuple


class LoginRateLimiter:
    """Thread-safe login rate limiter.
    
    Limits login attempts per username:
    - Max 5 attempts before lockout
    - 15-minute lockout period
    - Auto-unlock after timeout
    - Successful login resets counter
    """

    MAX_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15

    def __init__(self):
        self._attempts: Dict[str, int] = {}
        self._lockout_until: Dict[str, datetime] = {}
        self._lock = threading.Lock()

    def _clean_expired_lockouts(self):
        """Remove lockouts that have expired."""
        now = datetime.now()
        expired = [username for username, until in self._lockout_until.items() if until <= now]
        for username in expired:
            del self._lockout_until[username]
            self._attempts.pop(username, None)

    def check_login_allowed(self, username: str) -> Tuple[bool, str]:
        """Check if a login attempt is allowed for this username.
        
        Args:
            username: The username attempting to log in
            
        Returns:
            Tuple of (allowed: bool, message: str)
        """
        with self._lock:
            self._clean_expired_lockouts()

            if username not in self._attempts:
                return True, "Login allowed"

            if username in self._lockout_until:
                lockout_time = self._lockout_until[username]
                now = datetime.now()
                if now >= lockout_time:
                    # Lockout has expired
                    del self._lockout_until[username]
                    self._attempts.pop(username, None)
                    return True, "Login allowed"
                else:
                    remaining = lockout_time - now
                    minutes = int(remaining.total_seconds() / 60) + 1
                    return False, f"Account temporarily locked. Try again in {minutes} minute{'s' if minutes != 1 else ''}."

            attempts = self._attempts.get(username, 0)
            if attempts >= self.MAX_ATTEMPTS:
                # This shouldn't happen if lockout is set, but just in case
                lockout_until = datetime.now() + timedelta(minutes=self.LOCKOUT_MINUTES)
                self._lockout_until[username] = lockout_until
                return False, f"Too many failed attempts. Account locked for {self.LOCKOUT_MINUTES} minutes."

            return True, "Login allowed"

    def record_login_attempt(self, username: str, success: bool) -> None:
        """Record the result of a login attempt.
        
        Args:
            username: The username that attempted to log in
            success: Whether the login was successful
        """
        with self._lock:
            self._clean_expired_lockouts()

            if success:
                # Successful login — reset everything
                self._attempts.pop(username, None)
                self._lockout_until.pop(username, None)
            else:
                # Failed login — increment counter
                current = self._attempts.get(username, 0)
                self._attempts[username] = current + 1

                if self._attempts[username] >= self.MAX_ATTEMPTS:
                    # Lock the account
                    self._lockout_until[username] = datetime.now() + timedelta(minutes=self.LOCKOUT_MINUTES)

    def get_remaining_attempts(self, username: str) -> int:
        """Get the number of remaining login attempts for a username.
        
        Args:
            username: The username to check
            
        Returns:
            Number of remaining attempts (MAX_ATTEMPTS minus current failed attempts)
        """
        with self._lock:
            self._clean_expired_lockouts()

            if username in self._lockout_until:
                return 0

            attempts = self._attempts.get(username, 0)
            return max(0, self.MAX_ATTEMPTS - attempts)

    def get_lockout_time_remaining(self, username: str) -> str:
        """Get a human-readable string of time remaining on a lockout.
        
        Args:
            username: The username to check
            
        Returns:
            String like "12 minutes" or "Not locked"
        """
        with self._lock:
            if username not in self._lockout_until:
                return "Not locked"

            remaining = self._lockout_until[username] - datetime.now()
            if remaining.total_seconds() <= 0:
                return "Not locked"

            minutes = int(remaining.total_seconds() / 60) + 1
            return f"{minutes} minute{'s' if minutes != 1 else ''}"

    def reset_user(self, username: str) -> None:
        """Manually reset a user's login attempts and lockout.
        
        Useful for admin override or after password reset.
        
        Args:
            username: The username to reset
        """
        with self._lock:
            self._attempts.pop(username, None)
            self._lockout_until.pop(username, None)

    def get_stats(self) -> Dict:
        """Get current rate limiter stats for admin monitoring.
        
        Returns:
            Dict with current stats
        """
        with self._lock:
            self._clean_expired_lockouts()
            return {
                "tracked_users": len(self._attempts),
                "locked_users": len(self._lockout_until),
                "max_attempts": self.MAX_ATTEMPTS,
                "lockout_minutes": self.LOCKOUT_MINUTES,
                "locked_usernames": list(self._lockout_until.keys()),
            }


# Global instance — import this in app.py and database.py
rate_limiter = LoginRateLimiter()
