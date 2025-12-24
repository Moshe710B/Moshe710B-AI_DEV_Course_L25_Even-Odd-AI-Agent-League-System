"""
League Manager Agent - Entry point.

Manages player/referee registration, scheduling, and standings.
"""

import sys
import asyncio
from pathlib import Path

# Add SHARED to path for league_sdk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "SHARED"))

import uvicorn
from league_sdk import MCPServer, JsonLogger, get_config

from handlers import LeagueManagerHandlers
from scheduler import Scheduler
from standings import StandingsManager


class LeagueManager:
    """League Manager agent."""

    def __init__(self):
        """Initialize League Manager."""
        self.config = get_config()
        manager_config = self.config.agents.get("league_manager", {})

        self.host = manager_config.get("host", "127.0.0.1")
        self.port = manager_config.get("port", 8000)

        self.server = MCPServer("league_manager", "MANAGER", self.host, self.port)
        self.logger = JsonLogger("league_manager", "MANAGER")

        # Components
        self.standings = StandingsManager()
        self.scheduler = Scheduler()

        # State
        self.registered_players: dict[str, dict] = {}
        self.registered_referees: dict[str, dict] = {}
        self.player_counter = 0
        self.referee_counter = 0
        self.league_started = False
        self._start_task = None

        # Handlers
        self.handlers = LeagueManagerHandlers(self)
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register message handlers."""
        self.server.register_handler(
            "LEAGUE_REGISTER_REQUEST",
            self.handlers.handle_player_registration,
        )
        self.server.register_handler(
            "REFEREE_REGISTER_REQUEST",
            self.handlers.handle_referee_registration,
        )
        self.server.register_handler(
            "MATCH_RESULT_REPORT",
            self.handlers.handle_match_result,
        )
        self.server.register_handler(
            "LEAGUE_QUERY",
            self.handlers.handle_query,
        )

    async def check_and_start_league(self) -> None:
        """Check if conditions are met to start the league."""
        # Cancel existing start task if any
        if self._start_task and not self._start_task.done():
            self._start_task.cancel()
            try:
                await self._start_task
            except asyncio.CancelledError:
                pass

        league_config = self.config.league
        min_players = league_config.get("auto_start", {}).get("min_players_to_start", 4)
        min_referees = league_config.get("min_referees", 1)

        if (
            len(self.registered_players) >= min_players
            and len(self.registered_referees) >= min_referees
            and not self.league_started
        ):
            wait_time = league_config.get("auto_start", {}).get(
                "wait_after_min_players_seconds", 10
            )
            # Create new task
            self._start_task = asyncio.create_task(self._delayed_start(wait_time))

    async def _delayed_start(self, wait_time: int) -> None:
        """Delayed start after countdown."""
        self.logger.info(
            "LEAGUE_READY",
            f"Minimum players/referees met. Starting league in {wait_time}s",
            players=len(self.registered_players),
            referees=len(self.registered_referees),
        )
        league_config = self.config.league
        min_players = league_config.get("auto_start", {}).get("min_players_to_start", 4)
        min_referees = league_config.get("min_referees", 1)

        print(f"\n⏰ League will start in {wait_time} seconds...")
        print(f"   Players registered: {len(self.registered_players)}/{min_players}")
        print(f"   Referees registered: {len(self.registered_referees)}/{min_referees}")
        print(f"   Waiting for more players to join...\n")

        await asyncio.sleep(wait_time)

        print(f"\n🏁 Starting league with {len(self.registered_players)} players!\n")
        await self.start_league()

    async def start_league(self) -> None:
        """Start the league."""
        if self.league_started:
            return

        self.league_started = True
        self.logger.info("LEAGUE_START", "League starting")

        player_ids = list(self.registered_players.keys())
        self.scheduler.generate_schedule(player_ids)

        # Start first round
        await self.handlers.start_round()

    def run(self) -> None:
        """Run the League Manager server."""
        league_config = self.config.league
        min_players = league_config.get("auto_start", {}).get("min_players_to_start", 4)
        wait_time = league_config.get("auto_start", {}).get("wait_after_min_players_seconds", 60)

        print("=" * 60)
        print("    Even/Odd League Manager")
        print("=" * 60)
        print(f"  Host:          {self.host}")
        print(f"  Port:          {self.port}")
        print(f"  Endpoint:      http://{self.host}:{self.port}/mcp")
        print("=" * 60)
        print(f"  Waiting for:   {min_players} players + 1 referee")
        print(f"  Auto-start:    {wait_time}s after minimum met")
        print("=" * 60)

        self.logger.info("STARTUP", "League Manager starting")
        uvicorn.run(self.server.app, host=self.host, port=self.port)


if __name__ == "__main__":
    manager = LeagueManager()
    manager.run()
