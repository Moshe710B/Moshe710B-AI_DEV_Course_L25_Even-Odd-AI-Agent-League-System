# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a distributed multi-agent system implementing a competitive Even/Odd game league using the Model Context Protocol (MCP). The system consists of three agent types (League Manager, Referees, Players) that communicate via the `league.v2` protocol using JSON-RPC 2.0 over HTTP.

## Running the Project

### Environment Setup (Required First)

This project uses **UV** for package management. Install dependencies:

```bash
# Install UV (if needed)
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# Linux/Mac: curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv

# Activate virtual environment
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

### Quick Simulation

Run a complete league simulation (recommended for testing):

```bash
python run_league.py              # Sequential execution
python run_league.py --parallel   # Parallel execution (faster)
```

### Running Individual Agents (Distributed Mode)

**Option 1: Using PowerShell Script (Recommended for Windows)**
```powershell
.\start_league.ps1
```
This automatically starts all 7 agents (1 manager + 2 referees + 4 players) in separate PowerShell windows.

**Option 2: Manual Start in Separate Terminals**

Start agents in this **exact order** (League Manager must start first):

```bash
# Terminal 1: League Manager (must start first)
cd agents/league_manager && python main.py

# Terminal 2-3: Referees (start immediately after manager)
cd agents/referee_REF01 && python main.py
cd agents/referee_REF02 && python main.py

# Terminal 4-7: Players (P01-P04)
cd agents/player_P01 && python main.py
cd agents/player_P02 && python main.py
cd agents/player_P03 && python main.py
cd agents/player_P04 && python main.py
```

**Important**: All agents must register within 60 seconds or the league will timeout.

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=SHARED/league_sdk

# Run specific test file
pytest tests/test_game_logic.py -v

# IMPORTANT: Set PYTHONPATH before testing
export PYTHONPATH="${PYTHONPATH}:$(pwd)/SHARED"  # Linux/Mac
set PYTHONPATH=%PYTHONPATH%;%CD%\SHARED          # Windows
```

## Architecture Overview

### Three-Layer System Design

1. **League Management Layer** (`agents/league_manager/`)
   - Player and referee registration
   - Round-robin schedule generation
   - Standings calculation and tracking
   - League-wide announcements

2. **Game Refereeing Layer** (`agents/referee_*/`)
   - Match initialization and player invitations
   - Move collection and validation
   - Winner determination (using game rules)
   - Result reporting to League Manager

3. **Player Layer** (`agents/player_*/`)
   - Respond to game invitations
   - Make parity choices using strategies
   - Track match history and statistics

### Shared SDK (`SHARED/league_sdk/`)

All agents share common components:
- **MCP Server/Client** (`mcp_server.py`, `mcp_client.py`): FastAPI-based MCP implementation
- **Protocol Schemas** (`schemas.py`, `schemas_base.py`): 18 message type models (Pydantic)
- **Game Rules** (`game_rules/even_odd.py`): Pluggable game logic
- **Utilities**: Auth, logging (JSONL), circuit breaker, error handlers, state persistence

### Port Allocation

- League Manager: `8000`
- Referees: `8001-8002`
- Players: `8101-8104`

All agents expose `/mcp` endpoint for JSON-RPC 2.0 communication.

## Protocol Compliance (`league.v2`)

This implementation strictly follows the League Protocol V2 specification:

### Message Structure
All messages must include:
- `protocol`: "league.v2"
- `message_type`: One of 18 defined types
- `sender`: Format is `"league_manager"`, `"player:<ID>"`, or `"referee:<ID>"`
- `timestamp`: UTC timezone (ISO-8601 ending with 'Z' or '+00:00')
- `auth_token`: Required after registration (validated for all post-registration messages)

### Registration Flow
1. **Referees** register first using `REFEREE_REGISTER_REQUEST` → receive `referee_id` and `auth_token`
2. **Players** register using `LEAGUE_REGISTER_REQUEST` → receive `player_id` and `auth_token`
3. All subsequent messages must include the `auth_token` for authentication

### Critical Validations
- `parity_choice` must be exactly `"even"` or `"odd"` (lowercase)
- All timestamps must be UTC (enforced via Pydantic validators)
- Protocol version must be ≥2.0.0

### Timeout Specifications
- `GAME_JOIN_ACK`: 5 seconds
- `CHOOSE_PARITY_RESPONSE`: 30 seconds
- General HTTP requests: 10 seconds

### Retry Policy
- Timeout errors (E001): Retry up to 3 times with 2-second delays
- Connection errors (E009): Retry up to 3 times with 2-second delays
- Other errors: Immediate failure (no retry)

## Code Organization

### Agent Templates
- `agents/player_template/`: Base template for creating new player agents
- `agents/referee_template/`: Base template for creating new referee agents

