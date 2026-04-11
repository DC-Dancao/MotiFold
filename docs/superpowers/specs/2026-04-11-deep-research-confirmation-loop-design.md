# Deep Research — Multi-turn Confirmation Loop

## Overview

Add a multi-turn research confirmation flow to the Deep Research panel (深度研究). The AI performs research iteratively, pausing at each step to present 3 AI-generated follow-up options + manual input. User can Follow Up, Skip, or Confirm Done. Loop continues until AI signals no more follow-ups needed.

## Architecture

### Stack
- **Backend:** Python, FastAPI, LangGraph, Redis, Celery
- **Frontend:** React (via pnpm)
- **Transport:** SSE for streaming events, REST fetch for resume

### Flow

```
User starts research
    → graph runs, does research
    → AI decides: needs follow-up?
        → YES: interrupt() with options + manual input
               Frontend renders:
               [1] Option A
               [2] Option B
               [3] Option C
               [____] Manual input
               [Skip] [Confirm Done]
               User responds → POST /api/research/resume
               → loop back to AI decision
        → NO: proceed to final result
    → output final research result
```

### State Schema

```python
class ResearchState(TypedDict):
    topic: str
    research_history: list[str]       # accumulated research
    user_inputs: list[str]           # user's choices/inputs so far
    needs_followup: bool             # AI sets this each iteration
    followup_options: list[str]       # 3 options for current round
    is_complete: bool
```

### Graph Nodes

| Node | Purpose |
|------|---------|
| `research_node` | Performs actual research, appends findings to `research_history` |
| `followup_decision_node` | Calls LLM → sets `needs_followup` + generates `followup_options` |
| `interrupt_node` | Calls `interrupt()` — **pauses here**, returns payload to frontend |
| `finalize_node` | Produces final research output |

### Interrupt Payload

```python
interrupt({
    "question": "What would you like to explore further?",
    "options": ["Option A", "Option B", "Option C"],
    "allow_manual_input": True,
    "allow_skip": True,
    "allow_confirm_done": True,
})
```

### User Actions (Resume Values)

| User Action | Resume Value |
|-------------|--------------|
| Click option 1/2/3 | `"option_1"`, `"option_2"`, `"option_3"` |
| Type manual input | `{"type": "manual", "text": "..."}` |
| Click "Skip follow up" | `"skip"` |
| Click "Confirm Done" | `"confirm_done"` |

### Edge Logic

```
research_node → followup_decision_node
followup_decision_node → interrupt_node    [if needs_followup == True]
followup_decision_node → finalize_node     [if needs_followup == False]
interrupt_node → research_node             [after resume, loop]
```

## Backend API

### `POST /api/research/start`
Start a new research session.

**Request:**
```json
{"topic": "Explain quantum computing"}
```

**Response:**
```json
{"thread_id": "abc-123"}
```

### `GET /api/research/stream/{thread_id}`
SSE stream of research events.

**Event types:**
- `research_update` — partial research output
- `interrupt` — AI requesting follow-up (contains options payload)
- `complete` — research finished (contains final result)
- `error` — error occurred

**Interrupt event:**
```json
{"type": "interrupt", "data": {"question": "...", "options": [...], "allow_manual_input": true, "allow_skip": true, "allow_confirm_done": true}}
```

### `POST /api/research/resume/{thread_id}`
Resume after user action.

**Request:**
```json
{"action": "option_1"}  // or "skip", "confirm_done", or {"type": "manual", "text": "..."}
```

**Response:** Same as stream endpoint (resumes SSE stream)

## Frontend (Deep Research Panel)

### UI Layout
```
┌─────────────────────────────────────┐
│  深度研究 (Deep Research)            │
├─────────────────────────────────────┤
│                                     │
│  [Research output / history]        │
│                                     │
│  [Options displayed here when       │
│   interrupt fires]                  │
│                                     │
│  [1] Option A                       │
│  [2] Option B                       │
│  [3] Option C                       │
│  [____ Manual input ____]           │
│                                     │
│  [Skip] [Confirm Done]              │
│                                     │
└─────────────────────────────────────┘
```

### State
- `threadId: string | null`
- `status: 'idle' | 'streaming' | 'waiting_input' | 'complete' | 'error'`
- `researchHistory: string[]`
- `currentInterrupt: InterruptPayload | null`

### Behavior
1. User enters topic, clicks Start
2. SSE connects, shows streaming output
3. When `interrupt` event fires → show options + input, pause streaming display
4. User clicks option/types input + clicks Send
5. POST resume, reconnect SSE stream
6. Loop until `complete` event

## Acceptance Criteria

1. Research graph runs with iterative follow-up loop
2. AI generates 3 relevant options at each interrupt point
3. User can select 1/2/3, type manual input, skip, or confirm done
4. Graph state persists across resume via thread_id + checkpointer
5. SSE streams research updates in real-time
6. Frontend displays options reactively when interrupt fires
7. Loop terminates when user clicks "Confirm Done" or AI signals no more follow-ups
