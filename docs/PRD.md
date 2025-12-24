# Product Requirements Document (PRD)

## 1. Project Overview

- **Project Name:** Even/Odd AI Agent League System
- **Description:** A distributed multi-agent system implementing a competitive Even/Odd game league. The system includes three agent types (League Manager, Referee, Player) that communicate via the `league.v2` protocol using MCP (Model Context Protocol) over JSON-RPC 2.0 HTTP transport.
- **Problem Statement:** Build a complete autonomous league system where AI agents compete in games, demonstrating distributed systems, protocol compliance, and multi-agent coordination.
- **Why This Matters:** This project teaches MCP protocol implementation, autonomous agent design, distributed systems architecture, and real-world software engineering practices.

## 2. System Architecture

### 2.1 Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  LEAGUE MANAGEMENT LAYER                 │
│  ┌─────────────────────────────────────────────────┐   │
│  │           League Manager (Port 8000)             │   │
│  │  - Player/Referee registration                   │   │
│  │  - Round-robin scheduling                        │   │
│  │  - Standings calculation                         │   │
│  │  - LEAGUE_QUERY handling                         │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           ↕
┌─────────────────────────────────────────────────────────┐
│                  GAME REFEREEING LAYER                   │
│  ┌──────────────────┐    ┌──────────────────┐          │
│  │  Referee REF01   │    │  Referee REF02   │          │
│  │  (Port 8001)     │    │  (Port 8002)     │          │
│  │  - Match init    │    │  - Match init    │          │
│  │  - Move collect  │    │  - Move collect  │          │
│  │  - Winner calc   │    │  - Winner calc   │          │
│  └──────────────────┘    └──────────────────┘          │
└─────────────────────────────────────────────────────────┘
                           ↕
┌─────────────────────────────────────────────────────────┐
│                    PLAYER LAYER                          │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐          │
│  │  P01   │ │  P02   │ │  P03   │ │  P04   │          │
│  │ :8101  │ │ :8102  │ │ :8103  │ │ :8104  │          │
│  └────────┘ └────────┘ └────────┘ └────────┘          │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Agent Types

| Agent | Port(s) | Responsibilities |
|-------|---------|------------------|
| League Manager | 8000 | Registration, scheduling, standings, queries |
| Referee | 8001-8002 | Match orchestration, move collection, winner determination |
| Player | 8101-8104 | Game participation, strategy execution, result handling |

### 2.3 Communication Protocol

All agents communicate via **HTTP POST** to `/mcp` endpoint using:
- **Protocol:** `league.v2`
- **Transport:** JSON-RPC 2.0 over HTTP
- **Authentication:** Token-based (after registration)

## 3. Functional Requirements

### 3.1 League Manager Agent

**Registration Handling:**
- Accept `LEAGUE_REGISTER_REQUEST` from Players and Referees
- Assign unique IDs (P01-P04 for players, REF01-REF02 for referees)
- Generate and issue `auth_token` for each agent
- Track registered agents and their endpoints

**Scheduling:**
- Generate round-robin schedule for all registered players
- Assign referees to matches (load balancing)
- Broadcast `ROUND_ANNOUNCEMENT` to all agents

**Standings Management:**
- Calculate standings after each match (Win=3pts, Draw=1pt, Loss=0pt)
- Broadcast `LEAGUE_STANDINGS_UPDATE` after each round
- Handle `LEAGUE_QUERY` requests (standings, schedule, stats, next_match)

**League Lifecycle:**
- Send `ROUND_COMPLETED` after all matches in a round finish
- Send `LEAGUE_COMPLETED` when all rounds are done

### 3.2 Referee Agent

**Registration:**
- Register with League Manager on startup
- Receive `referee_id` and `auth_token`

**Match Orchestration:**
- Receive match assignments from League Manager
- Send `GAME_INVITATION` to both players
- Collect `GAME_JOIN_ACK` from both players (5s timeout)
- Send `CHOOSE_PARITY_CALL` to both players
- Collect `CHOOSE_PARITY_RESPONSE` (30s timeout)

**Winner Determination:**
- Draw random number (1-10)
- Determine winner based on number parity vs player choices
- Send `GAME_OVER` to both players
- Report `MATCH_RESULT_REPORT` to League Manager

**Error Handling:**
- Send `GAME_ERROR` for timeouts or invalid responses
- Handle retry logic for transient failures

