"""
Parity choice handling for the Referee.

Handles collecting parity choices and determining winners.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "SHARED"))

from league_sdk import MCPClient
from league_sdk.game_rules import EvenOddGame

if TYPE_CHECKING:
    from main import RefereeAgent


class ParityHandler:
    """Handles parity choice collection and winner determination."""

    def __init__(self, referee: "RefereeAgent"):
        """Initialize handler."""
        self.referee = referee
        self.logger = referee.logger
        self.game = EvenOddGame()

    async def request_parity_choices(self, match_state: dict) -> bool:
        """
        Request parity choices from both players.

        Returns:
            True if both players responded within deadline
        """
        match_id = match_state["match_id"]
        deadline = (datetime.now(timezone.utc) + timedelta(seconds=30)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        client = MCPClient(
            f"referee:{self.referee.referee_id}",
            self.referee.auth_token,
        )

        async def request_choice(player: dict, is_player_a: bool) -> bool:
            try:
                self.logger.info(
                    "REQUESTING_PARITY",
                    f"Requesting parity from {player['id']}",
                    player_id=player['id'],
                    endpoint=player['endpoint'],
                )
                response = await client.send(
                    player["endpoint"],
                    "CHOOSE_PARITY_CALL",
                    {"match_id": match_id, "deadline": deadline},
                )

                # Log the raw response for debugging
                self.logger.info(
                    "RAW_RESPONSE",
                    f"Received response from {player['id']}",
                    player_id=player['id'],
                    response=str(response)[:200],  # Limit to 200 chars
                )

                # Extract parity choice from response
                result = response.get("result", {})
                parity_choice = result.get("parity_choice")

                if parity_choice in ("even", "odd"):
                    # Store the choice in match state
                    if is_player_a:
                        match_state["player_a_choice"] = parity_choice
                    else:
                        match_state["player_b_choice"] = parity_choice

                    self.logger.info(
                        "CHOICE_RECEIVED",
                        f"Player {player['id']} chose {parity_choice}",
                        match_id=match_id,
                        choice=parity_choice,
                    )
                    return True
                else:
                    self.logger.error(
                        "INVALID_CHOICE",
                        f"Player {player['id']} returned invalid choice: {parity_choice}",
                        match_id=match_id,
                        response=result,
                    )
                    return False
            except Exception as e:
                self.logger.error(
                    "CHOICE_REQUEST_FAILED",
                    f"Failed to get choice from {player['id']}: {e}",
                    player_id=player["id"],
                    error=str(e),
                )
                return False

        tasks = [
            request_choice(match_state["player_a"], True),
            request_choice(match_state["player_b"], False),
        ]

        results = await asyncio.gather(*tasks)
        await client.close()

        # Check if both players provided valid choices
        return all(results)

    def determine_winner(self, match_state: dict) -> dict:
        """Determine match winner based on parity choices."""
        outcome = self.game.determine_match_outcome(
            match_state["player_a"]["id"],
            match_state["player_a_choice"],
            match_state["player_b"]["id"],
            match_state["player_b_choice"],
        )

        self.logger.match_event(
            match_state["match_id"],
            f"Result: {outcome.winner_id or 'DRAW'}",
        )

        return {
            "match_id": match_state["match_id"],
            "round_id": match_state["round_id"],
            "player_a_id": match_state["player_a"]["id"],
            "player_b_id": match_state["player_b"]["id"],
            "drawn_number": outcome.drawn_number,
            "player_a_choice": outcome.player_a_choice,
            "player_b_choice": outcome.player_b_choice,
            "player_a_result": outcome.player_a_result,
            "player_b_result": outcome.player_b_result,
            "winner_id": outcome.winner_id,
        }
