"""
In-memory session store for multi-turn conversation history.
Each session holds up to MAX_TURNS exchanges (user + assistant pairs).
Sessions expire after EXPIRY_MINUTES minutes of inactivity.
"""
import threading
import time
from collections import OrderedDict

MAX_TURNS = 10        # max user/assistant pairs to keep
EXPIRY_MINUTES = 60   # sessions older than this are evicted


class SessionStore:
    def __init__(self):
        self._sessions: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()

    def get_history(self, session_id: str) -> list[dict]:
        """Return conversation history as list of {role, content} dicts."""
        with self._lock:
            self._evict_expired()
            session = self._sessions.get(session_id)
            if not session:
                return []
            session["last_access"] = time.time()
            return list(session["history"])

    def append(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        """Append a user/assistant exchange to the session."""
        with self._lock:
            self._evict_expired()
            if session_id not in self._sessions:
                self._sessions[session_id] = {
                    "history": [],
                    "created_at": time.time(),
                    "last_access": time.time(),
                }
            session = self._sessions[session_id]
            session["history"].append({"role": "user",      "content": user_msg})
            session["history"].append({"role": "assistant", "content": assistant_msg})
            # Trim to MAX_TURNS pairs (2 messages per turn)
            if len(session["history"]) > MAX_TURNS * 2:
                session["history"] = session["history"][-(MAX_TURNS * 2):]
            session["last_access"] = time.time()

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def _evict_expired(self) -> None:
        cutoff = time.time() - EXPIRY_MINUTES * 60
        expired = [sid for sid, s in self._sessions.items() if s["last_access"] < cutoff]
        for sid in expired:
            del self._sessions[sid]


# Singleton shared across all requests
session_store = SessionStore()