### 3.3 Player Agent

**Registration:**
- Register with League Manager on startup
- Receive `player_id` and `auth_token`
- Persist credentials for restart recovery

**Game Participation:**
- Accept `GAME_INVITATION` within 5 seconds
- Choose parity ("even" or "odd") within 30 seconds
- Process `GAME_OVER` and update statistics

**Strategies (Pluggable):**
- **Random:** Equal probability even/odd
- **Deterministic:** Always choose one option
- **Alternating:** Switch between even/odd
- **Adaptive:** Learn from opponent history
- **LLM-Based:** Use AI model for decisions

**Query Support:**
- Send `LEAGUE_QUERY` to get standings, schedule, stats

### 3.4 Protocol Definitions (`league.v2`)

#### General Envelope (REQUIRED in ALL Messages)
```json
{
  "protocol": "league.v2",
  "message_type": "<TYPE>",
  "sender": "<TYPE:ID>",
  "timestamp": "<ISO-8601 UTC with Z>",
  "conversation_id": "<UUID>"
}
```

#### Envelope Field Requirements
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `protocol` | String | **Yes** | Always `"league.v2"` |
| `message_type` | String | **Yes** | Message type identifier |
| `sender` | String | **Yes** | Format: `type:id` (e.g., `player:P01`) |
| `timestamp` | String | **Yes** | UTC with `Z` suffix |
| `conversation_id` | String | **Yes** | Thread tracking ID |
| `auth_token` | String | Post-registration | Required after registration |

#### UTC Timestamp Requirement (CRITICAL)
| Format | Valid? | Explanation |
|--------|--------|-------------|
| `2025-01-15T10:30:00Z` | ✓ | Z suffix indicates UTC |
| `2025-01-15T10:30:00+00:00` | ✓ | +00:00 equals UTC |
| `2025-01-15T10:30:00+02:00` | ✗ | Non-UTC forbidden |
| `2025-01-15T10:30:00` | ✗ | No timezone forbidden |

### 3.5 Complete Message Types (18 Types)

| Category | Message Type | Direction |
|----------|--------------|-----------|
| Registration | `LEAGUE_REGISTER_REQUEST` | Agent → Manager |
| Registration | `LEAGUE_REGISTER_RESPONSE` | Manager → Agent |
| Registration | `REFEREE_REGISTER_REQUEST` | Referee → Manager |
| Registration | `REFEREE_REGISTER_RESPONSE` | Manager → Referee |
| Round | `ROUND_ANNOUNCEMENT` | Manager → All |
| Round | `ROUND_COMPLETED` | Manager → All |
| Match | `GAME_INVITATION` | Referee → Player |
| Match | `GAME_JOIN_ACK` | Player → Referee |
| Match | `CHOOSE_PARITY_CALL` | Referee → Player |
| Match | `CHOOSE_PARITY_RESPONSE` | Player → Referee |
| Match | `GAME_OVER` | Referee → Player |
| Match | `MATCH_RESULT_REPORT` | Referee → Manager |
| Standings | `LEAGUE_STANDINGS_UPDATE` | Manager → All |
| Query | `LEAGUE_QUERY` | Player → Manager |
| Query | `LEAGUE_QUERY_RESPONSE` | Manager → Player |
| Completion | `LEAGUE_COMPLETED` | Manager → All |
| Error | `LEAGUE_ERROR` | Manager → Agent |
| Error | `GAME_ERROR` | Referee → Player |

### 3.6 Error Codes Reference
| Code | Name | Description | Retryable |
|------|------|-------------|-----------|
| E001 | TIMEOUT_ERROR | Response not received in time | Yes |
| E003 | MISSING_REQUIRED_FIELD | Required field missing | No |
| E004 | INVALID_PARITY_CHOICE | Invalid choice | No |
| E005 | PLAYER_NOT_REGISTERED | Player ID not found | No |
| E006 | REFEREE_NOT_REGISTERED | Referee ID not found | No |
| E009 | CONNECTION_ERROR | Connection failure | Yes |
| E011 | AUTH_TOKEN_MISSING | Auth token not included | No |
| E012 | AUTH_TOKEN_INVALID | Auth token is invalid | No |
| E018 | PROTOCOL_VERSION_MISMATCH | Version incompatible | No |
| E021 | INVALID_TIMESTAMP | Not UTC format | No |