Each template includes:
- `main.py`: Entry point and server initialization
- `handlers.py`: Message type handlers
- Agent-specific components (e.g., `strategies/` for players)

### Player Strategies (`agents/player_template/strategies/`)

All strategies implement `BaseStrategy` abstract class:
- `random_strategy.py`: Random choice (Nash equilibrium)
- `deterministic.py`: Always chooses same parity
- `alternating.py`: Switches between even/odd
- `adaptive.py`: Learns from opponent patterns

To create a new strategy:
1. Inherit from `BaseStrategy`
2. Implement `name` property and `choose()` method
3. Return `"even"` or `"odd"` (lowercase, validated)

### State Management

#### Persistence Locations
- Match results: `SHARED/data/matches/`
- Standings: `SHARED/data/standings/`
- Player state: `SHARED/data/state/`
- Logs (JSONL): `SHARED/logs/{agent_type}/`

#### State Persistence Module
Use `league_sdk.state_persistence` for saving/loading player state across restarts.

## Game Rules and Logic

### Even/Odd Game Mechanics

1. Both players choose `"even"` or `"odd"`
2. Referee draws random number (1-10)
3. Winner determination:
   - **Same choice**: Always DRAW (regardless of number)
   - **Different choices**: Winner is player whose choice matches number parity
4. Scoring: Win = 3 points, Draw = 1 point, Loss = 0 points

### Standings Tie-Breaking
1. Total points (descending)
2. Number of wins (descending)
3. Number of draws (descending)
4. Head-to-head result
5. Alphabetical by player_id

## Key Design Patterns

### Circuit Breaker (`league_sdk/circuit_breaker.py`)
HTTP calls to other agents use circuit breaker pattern to prevent cascading failures. States: CLOSED → OPEN → HALF_OPEN.

### Repository Pattern (`league_sdk/repositories.py`)
Clean data access abstraction for standings, matches, and player data.

### Strategy Pattern
Player decision-making is fully pluggable via `BaseStrategy` interface.

### Message Envelope Pattern
All protocol messages extend `MessageEnvelope` base class with common fields (protocol, sender, timestamp, auth_token).

## Configuration

Configuration is loaded from `SHARED/config/agents.json` (if present) or uses defaults:

```python
from league_sdk import get_config

config = get_config()
agent_config = config.agents.get("league_manager", {})
host = agent_config.get("host", "127.0.0.1")
port = agent_config.get("port", 8000)
```

## Common Development Tasks

### Adding a New Player Strategy

1. Create new file in `agents/player_template/strategies/`
2. Implement `BaseStrategy`:
   ```python
   class MyStrategy(BaseStrategy):
       @property
       def name(self) -> str:
           return "my_strategy"

       def choose(self, match_id: str, opponent_id: str, history: list[dict] = None) -> ParityChoice:
           # Your logic here
           return "even"  # or "odd"
   ```
3. Update `agents/player_template/strategies/__init__.py`
4. Configure player to use strategy in agent initialization

### Adding New Message Types

1. Define Pydantic model in `SHARED/league_sdk/schemas.py`
2. Extend `MessageEnvelope` base class
3. Add handler method in appropriate agent's `handlers.py`
4. Register handler in agent's `_register_handlers()` method

### Debugging Agent Communication

Check JSONL logs in `SHARED/logs/`:
```bash
# View recent player logs
cat SHARED/logs/players/P01.log.jsonl | tail -50

# View league manager logs
cat SHARED/logs/league_manager/league_manager.log.jsonl | tail -50

# View referee logs (most useful for debugging match flow)
cat SHARED/logs/referee/REF01.log.jsonl | tail -100
```

Each log entry is a JSON object with: `timestamp`, `level`, `agent_id`, `message`, and optional `data`.

**Key events to look for in referee logs when debugging matches**:
- `MESSAGE_RECEIVED` - Referee received START_MATCH
- `SENDING_INVITATIONS` - Starting to invite players
- `INVITING_PLAYER` - Sending invitation to specific player (includes endpoint)
- `INVITATION_SENT` - Invitation successfully sent
- `INVITATION_FAILED` - Invitation failed (check error message)
- `WAITING_FOR_JOINS` - Waiting for player acknowledgments
- `JOIN_CHECK` - Final join status (shows `A=True/False, B=True/False`)
- `TECHNICAL_LOSS` - Match ended in technical loss (check reason: `join_timeout` or `choice_timeout`)
- `RESULT_REPORTED` - Result sent back to League Manager

## Troubleshooting

### "Module not found" errors
Ensure PYTHONPATH includes `SHARED/`:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/SHARED"
```

### Port conflicts
Check for processes using ports:
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <pid> /F

# Linux/Mac
lsof -i :8000
kill <pid>
```

