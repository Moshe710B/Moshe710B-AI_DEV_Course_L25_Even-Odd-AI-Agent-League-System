"""
Message handlers for the League Manager.
"""

import asyncio
from typing import Any, TYPE_CHECKING

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "SHARED"))

from league_sdk import (
    utc_now,
    generate_uuid,
    generate_token,
    MCPClient,
)

if TYPE_CHECKING:
    from main import LeagueManager


class LeagueManagerHandlers:
    """Message handlers for League Manager."""

    def __init__(self, manager: "LeagueManager"):
        """Initialize handlers."""
        self.manager = manager
        self.logger = manager.logger

    async def handle_player_registration(self, params: dict) -> dict:
        """Handle player registration request."""
        player_meta = params.get("player_meta", {})
        display_name = player_meta.get("display_name", "Unknown")
        endpoint = player_meta.get("contact_endpoint")

        # Extract player ID from sender (format: "player:P01")
        sender = params.get("sender", "")
        if ":" in sender:
            requested_id = sender.split(":")[-1]
            player_id = requested_id if requested_id.startswith("P") else f"P{self.manager.player_counter + 1:02d}"
        else:
            # Fallback to sequential ID if sender doesn't have expected format
            self.manager.player_counter += 1
            player_id = f"P{self.manager.player_counter:02d}"

        auth_token = generate_token()

        # Store registration
        self.manager.registered_players[player_id] = {
            "player_id": player_id,
            "display_name": display_name,
            "endpoint": endpoint,
            "auth_token": auth_token,
            "meta": player_meta,
        }

        # Register auth token so player can send authenticated messages
        self.manager.server.register_auth_token(f"player:{player_id}", auth_token)

        # Register in standings
        self.manager.standings.register_player(player_id, display_name)

        self.logger.info(
            "PLAYER_REGISTERED",
            f"Player {player_id} ({display_name}) registered",
            player_id=player_id,
        )

        # Print registration status
        total_players = len(self.manager.registered_players)
        total_referees = len(self.manager.registered_referees)
        print(f"✅ Player registered: {player_id} ({display_name})")
        print(f"   Total: {total_players} players, {total_referees} referees")

        # Check if we can start
        asyncio.create_task(self.manager.check_and_start_league())

        return self.manager.server.build_response(
            "LEAGUE_REGISTER_RESPONSE",
            conversation_id=params.get("conversation_id"),
            status="REGISTERED",
            player_id=player_id,
            auth_token=auth_token,
        )

    async def handle_referee_registration(self, params: dict) -> dict:
        """Handle referee registration request."""
        referee_meta = params.get("referee_meta", {})
        endpoint = referee_meta.get("contact_endpoint")

        # Assign referee ID
        self.manager.referee_counter += 1
        referee_id = f"REF{self.manager.referee_counter:02d}"
        auth_token = generate_token()

        # Store registration
        self.manager.registered_referees[referee_id] = {
            "referee_id": referee_id,
            "endpoint": endpoint,
            "auth_token": auth_token,
            "meta": referee_meta,
        }

        # Register auth token so referee can send authenticated messages
        self.manager.server.register_auth_token(f"referees:{referee_id}", auth_token)

        self.logger.info(
            "REFEREE_REGISTERED",
            f"Referee {referee_id} registered",
            referee_id=referee_id,
        )

        # Print registration status
        total_players = len(self.manager.registered_players)
        total_referees = len(self.manager.registered_referees)
        print(f"✅ Referee registered: {referee_id}")
        print(f"   Total: {total_players} players, {total_referees} referees")

        # Check if we can start
        asyncio.create_task(self.manager.check_and_start_league())

        return self.manager.server.build_response(
            "REFEREE_REGISTER_RESPONSE",
            conversation_id=params.get("conversation_id"),
            status="REGISTERED",
            referee_id=referee_id,
            auth_token=auth_token,
        )

    async def handle_match_result(self, params: dict) -> dict:
        """Handle match result report from referee."""
        match_id = params.get("match_id")
        player_a_id = params.get("player_a_id")
        player_b_id = params.get("player_b_id")
        player_a_result = params.get("player_a_result")
        player_b_result = params.get("player_b_result")
        winner_id = params.get("winner_id")

        # Update standings
        self.manager.standings.update_result(player_a_id, player_a_result)
        self.manager.standings.update_result(player_b_id, player_b_result)

        # Print to console
        result_str = winner_id if winner_id else "DRAW"
        print(f"📊 Match Result: {match_id} - {player_a_id} vs {player_b_id} → {result_str}")

        self.logger.match_event(
            match_id,
            f"Result: {player_a_id}={player_a_result}, {player_b_id}={player_b_result}",
        )

        # Track round completion
        if not hasattr(self.manager, '_round_matches_completed'):
            self.manager._round_matches_completed = 0

        self.manager._round_matches_completed += 1

        # Check if round is complete
        current_round = self.manager.scheduler.get_current_round()
        if current_round:
            total_in_round = len(current_round)
            if self.manager._round_matches_completed >= total_in_round:
                # Round complete - advance
                round_num = self.manager.scheduler.current_round + 1
                self.logger.info("ROUND_COMPLETE", f"Round {round_num} finished")

                # Print round completion and standings
                print(f"\n✅ Round {round_num} Complete!")
                print("=" * 60)
                standings = self.manager.standings.get_standings()
                print(f"{'Rank':<6} {'Player':<12} {'Played':<7} {'Wins':<5} {'Draws':<6} {'Losses':<7} {'Pts':<5}")
                print("-" * 60)
                for i, s in enumerate(standings, 1):
                    print(f"{i:<6} {s['player_id']:<12} {s['played']:<7} {s['wins']:<5} {s['draws']:<6} {s['losses']:<7} {s['points']:<5}")
                print("=" * 60 + "\n")

                # Reset counter
                self.manager._round_matches_completed = 0

                # Advance to next round
                if self.manager.scheduler.advance_round():
                    # More rounds to play
                    await self.start_round()
                else:
                    # League complete
                    await self.complete_league()

        # Broadcast standings
        await self.broadcast_standings()

        return {"status": "ACCEPTED"}

    async def handle_query(self, params: dict) -> dict:
        """Handle league query."""
        query_type = params.get("query_type")

        data = {}
        if query_type == "standings":
            data = {"standings": self.manager.standings.get_standings()}
        elif query_type == "schedule":
            data = self.manager.scheduler.get_schedule_summary()
        elif query_type == "stats":
            data = self.manager.standings.get_stats()
        elif query_type == "next_match":
            sender = params.get("sender", "")
            player_id = sender.split(":")[-1] if ":" in sender else None
            if player_id:
                data = {"match": self.manager.scheduler.get_player_next_match(player_id)}

        return self.manager.server.build_response(
            "LEAGUE_QUERY_RESPONSE",
            conversation_id=params.get("conversation_id"),
            query_type=query_type,
            data=data,
        )

    async def start_round(self) -> None:
        """Start a new round."""
        # Assign referees to matches
        referee_ids = list(self.manager.registered_referees.keys())
        self.manager.scheduler.assign_referees(referee_ids)

        round_matches = self.manager.scheduler.get_current_round()
        if not round_matches:
            await self.complete_league()
            return

        round_id = round_matches[0]["round_id"]
        round_num = self.manager.scheduler.current_round + 1

        self.logger.info("ROUND_START", f"Starting round {round_num}", round_id=round_id)

        # Broadcast round announcement
        await self.broadcast_round_announcement(round_id, round_num, round_matches)

        # Notify referees to start matches
        for match in round_matches:
            await self.notify_referee_start_match(match)

    async def broadcast_round_announcement(
        self, round_id: str, round_num: int, matches: list[dict]
    ) -> None:
        """Broadcast round announcement to all agents."""
        # Simplified: just log for now
        self.logger.info(
            "ROUND_ANNOUNCEMENT",
            f"Round {round_num} with {len(matches)} matches",
            round_id=round_id,
        )

    async def notify_referee_start_match(self, match: dict) -> None:
        """Notify referee to start a match."""
        referee_id = match.get("referee_id")
        referee = self.manager.registered_referees.get(referee_id)
        if not referee:
            return

        self.logger.info(
            "MATCH_ASSIGNED",
            f"Match {match['match_id']} assigned to {referee_id}",
            match_id=match["match_id"],
        )

        # Send HTTP request to referee to start match
        client = MCPClient("league_manager:MANAGER")

        try:
            await client.send(
                referee["endpoint"],
                "START_MATCH",
                {
                    "match_id": match["match_id"],
                    "round_id": match["round_id"],
                    "player_a": match["player_a"],
                    "player_b": match["player_b"],
                    "player_a_endpoint": self.manager.registered_players[match["player_a"]]["endpoint"],
                    "player_b_endpoint": self.manager.registered_players[match["player_b"]]["endpoint"],
                }
            )
            self.logger.info("MATCH_STARTED", f"Referee {referee_id} starting {match['match_id']}")
        except Exception as e:
            self.logger.error("MATCH_START_FAILED", str(e), match_id=match["match_id"])
        finally:
            await client.close()

    async def broadcast_standings(self) -> None:
        """Broadcast standings to all players."""
        standings = self.manager.standings.get_standings()
        self.logger.info(
            "STANDINGS_UPDATE",
            f"Broadcasting standings to {len(standings)} players",
            standings=standings
        )

    async def complete_league(self) -> None:
        """Complete the league."""
        standings = self.manager.standings.get_standings()
        winner = standings[0] if standings else None

        # Print final standings
        print("\n" + "=" * 60)
        print("🏆 LEAGUE COMPLETE - FINAL STANDINGS 🏆")
        print("=" * 60)
        print(f"{'Rank':<6} {'Player':<12} {'Played':<7} {'Wins':<5} {'Draws':<6} {'Losses':<7} {'Pts':<5}")
        print("-" * 60)
        for i, s in enumerate(standings, 1):
            trophy = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "  "))
            print(f"{trophy} {i:<4} {s['player_id']:<12} {s['played']:<7} {s['wins']:<5} {s['draws']:<6} {s['losses']:<7} {s['points']:<5}")
        print("=" * 60)

        if winner:
            print(f"\n👑 CHAMPION: {winner['player_id']} with {winner['points']} points!")
            print(f"   Record: {winner['wins']}W-{winner['draws']}D-{winner['losses']}L")
        print("=" * 60 + "\n")

        # Log final standings with full details
        self.logger.info(
            "LEAGUE_COMPLETED",
            f"League completed. Winner: {winner['player_id'] if winner else 'N/A'}",
            final_standings=standings
        )