### 3.7 Response Timeouts
| Message Type | Timeout | Notes |
|-------------|---------|-------|
| LEAGUE_REGISTER | 10 sec | Registration |
| REFEREE_REGISTER | 10 sec | Referee registration |
| GAME_JOIN_ACK | 5 sec | Join confirmation |
| CHOOSE_PARITY | 30 sec | Parity choice |
| MATCH_RESULT_REPORT | 10 sec | Report to Manager |
| LEAGUE_QUERY | 10 sec | Query response |

### 3.8 Retry Policy
- **Maximum Retries:** 3
- **Backoff:** 2 seconds between retries
- **Retryable Errors:** E001 (timeout), E009 (connection)
- **After Max Retries:** Technical loss

## 4. Technical Requirements

### 4.1 Shared SDK (`league_sdk`)

The SDK provides common functionality for all agents:

| Module | Purpose |
|--------|---------|
| `config_loader.py` | Lazy-load JSON configuration with caching |
| `config_models.py` | Type-safe dataclass configuration models |
| `schemas.py` | Complete Pydantic models for all 18 message types |
| `mcp_client.py` | HTTP client with retry logic |
| `mcp_server.py` | Base MCP server class for agents |
| `repositories.py` | Data access (standings, matches, state, players) |
| `logger.py` | JSONL structured logging |
| `helpers.py` | UTC timestamps, ID generation, validation |
| `game_rules/even_odd.py` | Even/Odd game logic |

### 4.2 Environment & Stack
- **Language:** Python 3.10+
- **Virtual Environment:** UV (mandatory)
- **Dependencies:**
  - `fastapi`, `uvicorn`: HTTP server
  - `httpx`: Async HTTP client
  - `pydantic`: Message validation
  - `python-dotenv`: Configuration
  - `matplotlib`, `seaborn`: Visualization

### 4.3 Performance Constraints
- **Response Times:** Must meet all timeout requirements
- **Concurrency:** Async/await for non-blocking operations
- **Parallel Matches:** Support concurrent match execution

### 4.4 Resilience Patterns
- **Retry with Backoff:** 3 retries, 2s backoff
- **Circuit Breaker:** Prevent cascading failures
- **State Persistence:** Survive agent restarts

## 5. Success Criteria

### 5.1 Full System Operation
- [ ] League Manager registers players and referees
- [ ] Round-robin schedule generated correctly
- [ ] Referees conduct matches in parallel
- [ ] Players respond within timeouts
- [ ] Standings calculated correctly
- [ ] Full league runs to completion

### 5.2 Protocol Compliance
- [ ] All 18 message types implemented
- [ ] UTC timestamps enforced
- [ ] Auth tokens validated
- [ ] Envelope fields complete

### 5.3 Code Quality
- [ ] All files under 150 lines (PROJECT_GUIDELINES)
- [ ] Type hints throughout
- [ ] Comprehensive logging
- [ ] Unit tests for core logic

### 5.4 Visual Results
- [ ] Performance graphs in results/graphs/
- [ ] Match history visualization
- [ ] Standings progression chart

## 6. Directory Structure

```
L25/
├── README.md                    # Complete setup and run instructions
├── requirements.txt             # All dependencies
├── .gitignore
├── .env.example
│
├── SHARED/                      # Shared SDK and resources
│   ├── config/                  # JSON configuration files
│   │   ├── system.json          # Protocol settings
│   │   ├── agents.json          # Agent definitions
│   │   └── league.json          # League settings
│   ├── data/                    # Runtime data
│   │   ├── standings/           # League standings
│   │   ├── matches/             # Match history
│   │   └── state/               # Agent state persistence
│   ├── logs/                    # JSONL structured logs
│   │   ├── league_manager/
│   │   ├── referees/
│   │   └── players/
│   └── league_sdk/              # Python SDK package
│       ├── __init__.py
│       ├── config_loader.py
│       ├── config_models.py
│       ├── schemas.py           # All 18 message type models
│       ├── mcp_client.py
│       ├── mcp_server.py
│       ├── repositories.py
│       ├── logger.py
│       ├── helpers.py
│       └── game_rules/
│           ├── __init__.py
│           └── even_odd.py
│
├── agents/                      # Agent implementations
│   ├── league_manager/
│   │   ├── main.py
│   │   ├── handlers.py
│   │   └── scheduler.py
│   ├── referee_template/
│   │   ├── main.py
│   │   ├── handlers.py
│   │   └── game_logic.py
│   ├── referee_REF01/           # Instance from template
│   ├── referee_REF02/
│   ├── player_template/
│   │   ├── main.py
│   │   ├── handlers.py
│   │   └── strategy.py
│   ├── player_P01/              # Instance from template
│   ├── player_P02/
│   ├── player_P03/
│   └── player_P04/
│
├── results/                     # Visual outputs
│   ├── graphs/
│   │   ├── standings_progression.png
│   │   ├── win_distribution.png
│   │   └── strategy_comparison.png
│   └── examples/
│
├── docs/
│   ├── PRD.md
│   ├── tasks.json
│   └── homework-part-*.md
│
└── tests/
    ├── test_sdk.py
    ├── test_league_manager.py
    ├── test_referee.py
    └── test_player.py
```

