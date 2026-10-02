"""Semantic behavior states (spec rev1 §11) + a tiny state machine."""
from __future__ import annotations

from enum import Enum


class State(str, Enum):
    IDLE = "idle"
    CURIOUS = "curious"
    LISTENING = "listening"
    READING = "reading"
    THINKING = "thinking"
    PLANNING = "planning"
    SEARCHING = "searching"
    BUILDING = "building"
    CODING = "coding"
    TESTING = "testing"
    WORKING = "working"
    WAITING = "waiting"
    CONFUSED = "confused"
    CONCERNED = "concerned"
    CELEBRATING = "celebrating"
    FRUSTRATED = "frustrated"
    RECOVERING = "recovering"
    SLEEPING = "sleeping"
    URGENT = "urgent"
    CALLING_USER = "calling_user"
    TRAVELING = "traveling"
    OBSERVING = "observing"


class StateMachine:
    def __init__(self, initial: State = State.IDLE) -> None:
        self.state: State = initial

    def set(self, s: State) -> State:
        old, self.state = self.state, s
        return old
