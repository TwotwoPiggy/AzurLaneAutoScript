<!-- refreshed: 2026-09-11 -->
# Architecture

**Analysis Date:** 2026-09-11

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                        User Interface Layer                             │
├───────────────────────────────────┬─────────────────────────────────────┤
│   Electron Desktop Client         │   Web Dashboard (PyWebIO / ASGI)    │
│   `webapp/packages/`              │   `gui.py`, `module/webui/app.py`   │
└─────────────────┬─────────────────┴──────────────────┬──────────────────┘
                  │                                    │
                  ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Process & Multi-Instance Management Layer                  │
│   `module/webui/process_manager.py` (Isolated Alas subprocesses)        │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Task Scheduler & State Orchestration Layer                 │
│   `alas.py`: AzurLaneAutoScript.loop(), task scheduling & recovery      │
│   `module/config/`: AzurLaneConfig, watcher, config_generated.py        │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   Business Logic & Feature Modules                      │
│   Campaign & Battle: `module/campaign/`, `module/combat/`, `campaign/`  │
│   Daily / Operation Siren: `module/os/`, `module/daily/`, `module/dorm/`│
│   Map Navigation: `module/map/`, `module/map_detection/`                │
└─────────────────┬────────────────────────────────────┬──────────────────┘
                  │                                    │
                  ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              UI Navigation & Game Dialogue Abstraction Layer            │
│   `module/ui/ui.py` (Directed Graph Page Navigator)                     │
│   `module/handler/info_handler.py` (Popup & Emergency Interceptor)      │
│   `module/base/base.py` (ModuleBase - Loop sugar, state assertions)     │
└─────────────────┬────────────────────────────────────┬──────────────────┘
                  │                                    │
                  ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Perception, Vision & Device Communication Layer            │
│   Vision: `module/base/button.py`, `module/base/utils.py`, `module/ocr/`│
│   Device: `module/device/device.py`, `connection.py`                    │
│   Capture: DroidCast, Scrcpy, aScreenCap, NemuIpc, LDOpenGL             │
│   Input: MaaTouch, Minitouch, Hermit, ADB Socket                        │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Hardware / Android Emulator Runtime Target                 │
│   MuMu, LDPlayer, Nox, BlueStacks, MEmu, WSA, Physical Device (1280x720)│
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| **`AzurLaneAutoScript`** | Top-level entry orchestrator: initializes config, manages scheduler loop, handles exceptions and crash recovery | `alas.py` |
| **`AzurLaneConfig`** | Configuration manager: loads user JSON/YAML configs, calculates next run times, triggers watchers | `module/config/config.py` |
| **`ProcessManager`** | WebUI process supervisor: manages start/stop/restart events of background Alas instances | `module/webui/process_manager.py` |
| **`Device`** | High-level device controller: combines connection lifecycle, screenshot pipelines, and touch injection | `module/device/device.py` |
| **`Connection`** | ADB connection pool: establishes ADB sockets, discovers emulators, handles reconnection | `module/device/connection.py` |
| **`Screenshot`** | Frame capture engine: multiplexes ADB, DroidCast, Scrcpy, NemuIPC, and LDOpenGL capture methods | `module/device/screenshot.py` |
| **`Control`** | Touch and gesture engine: dispatches click, multi-click, long-click, and drag/swipe to MaaTouch/minitouch | `module/device/control.py` |
| **`ModuleBase`** | Core automation base class: provides looping syntactic sugar (`loop()`), image matching (`appear`), and workers | `module/base/base.py` |
| **`InfoHandler`** | Global modal interceptor: auto-handles login notices, maintenance prompts, battle pass popups, stamina alerts | `module/handler/info_handler.py` |
| **`UI` & `Page`** | Directed-graph page navigation: uses BFS/A* across `Page` nodes to navigate in-game interfaces reliably | `module/ui/ui.py`, `module/ui/page.py` |
| **`Combat`** | Battle loop handler: monitors combat start, auto-combat toggles, submarine airstrikes, and post-battle grading | `module/combat/combat.py` |
| **`CampaignBase` & `Map`** | Tactical map movement: handles grid parsing, obstacle avoidance, fleet positioning, and Boss targeting | `module/campaign/campaign_base.py`, `module/map/map.py` |
| **`AlOcr` & `Ocr`** | Optical character recognition: performs localized digit and string recognition using CNOCR/MXNet | `module/ocr/al_ocr.py`, `module/ocr/ocr.py` |