## 7. Critical Implementation Details

### 7.1 Authentication Flow

**Challenge:** Referees and players exchange messages, but who validates auth tokens?

**Solution:**
- League Manager registers auth tokens for both players AND referees during registration
- Player → Referee messages: No auth required (referee doesn't have player tokens)
- Referee → Manager messages: Auth required (manager has referee tokens)
- Player → Manager messages: Auth required (manager has player tokens)

**Code:**
```python
# In League Manager registration handlers
self.manager.server.register_auth_token(f"player:{player_id}", auth_token)
self.manager.server.register_auth_token(f"referees:{referee_id}", auth_token)
```

### 7.2 Async Match Orchestration

**Challenge:** Match orchestration takes 5-35 seconds (invitation timeout + parity timeout). If referee handler blocks, League Manager advances rounds before matches complete.

**Solution:** Referees use background tasks (`asyncio.create_task`) to orchestrate matches:

```python
async def handle_match_assignment(self, params: dict) -> dict:
    async def run_match():
        result = await self.referee.orchestrator.conduct_match(...)
        await self._report_result(result)

    asyncio.create_task(run_match())  # Don't await!
    return {"status": "ACCEPTED"}  # Return immediately
```

### 7.3 Parity Response Capture

**Challenge:** Players return parity choice in HTTP response, but referee was ignoring it and waiting 30 seconds for nothing.

**Solution:** Capture and parse HTTP response immediately:

```python
response = await client.send(endpoint, "CHOOSE_PARITY_CALL", {...})
parity_choice = response.get("result", {}).get("parity_choice")
if parity_choice in ("even", "odd"):
    match_state["player_a_choice"] = parity_choice
```

### 7.4 Console Output for User Experience

**Challenge:** League runs but user sees nothing happening.

**Solution:** Add real-time console output:
- Match results as they complete: `📊 Match Result: R1M1 - P04 vs P03 → P03`
- Round completion with standings table
- Final standings with trophy emojis (🥇🥈🥉)
- Champion announcement

### 7.5 Logging Directory Consistency

**Challenge:** Duplicate logs in `player/` and `players/`, `referee/` and `referees/`

**Root Cause:** Agent main.py created `JsonLogger("players", id)` but `MCPServer` created `JsonLogger("player", id)`

**Solution:** Use consistent agent_type in both:
```python
self.server = MCPServer("players", player_id, ...)  # Match the logger
self.logger = JsonLogger("players", player_id)
```

## 8. Learning Objectives

This project demonstrates:
1. **Multi-Agent Systems:** Coordination between autonomous agents
2. **MCP Protocol:** JSON-RPC 2.0 over HTTP implementation
3. **Distributed Architecture:** Three-layer system design
4. **Protocol Compliance:** Strict specification adherence
5. **Resilience Patterns:** Retry, backoff, circuit breaker
6. **Strategy Pattern:** Pluggable decision algorithms
7. **Repository Pattern:** Clean data access abstraction
8. **Async Programming:** Background tasks, event-driven design
9. **Authentication:** Token generation, validation, propagation
10. **Debugging Distributed Systems:** Log analysis, message tracing

## 9. Deployment

### Running the Full League

```bash
# Terminal 1: League Manager
cd agents/league_manager && python main.py

# Terminal 2-3: Referees
cd agents/referee_REF01 && python main.py
cd agents/referee_REF02 && python main.py

# Terminal 4-7: Players
cd agents/player_P01 && python main.py
cd agents/player_P02 && python main.py
cd agents/player_P03 && python main.py
cd agents/player_P04 && python main.py
```

### Expected Flow
1. League Manager starts on port 8000
2. Referees register with Manager (ports 8001-8002)
3. Players register with Manager (ports 8101-8104)
4. Manager waits 60 seconds after minimum requirements met (4 players + 1 referee)
5. Manager creates round-robin schedule and starts league
6. Manager assigns matches to referees
7. Referees conduct matches in parallel (background tasks)
8. Referees send `MATCH_RESULT_REPORT` to Manager
9. Results displayed in console and standings updated
10. Round completes, standings broadcast
11. Repeat steps 6-10 until all rounds complete
12. League completion announced with final standings

### Quick Testing: Simulation Mode

For rapid testing without distributed agents:

```bash
# Sequential execution
python SIMULATION_run_league.py

# Parallel execution (faster)
python SIMULATION_run_league.py --parallel
```

Simulation mode:
- Completes in < 1 second
- No HTTP transport (direct method calls)
- Perfect for testing game logic and strategies
- Results identical to distributed mode

## 10. Common Issues and Solutions

### Issue 1: Matches Start But Never Complete

**Symptoms:**
- League Manager shows `MATCH_STARTED`
- No `MATCH_RESULT_REPORT` received
- Standings never update

**Root Cause:** Auth validation blocking referee results

**Solution:**
```python
# In League Manager registration handler
self.manager.server.register_auth_token(f"referees:{referee_id}", auth_token)
```

**Diagnosis:**
```bash
cat SHARED/logs/league_manager/MANAGER.log.jsonl | grep "AUTH_FAILED"
```

### Issue 2: Empty Standings Table

**Symptoms:**
- Round completes but table shows no data
- Headers display but no player rows

**Root Cause:** Key mismatch between standings data and display code

**Solution:** Use `wins/draws/losses` (plural) not `won/draw/lost`
```python
print(f"{s['wins']:<5} {s['draws']:<6} {s['losses']:<7}")
```

### Issue 3: All Matches Timeout

**Symptoms:**
- All matches result in `TECHNICAL_LOSS`
- Referee logs show `JOIN_CHECK: A=False, B=False`

**Root Cause:** Players not responding to `GAME_INVITATION`

**Diagnosis:**
```bash
cat SHARED/logs/referees/REF01.log.jsonl | grep "INVITATION_FAILED"
cat SHARED/logs/players/P01.log.jsonl | grep "INVITATION_RECEIVED"
```

**Common Causes:**
- Player endpoints incorrect in registration
- Auth blocking player → referee messages
- Player handlers not registered

## 11. Performance Metrics

### Simulation Mode
- **Full League (6 matches):** < 300ms
- **Per Match:** ~50ms
- **Memory:** < 10MB

### Distributed Mode
- **Full League (6 matches):** ~15-20 seconds
- **Per Match:** ~5-8 seconds (includes timeouts)
- **Network Overhead:** ~2-3 seconds total
- **Memory:** ~50MB (all 7 agents)

### Bottlenecks
1. **Parity timeout:** 30 seconds (if player doesn't respond)
2. **Join timeout:** 5 seconds (if player doesn't join)
3. **HTTP round-trip:** ~10-50ms per request
4. **Sequential rounds:** Can't start Round 2 until Round 1 completes

### Optimization Opportunities
1. **Reduce timeouts:** 5s → 2s for join, 30s → 10s for parity
2. **Parallel rounds:** Run multiple rounds concurrently
3. **Connection pooling:** Reuse HTTP connections (already implemented)
4. **Event-driven:** Use WebSockets instead of polling

## 12. Future Enhancements

### Short Term (v2.1)
- [ ] Add PowerShell/Bash scripts for easy multi-terminal launch
- [ ] Implement `LEAGUE_STANDINGS_UPDATE` broadcast to players
- [ ] Add match replay feature from logs
- [ ] Create web dashboard for real-time viewing

### Medium Term (v3.0)
- [ ] WebSocket transport for lower latency
- [ ] Tournament brackets (elimination style)
- [ ] More game types (Rock-Paper-Scissors, Tic-Tac-Toe)
- [ ] LLM-based adaptive strategies
- [ ] Spectator mode with live commentary

### Long Term (v4.0)
- [ ] Cloud deployment (AWS/GCP)
- [ ] Multi-league federation
- [ ] Player ranking system (ELO)
- [ ] Historical analytics dashboard
- [ ] API for external clients