### Registration timeout
League Manager waits 60 seconds for player registration by default. Ensure all players register within this window when running distributed agents.

### Agent startup crashes
1. Verify config files are valid JSON
2. Check logs in `SHARED/logs/{agent_type}/`
3. Ensure League Manager is running before starting players/referees

### All matches result in TECHNICAL_LOSS
This usually indicates one of these issues:

**Symptom**: Standings show 0 played, 0 wins for all players
**Diagnosis steps**:
1. Check referee logs for `SENDING_INVITATIONS` events
   - If missing: Handler not executing (check `handle_match_assignment` is running in background)
2. Check for `INVITATION_FAILED` errors
   - If present: Check endpoints are correct and players are running
3. Check for `JOIN_CHECK: A=False, B=False`
   - If present: Players aren't responding to `GAME_INVITATION` messages
4. Check player logs for `INVITATION_RECEIVED` events
   - If missing: Players aren't receiving invitations (check endpoints)

**Common causes**:
- Referee handler blocking instead of using background task (see "Async Match Orchestration" section)
- Incorrect player endpoints in League Manager's registered players
- Player handlers not registered for `GAME_INVITATION` or `CHOOSE_PARITY_CALL`
- Auth token mismatch between referee and players

## Important Implementation Notes

### UTC Timestamp Enforcement
All timestamps MUST be UTC. The SDK provides `utc_now()` helper:
```python
from league_sdk.helpers import utc_now
timestamp = utc_now()  # Returns ISO-8601 string with 'Z' suffix
```

### Authentication Tokens
Tokens are generated during registration and must be included in all subsequent messages. The `MCPServer` automatically validates tokens using `AuthTokenValidator`.

### Async Match Orchestration (CRITICAL)
**Referees must run matches in background tasks to avoid blocking the HTTP handler.**

In [agents/referee_template/handlers.py](agents/referee_template/handlers.py#L98-L131), the `handle_match_assignment()` handler uses `asyncio.create_task()` to:
1. Return `{"status": "ACCEPTED"}` immediately to League Manager
2. Run match orchestration (invitations, parity collection, winner determination) in background
3. Report result via `MATCH_RESULT_REPORT` when complete

**Why this matters**: Match orchestration takes 5+ seconds (invitation timeout + parity timeout). If the handler blocks waiting for the match to complete, the League Manager will advance rounds before matches finish, causing race conditions.

```python
# CORRECT: Background task
async def handle_match_assignment(self, params: dict) -> dict:
    async def run_match():
        result = await self.referee.orchestrator.conduct_match(...)
        await self._report_result(result)

    asyncio.create_task(run_match())  # Don't await!
    return {"status": "ACCEPTED"}  # Return immediately

# WRONG: Blocking
async def handle_match_assignment(self, params: dict) -> dict:
    result = await self.referee.orchestrator.conduct_match(...)  # Blocks for 5+ seconds!
    await self._report_result(result)
    return {"status": "COMPLETED", "result": result}
```

### Parallel Match Execution
The system supports running multiple matches concurrently using multiple referee instances. The `run_league.py` script demonstrates this with `--parallel` flag.

### Error Codes
The protocol defines standardized error codes (E001-E021) in `schemas_base.py`. Use these for consistent error reporting.

## Key Differences: Simulation vs Distributed Mode

Understanding these differences is critical when debugging:

| Aspect | Simulation Mode (`run_league.py`) | Distributed Mode (HTTP agents) |
|--------|-----------------------------------|--------------------------------|
| **Communication** | Direct Python method calls | HTTP JSON-RPC 2.0 over network |
| **Agent lifecycle** | In-memory objects | Separate processes on ports 8000-8104 |
| **Match execution** | Synchronous, blocking | Async background tasks (CRITICAL!) |
| **Timeouts** | Not enforced (instant responses) | 5s join, 30s parity, 10s HTTP |
| **Errors** | Python exceptions | HTTP errors, timeouts, circuit breaker |
| **Logging** | Console output only | JSONL files + console |
| **Registration** | Not required | Required with auth tokens |
| **Testing speed** | Fast (< 1 second) | Slow (5-10 seconds per round) |

**What this means**: Code that works perfectly in simulation can fail in distributed mode due to:
- Network timeouts
- Async race conditions (handlers blocking)
- Auth token validation
- Incorrect endpoints
- Missing HTTP error handling

Always test distributed mode separately, even if simulation passes all tests.

## Documentation References

- Project README: `README.md`
- Homework assignments: `DOCS/homework-part-*.md`
- Original PRD: `DOCS/PRD.md`
- API specification: `DOCS/API.md`
