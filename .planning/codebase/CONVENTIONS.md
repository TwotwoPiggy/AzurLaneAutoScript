# Coding Conventions

**Analysis Date:** 2026-09-11

## Naming Patterns

**Files & Directories:**
- Python modules: `snake_case.py` (e.g., `campaign_base.py`, `info_handler.py`)
- Assets files: Co-located `assets.py` inside each module package (e.g., `module/dorm/assets.py`)
- Test files: `test_<module_or_feature>.py` under `tests/`
- TypeScript/Vue files: `kebab-case.ts` / `PascalCase.vue`

**Classes:**
- `PascalCase` for all classes and models:
  ```python
  class AzurLaneAutoScript: ...
  class RewardCommission(UI): ...
  class Button: ...
  ```

**Functions & Methods:**
- `snake_case` for all functions and class methods:
  ```python
  def ui_ensure(self, page_target): ...
  def appear_then_click(self, button, offset=0, interval=0): ...
  def get_next_task(self): ...
  ```

**Variables & Attributes:**
- Local variables and attributes: `snake_case`
- Configuration accessors: `Category_OptionName` pattern (UpperCamelCase joined by underscore):
  ```python
  self.config.Emulator_Serial
  self.config.Optimization_WhenTaskQueueEmpty
  self.config.Error_SaveError
  ```

**UI Constants (Buttons, Templates, Grids):**
- `SCREAMING_SNAKE_CASE` for all `Button`, `Template`, and `Grid` instances:
  ```python
  BATTLE_PREPARATION = Button(area=(1025, 608, 1222, 672), color=(235, 177, 89), button=(1025, 608, 1222, 672))
  POPUP_CONFIRM = Button(area=(764, 523, 916, 574), color=(115, 166, 239), button=(764, 523, 916, 574))
  ```

**Page Instances:**
- Prefix `page_` followed by lowercase descriptor:
  ```python
  page_main = Page(MAIN_CHECK)
  page_campaign = Page(CAMPAIGN_CHECK)
  ```

## Code Style

**Python Formatting & Style:**
- Follows PEP 8 guidelines with 4-space indentation.
- Maximum line length generally kept under 120 characters.
- Explicit type annotations in new modules and utility functions (`typing.Optional`, `typing.Tuple`, `np.ndarray`).

**Linting & Hygiene:**
- ESLint + vue-tsc for desktop frontend (`webapp/`).
- Python code avoids wildcard imports except within internal module `assets.py` or `module/base/utils.py`.

## Import Organization

**Standard Grouping Order:**
1. Python standard library (`os`, `sys`, `time`, `datetime`, `re`, `threading`)
2. Third-party packages (`cv2`, `numpy`, `adbutils`, `inflection`, `rich`, `yaml`)
3. Internal framework primitives (`module.base.*`, `module.device.*`, `module.logger`, `module.exception`)
4. Domain modules, sibling utilities, and local `assets`

**Example:**
```python
import os
import time
from datetime import datetime

import cv2
import numpy as np

from module.base.button import Button
from module.base.decorator import cached_property
from module.base.timer import Timer
from module.exception import GameStuckError
from module.logger import logger
from module.ui.ui import UI
from module.dorm.assets import DORM_CHECK, DORM_FEED
```

## State Machine & Looping Conventions

**State Looping Sugar:**
All wait loops and polling actions MUST use `self.loop()`:
```python
# Standard UI wait and click pattern
for _ in self.loop():
    if self.appear(DORM_FEED):
        break
    if self.appear_then_click(DORM_CHECK, interval=1):
        continue

# Looping with explicit timeout
for _ in self.loop(timeout=10):
    if self.appear(TARGET_BUTTON):
        logger.info('Target found')
        break
else:
    logger.warning('Wait timed out')
```

**Property Caching Pattern:**
Use `@cached_property` for expensive component instantiation, and invalidate with `del_cached_property`:
```python
@cached_property
def device(self):
    return Device(config=self.config)

# Invalidate when reloaded
del_cached_property(self, 'device')
```

## Error Handling

**Guidelines:**
- Never silence unexpected exceptions with bare `except: pass`.
- Convert low-level timeouts or stuck loops into semantic domain exceptions:
  - `raise GameStuckError('Failed to leave battle screen after 30s')`
  - `raise RequestHumanTakeover('Dock is full and auto-retirement is disabled')`
  - `raise TaskEnd('Commission dispatched successfully')` (control flow termination)
- Catch specific errors at the top-level loop (`alas.py`) to trigger automated mitigation (screenshot dumping, game restart, device re-connection).

## Logging

**Framework:** Custom logger in `module/logger.py` based on `Rich`.

**Conventions:**
- Section Header: `logger.hr('Task Name', level=0)` (large banner), `level=1` (minor banner).
- Attribute/State Reporting: `logger.attr('OptionKey', value)` displays colorized key-value pairs.
- Informational: `logger.info('Message')` for standard state transitions.
- Warning/Error: `logger.warning(...)` for retried actions; `logger.critical(...)` before requesting human takeover.

**Example:**
```python
logger.hr('Start Commission', level=1)
logger.attr('Server', self.config.SERVER)
logger.info('Navigating to commission screen')
```

## Comments & Documentation

**When to Comment:**
- Document non-obvious pixel offsets, OCR regex quirks, and server-specific divergences (e.g. EN font width differences).
- Docstrings required on `ModuleBase` public methods and complex algorithms (e.g., A* map traversal, OCR post-processing).

---

*Convention analysis: 2026-09-11*