## Pattern Overview

**Overall:** Hierarchical Class Composition & Directed Graph State Machine with Polling Loop.

**Key Characteristics:**
- **Layered Class Inheritance:** Core automation primitives inherit downward (`ModuleBase` → `InfoHandler` → `UI` → `Combat` → `CampaignBase` → `CampaignRun`). Every domain subclass has access to device actions, image matching, and modal interception.
- **Graph-Driven Page Routing:** Game menus are modeled as nodes in a directed graph (`Page`), with automatic shortest-path traversal (`UI.ui_goto`).
- **Cooperative Task Scheduling:** Tasks declare time-delayed next runs. The scheduler loop queries the earliest runnable task, executes it to completion, and re-evaluates schedules.
- **Decoupled Perception & Action:** Recognition evaluates normalized images (1280x720); touch injection randomizes coordinates within button bounding boxes to emulate human input.

## Layers

**1. Orchestration Layer:**
- Location: `alas.py`, `module/config/`
- Contains: `AzurLaneAutoScript`, `AzurLaneConfig`, scheduler queue calculation
- Depends on: Configuration templates, Device layer, Business modules
- Used by: CLI execution, WebUI process runner

**2. Navigation & UI State Layer:**
- Location: `module/ui/`, `module/handler/`
- Contains: `Page`, `UI`, `InfoHandler`, modal asset definitions
- Depends on: `ModuleBase`, button and template assets
- Used by: All business modules (Campaign, Dorm, Commission, etc.)

**3. Vision & Input (Perception/Actuation) Layer:**
- Location: `module/base/`, `module/device/`, `module/ocr/`
- Contains: `Device`, `Screenshot`, `Control`, `Button`, `Template`, `AlOcr`
- Depends on: OpenCV, NumPy, adbutils, uiautomator2, cnocr
- Used by: `ModuleBase` and all subclasses

**4. Business & Domain Layer:**
- Location: `module/<feature>/` (55 subdirectories), `campaign/`
- Contains: Feature routines (e.g. `RewardResearch`, `RewardCommission`, `CampaignRun`, `OSCampaignRun`)
- Depends on: `UI`, `Combat`, `Map`

## Data Flow

### Primary Request Path (Scheduled Task Execution)

1. **Task Selection:** `AzurLaneAutoScript.get_next_task()` selects the task with earliest `next_run` timestamp (`alas.py:492`).
2. **Device State Check:** Evaluates whether wait time requires game sleep, stay, or home screen navigation (`alas.py:509`).
3. **Execution Dispatch:** Calls task method via camelCase-to-snake_case mapping (`inflection.underscore(task)`) (`alas.py:587`).
4. **Navigation:** Domain class executes `self.ui_ensure(page_target)`, traversing page graph nodes (`module/ui/ui.py:440`).
5. **Observation Loop:** Subroutine enters `for _ in self.loop():`, taking screenshot and checking button presence (`module/base/base.py:127`).
6. **Interaction:** Triggers randomized click inside bounding box (`module/device/control.py:38`).
7. **Schedule Update:** On task end (`TaskEnd`), sets next run time in `AzurLaneConfig` and saves to JSON (`module/config/config.py`).

### Error Recovery Flow

1. **Detection:** Catch `GameStuckError`, `GameTooManyClickError`, or `GameNotRunningError` (`alas.py:73-92`).
2. **Artifact Dump:** Call `save_error_log()`, saving the last 60 screenshots from circular deque and filtered logs (`alas.py:135`).
3. **Recovery Task Call:** Insert emergency `Restart` task at the front of the scheduler queue (`alas.py:82`).
4. **App Restart:** Restart game process, perform automatic login, and re-enter main interface (`module/handler/login.py`).

