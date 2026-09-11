# Codebase Structure

**Analysis Date:** 2026-09-11

## Directory Layout

```
AzurLaneAutoScript/
├── alas.py                     # CLI entry point for scheduler & headless automation
├── gui.py                      # Web service entry point (ASGI Uvicorn + PyWebIO)
├── docker-compose.yml          # Container configuration for headless deployment
├── requirements-in.txt         # Unpinned direct dependency declarations
├── requirements.txt            # Pinned dependency manifest
├── assets/                     # Target visual templates and UI masks by server
│   ├── cn/                     # Simplified Chinese templates
│   ├── en/                     # English server templates
│   ├── jp/                     # Japanese server templates
│   ├── tw/                     # Traditional Chinese server templates
│   ├── gui/                    # WebUI static icons
│   └── mask/                   # OpenCV binary image masks
├── bin/                        # Platform binaries and ADB helpers
├── campaign/                   # Campaign map data, grid layouts, and route definitions
│   ├── campaign_main/          # Main storyline chapters (1-1 to 15-4)
│   ├── campaign_hard/          # Hard mode maps
│   ├── campaign_war_archives/  # Permanent war archive event maps
│   └── event_YYYYMMDD_<server>/# Historical and active limited-time event maps
├── config/                     # Configuration templates and defaults
│   ├── template.json           # Master config schema and default values
│   └── deploy.template*.yaml   # Deployment config templates (Windows/Linux/Docker/AidLux)
├── deploy/                     # Deployment helper scripts and environment setup
├── dev_tools/                  # Developer utilities (template extraction, Lua unpacker)
├── module/                     # Core backend source code (55 subpackages)
│   ├── base/                   # Vision primitives, Button, Template, and BaseModule
│   ├── device/                 # Hardware connection, screenshot methods, touch injection
│   ├── config/                 # Config loader, code generator, and watcher
│   ├── ui/                     # Directed graph page routing system
│   ├── handler/                # Modal dialog and alert interception (InfoHandler)
│   ├── combat/                 # Tactical battle state machine & submarine actions
│   ├── campaign/               # Map runner and tactical execution
│   ├── map/                    # Grid representations, obstacles, and A* pathfinding
│   ├── map_detection/          # Grid detection, homography, and tile identification
│   ├── ocr/                    # Neural network OCR inference and string normalization
│   ├── webui/                  # FastAPI routes, PyWebIO views, and process manager
│   ├── notify/                 # Multi-channel push notification service (OnePush)
│   └── <feature>/              # 40+ specific gameplay modules (dorm, research, os, etc.)
├── submodule/                  # Git submodules and bridge connectors
│   ├── AlasFpyBridge/          # Python bridge
│   └── AlasMaaBridge/          # Integration with MAA (MaaFramework) touch and engine
├── tests/                      # Pytest unit tests for deterministic algorithms
└── webapp/                     # Desktop Electron + Vue 3 GUI client application
    ├── packages/
    │   ├── main/               # Electron main process (lifecycle, IPC)
    │   ├── preload/            # Electron secure preload bridge
    │   └── renderer/           # Vue 3 reactive dashboard UI
    └── scripts/                # Vite build and watch scripts
```

## Directory Purposes

**`module/base/`:**
- Purpose: Fundamental automation building blocks and computer vision wrappers.
- Contains: `Button`, `Template`, `ModuleBase`, state looping generators (`loop()`), image utils, and execution timers.
- Key files: `module/base/base.py`, `module/base/button.py`, `module/base/utils.py`, `module/base/timer.py`.

**`module/device/`:**
- Purpose: Multi-platform device communication, frame capture, and touch dispatch.
- Contains: ADB socket clients, auto-reconnection wrappers, screenshot methods (DroidCast, Scrcpy, NemuIPC, LDOpenGL), touch drivers (MaaTouch, minitouch, Hermit).
- Key files: `module/device/device.py`, `module/device/connection.py`, `module/device/screenshot.py`, `module/device/control.py`.

**`module/config/`:**
- Purpose: Configuration file management, dynamic attribute generation, and reactive reload.
- Contains: Schema readers, Pydantic argument models, AST code generators, and file system watchers.
- Key files: `module/config/config.py`, `module/config/code_generator.py`, `module/config/config_generated.py`, `module/config/watcher.py`.

**`module/ui/`:**
- Purpose: State graph traversal across Azur Lane menu screens.
- Contains: Graph node model (`Page`), path solver (`init_connection`), page verification buttons.
- Key files: `module/ui/ui.py`, `module/ui/page.py`, `module/ui/assets.py`.

**`module/campaign/` & `campaign/`:**
- Purpose: Execution strategies for sorties, combat chapters, and event stages.
- Contains: Map state machines, boss-rush logic, ammo and health management, grid point classes.
- Key files: `module/campaign/run.py`, `module/campaign/campaign_base.py`, `module/campaign/os_run.py`.

