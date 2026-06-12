"""
Base Agent — shared functionality for all MACH-1 teams.
"""
from abc import ABC, abstractmethod
from typing import Optional
from utils.logger import get_logger
from utils.router import call_llm, call_llm_json
from utils.database import db


class BaseAgent(ABC):
    """Base class for all MACH-1 agent teams."""

    team_name: str = "base"

    def __init__(self):
        self.log = get_logger(f"mach1.{self.team_name}")
        self.db = db

    def ask(self, prompt: str, system: str = None, temperature: float = 0.7,
            max_tokens: int = 2048) -> Optional[str]:
        """Send a prompt to the team's LLM chain. Returns text or None."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        result = call_llm(
            team=self.team_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if result:
            return result["content"]
        return None

    def ask_json(self, prompt: str, system: str = None, temperature: float = 0.3,
                 max_tokens: int = 2048) -> Optional[dict]:
        """Send a prompt and parse JSON response. Returns dict or None."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        result = call_llm_json(
            team=self.team_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if result and result.get("parsed"):
            return result["parsed"]
        return None

    @abstractmethod
    def run_task(self, task: dict) -> dict:
        """
        Execute a task assigned by the CEO.

        Args:
            task: dict with at least 'description' key

        Returns:
            dict with 'success' bool and 'result' str
        """
        pass

    def get_status(self) -> dict:
        """Return current team status for CEO overview."""
        pending = self.db.get_tasks(team=self.team_name, status="queued")
        running = self.db.get_tasks(team=self.team_name, status="running")
        return {
            "team": self.team_name,
            "pending_tasks": len(pending),
            "running_tasks": len(running),
        }