**State Management:**
- Task schedules and user settings persist in `config/{config_name}.json`.
- Game state is strictly derived from continuous live screen observation (no hidden in-memory state out-of-sync with game client).

## Key Abstractions

**`Button` / `Template`:**
- Purpose: Represents a visual UI element with bounding box coordinates, expected pixel color, clickable target area, and reference template file.
- Examples: `module/base/button.py`, `module/ui/assets.py`
- Pattern: Value Object / Descriptor pattern.

**`Page`:**
- Purpose: Represents a top-level in-game page/menu with dedicated verification button and incoming/outgoing edges.
- Examples: `module/ui/page.py`
- Pattern: State / Graph Node pattern.

**`Device`:**
- Purpose: Facade combining multiple inheritance for hardware connection, video stream decoding, and low-latency touch injection.
- Examples: `module/device/device.py`
- Pattern: Facade / Adapter pattern.

## Entry Points

**CLI Automation Scheduler:**
- Location: `alas.py` (`python alas.py -c <config_name>`)
- Triggers: User manual launch, CLI scripts, scheduled cron jobs
- Responsibilities: Runs the infinite task evaluation loop for a single configuration instance.

**Web Dashboard & API Server:**
- Location: `gui.py` (`python gui.py --port 22267`)
- Triggers: User launch, desktop shortcut, electron wrapper
- Responsibilities: Starts Uvicorn ASGI server hosting PyWebIO management dashboard and ProcessManager API.

**Electron Desktop GUI Client:**
- Location: `webapp/packages/main/index.ts`
- Triggers: Desktop executable launch
- Responsibilities: Native window management, auto-updater, embedded webapp rendering.

## Architectural Constraints

- **Fixed Display Geometry:** The entire image recognition pipeline assumes a native resolution of 1280x720 pixels landscape. Any deviating screen size must be downscaled or realigned.
- **Process Isolation per Account:** Multi-account / multi-instance running is achieved by spawning distinct Python OS processes for each configuration name, preventing cross-account state pollution.
- **Single-Threaded Actuation:** Touch injection and screen capture on a single device instance are serialized; concurrent taps are disallowed to maintain state machine determinism.

## Anti-Patterns

### Blocking Sleep in State Loops

**What happens:** Using standard `time.sleep()` for multi-second delays inside UI state transitions.
**Why it's wrong:** Freezes event loops, delays error handling, and prevents stop event signals from triggering cleanly.
**Do this instead:** Use `for _ in self.loop():` with `Timer` intervals or `self.device.sleep()`.

### Hardcoded Pixel Coordinates for Taps

**What happens:** Direct calls to `device.click((x, y))` with exact static integers.
**Why it's wrong:** Increases anti-cheat detection risk and fails across localized UI variations.
**Do this instead:** Define a `Button` with defined area boundaries and let `random_rectangle_point` introduce natural variance.

## Error Handling

**Strategy:** Fail-safe defensive recovery with structured exception propagation.

**Patterns:**
- Custom exception taxonomy (`module/exception.py`):
  - `ScriptError`: Logic/programming errors.
  - `GameStuckError`: Same screen detected continuously without progress.
  - `GamePageUnknownError`: Unrecognized game page; triggers server maintenance check.
  - `RequestHumanTakeover`: Unrecoverable scenarios (e.g., account ban check, dock full when retirement disabled).
- Circuit Breaker: If a task fails 3 consecutive times, Alas halts and notifies via OnePush rather than continuing endlessly.

## Cross-Cutting Concerns

**Logging:** Centralized via `module/logger.py` with sensitive data redaction (`module/handler/sensitive_info.py`).
**Validation:** Pydantic models for config options (`module/config/argument/`).
**OCR Normalization:** Regex post-processing, digit substitutions, and counter fixups (`module/ocr/ocr.py`).

---

*Architecture analysis: 2026-09-11*
