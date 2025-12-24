"""
Game orchestration logic for the Referee.

Handles match flow: invitation, parity collection, winner determination.
"""

from typing import TYPE_CHECKING

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "SHARED"))

import asyncio
from league_sdk import MCPClient
from invitation_handler import InvitationHandler
from parity_handler import ParityHandler

if TYPE_CHECKING:
    from main import RefereeAgent


class GameOrchestrator:
    """Orchestrates match flow."""

    def __init__(self, referee: "RefereeAgent"):
        """Initialize orchestrator."""
        self.referee = referee
        self.logger = referee.logger
        self.invitation_handler = InvitationHandler(referee)
        self.parity_handler = ParityHandler(referee)

    async def conduct_match(
        self,
        match_id: str,
        round_id: str,
        player_a: dict,
        player_b: dict,
    ) -> dict:
        """
        Conduct a complete match.

        Args:
            match_id: Match identifier
            round_id: Round identifier
            player_a: Player A info with endpoint
            player_b: Player B info with endpoint

        Returns:
            Match result
        """
        self.logger.match_event(match_id, "Match starting")

        # Store match state
        match_state = {
            "match_id": match_id,
            "round_id": round_id,
            "player_a": player_a,
            "player_b": player_b,
            "player_a_joined": False,
            "player_b_joined": False,
            "player_a_choice": None,
            "player_b_choice": None,
        }
        self.referee.active_matches[match_id] = match_state

        try:
            # Step 1: Send invitations
            join_ok = await self.invitation_handler.send_invitations(match_state)
            if not join_ok:
                return self._technical_loss_result(match_state, "join_timeout")

            # Step 2: Request parity choices
            choices_ok = await self.parity_handler.request_parity_choices(match_state)
            if not choices_ok:
                return self._technical_loss_result(match_state, "choice_timeout")

            # Step 3: Determine winner
            result = self.parity_handler.determine_winner(match_state)

            # Step 4: Send game over to players
            await self._send_game_over(match_state, result)

            return result

        finally:
            # Cleanup
            self.referee.active_matches.pop(match_id, None)

    async def _send_game_over(self, match_state: dict, result: dict) -> None:
        """Send game over to both players."""
        match_id = match_state["match_id"]
        self.logger.match_event(match_id, "Sending GAME_OVER to players")

        # Create MCP client for sending messages
        client = MCPClient(
            f"referee:{self.referee.referee_id}",
            self.referee.auth_token,
        )

        try:
            # Prepare GAME_OVER message for player A
            game_over_a = {
                "match_id": match_id,
                "drawn_number": result["drawn_number"],
                "your_choice": result["player_a_choice"],
                "opponent_choice": result["player_b_choice"],
                "result": result["player_a_result"],
                "points_earned": 3 if result["player_a_result"] == "WIN" else (1 if result["player_a_result"] == "DRAW" else 0),
            }

            # Prepare GAME_OVER message for player B
            game_over_b = {
                "match_id": match_id,
                "drawn_number": result["drawn_number"],
                "your_choice": result["player_b_choice"],
                "opponent_choice": result["player_a_choice"],
                "result": result["player_b_result"],
                "points_earned": 3 if result["player_b_result"] == "WIN" else (1 if result["player_b_result"] == "DRAW" else 0),
            }

            # Send to both players concurrently
            await asyncio.gather(
                client.send(
                    match_state["player_a"]["endpoint"],
                    "GAME_OVER",
                    game_over_a,
                ),
                client.send(
                    match_state["player_b"]["endpoint"],
                    "GAME_OVER",
                    game_over_b,
                ),
                return_exceptions=True,
            )

            self.logger.match_event(match_id, "GAME_OVER sent to both players")

        except Exception as e:
            self.logger.error("GAME_OVER_SEND_FAILED", str(e), match_id=match_id)
        finally:
            await client.close()

    def _technical_loss_result(self, match_state: dict, reason: str) -> dict:
        """Create technical loss result."""
        self.logger.error(
            "TECHNICAL_LOSS",
            f"Match {match_state['match_id']} ended in technical loss: {reason}",
            match_id=match_state["match_id"],
            reason=reason,
        )
        return {
            "match_id": match_state["match_id"],
            "round_id": match_state["round_id"],
            "player_a_id": match_state["player_a"]["id"],
            "player_b_id": match_state["player_b"]["id"],
            "error": reason,
            "player_a_result": "TECHNICAL_LOSS",
            "player_b_result": "TECHNICAL_LOSS",
        }