**`module/ocr/`:**
- Purpose: Text detection and reading from live game frames.
- Contains: CNOCR/MXNet inference pipelines, character dictionary lookups, regex fixup rules.
- Key files: `module/ocr/al_ocr.py`, `module/ocr/ocr.py`, `module/ocr/rpc.py`.

**`module/webui/`:**
- Purpose: Web-based control panel and API service.
- Contains: PyWebIO dashboard UI, FastAPI endpoints, subprocess management for multiple Alas bots.
- Key files: `module/webui/app.py`, `module/webui/process_manager.py`, `module/webui/widgets.py`.

**`webapp/`:**
- Purpose: Modern Electron desktop wrapper.
- Contains: Cross-platform desktop window shell, Vue 3 renderer, multi-config launcher.
- Key files: `webapp/package.json`, `webapp/packages/renderer/src/App.vue`.

## Key File Locations

**Entry Points:**
- `alas.py`: Main CLI scheduler entry point.
- `gui.py`: Main WebUI / API server entry point.
- `webapp/packages/main/index.ts`: Electron desktop client entry point.

**Configuration:**
- `config/template.json`: Master JSON schema for all Alas configurations.
- `config/deploy.template.yaml`: Master deployment YAML configuration.
- `module/config/config_generated.py`: Auto-generated property classes for IDE intellisense.

**Core Logic:**
- `module/base/base.py`: Central `ModuleBase` class providing perception and action primitives.
- `module/device/device.py`: Aggregated device driver facade.
- `module/ui/ui.py`: UI page navigation engine.
- `module/combat/combat.py`: Tactical combat loop and decision logic.

**Testing:**
- `tests/`: Automated unit tests directory.
- `tests/shop_event/test_item.py`: OCR character correction tests.
- `tests/island_handler/test_production_plan_calculator.py`: Island minigame production optimization tests.

## Naming Conventions

**Files:**
- Python files: `snake_case.py` (e.g., `campaign_base.py`, `process_manager.py`).
- Assets files: `assets.py` placed adjacent to the domain logic (e.g. `module/combat/assets.py`, `module/ui/assets.py`).
- TypeScript / Vue: `kebab-case` or `PascalCase.vue` for components; `camelCase.ts` for utilities.

**Directories:**
- Python packages: `snake_case` (e.g., `map_detection`, `event_hospital`, `private_quarters`).
- Campaign map directories: `event_YYYYMMDD_<server>` (e.g. `event_20260908_cn`).

**Classes & Constants:**
- Domain classes: `PascalCase` (e.g., `AzurLaneAutoScript`, `ModuleBase`, `CampaignRun`).
- UI Buttons & Templates: `SCREAMING_SNAKE_CASE` (e.g., `BATTLE_PREPARATION`, `DOCK_CHECK`, `POPUP_CONFIRM`).

## Where to Add New Code

**New In-Game Task / Feature:**
- Primary logic: Create a new subdirectory under `module/<feature_name>/` (e.g., `module/new_feature/new_feature.py`).
- Inherit from `UI` or `ModuleBase`.
- Add UI assets in `module/<feature_name>/assets.py` using `Button` or `Template`.
- Expose the method on `AzurLaneAutoScript` in `alas.py` (e.g., `def new_feature(self): ...`).
- Declare the config schema in `config/template.json` under a new section.
- Run `dev_tools/requirements_updater.py` or `python -m module.config.code_generator` to regenerate `config_generated.py`.

**New Campaign / Event Map:**
- Create stage directory in `campaign/event_YYYYMMDD_<server>/`.
- Define map grid matrix, fleet spawn points, and strategy overrides.
- Inherit from `CampaignBase` (`module/campaign/campaign_base.py`).

**Shared Primitives & Utilities:**
- Shared image manipulation or math: `module/base/utils.py`.
- Shared device / ADB operations: `module/device/method/utils.py`.
- OCR parsing rules: `module/ocr/ocr.py`.

**Tests:**
- Pure logic / computation tests: Add to `tests/<feature>/test_<name>.py`.

## Special Directories

**`.planning/`:**
- Purpose: GSD workflow state, codebase documentation, and phase specifications.
- Generated: Semi-automated by GSD workflows.
- Committed: Tracked in git repository.

**`log/`:**
- Purpose: Runtime execution logs and crash dumps (`log/error/<timestamp>/`).
- Generated: Yes.
- Committed: No (ignored by `.gitignore`).

**`screenshots/`:**
- Purpose: Saved drop records and AzurStats upload caches.
- Generated: Yes.
- Committed: No (ignored by `.gitignore`).

---

*Structure analysis: 2026-09-11*
