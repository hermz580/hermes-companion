"""Personality memory: the companion learns your rhythm, never your content.

Stored locally (``%LOCALAPPDATA%\\hermes-companion\\personality.json`` or
``~/.hermes-companion``) and made only of counts and dates:

* activity per hour of the day (24 counters),
* days seen, session starts, breaks taken,
* typical session length.

From that it derives a few gentle traits - night owl or early bird, steady
or bursty, how talkative to be - and moments worth marking: the first hello
of the day, welcome back after a long break, a stretch reminder when you've
gone longer than usual. Delete the file to make it forget everything.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path


def default_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "hermes-companion" if base else Path.home() / ".hermes-companion"
    return root / "personality.json"


@dataclass
class Personality:
    path: Path | None = None
    hours: list[int] = field(default_factory=lambda: [0] * 24)
    days: list[str] = field(default_factory=list)
    sessions: int = 0
    breaks: int = 0
    session_minutes: list[float] = field(default_factory=list)
    last_active: float = 0.0
    session_start: float = 0.0
    _stretch_said: bool = False

    BREAK_S = 20 * 60

    # -- persistence --------------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> "Personality":
        path = path or default_path()
        p = cls(path=path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            p.hours = [int(v) for v in raw.get("hours", [0] * 24)][:24] or [0] * 24
            p.days = [str(d) for d in raw.get("days", [])][-60:]
            p.sessions = int(raw.get("sessions", 0))
            p.breaks = int(raw.get("breaks", 0))
            p.session_minutes = [float(m) for m in raw.get("session_minutes", [])][-30:]
            p.last_active = float(raw.get("last_active", 0.0))
        except (OSError, ValueError, TypeError):
            pass
        return p

    def save(self) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({
                "hours": self.hours, "days": self.days[-60:], "sessions": self.sessions,
                "breaks": self.breaks, "session_minutes": self.session_minutes[-30:],
                "last_active": self.last_active,
            }), encoding="utf-8")
        except OSError:
            pass

    # -- learning -------------------------------------------------------------
    def start(self, now: float | None = None) -> str | None:
        """Call once at launch; returns a greeting worth saying, if any."""
        now = time.time() if now is None else now
        today = time.strftime("%Y-%m-%d", time.localtime(now))
        first_today = today not in self.days
        long_away = self.last_active and now - self.last_active > 6 * 3600
        if first_today:
            self.days.append(today)
        self.sessions += 1
        self.session_start = now
        hour = time.localtime(now).tm_hour
        self.save()
        if first_today and len(self.days) == 1:
            return "Hello! I'm here when you need me."
        if first_today:
            part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
            return f"Good {part}! Day {len(self.days)} together."
        if long_away:
            return "Welcome back!"
        return None

    def activity(self, now: float | None = None) -> str | None:
        """Call on user activity; returns something to say, if anything."""
        now = time.time() if now is None else now
        said = None
        if self.last_active and now - self.last_active > self.BREAK_S:
            self.breaks += 1
            if self.session_start:
                self.session_minutes.append((self.last_active - self.session_start) / 60)
            self.session_start = now
            self._stretch_said = False
            said = "Welcome back - nice break."
        self.hours[time.localtime(now).tm_hour] += 1
        self.last_active = now
        usual = self.usual_session_minutes()
        if usual and not self._stretch_said and self.session_start and \
                (now - self.session_start) / 60 > usual * 1.25 + 10:
            self._stretch_said = True
            said = "Longer than usual today - time for a stretch?"
        if sum(self.hours) % 50 == 0:
            self.save()
        return said

    # -- traits ---------------------------------------------------------------------
    def usual_session_minutes(self) -> float | None:
        recent = [m for m in self.session_minutes[-10:] if m > 5]
        return sorted(recent)[len(recent) // 2] if len(recent) >= 3 else None

    def chronotype(self) -> str:
        total = sum(self.hours)
        if total < 30:
            return "getting to know you"
        night = sum(self.hours[h] for h in (22, 23, 0, 1, 2, 3))
        early = sum(self.hours[h] for h in (5, 6, 7, 8))
        if night / total > 0.3:
            return "night owl"
        if early / total > 0.25:
            return "early bird"
        return "daytime"

    def curiosity_bias(self) -> float:
        """Negative = more reactive. Busy-hour users get a calmer companion."""
        total = sum(self.hours)
        if total < 30:
            return 0.0
        peak = max(self.hours) / total
        return 0.08 if peak > 0.2 else -0.04

    def summary(self) -> dict:
        return {"days": len(self.days), "sessions": self.sessions, "breaks": self.breaks,
                "chronotype": self.chronotype(),
                "usual_session_minutes": self.usual_session_minutes()}
