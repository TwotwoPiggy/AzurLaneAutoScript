# Testing Patterns

**Analysis Date:** 2026-09-11

## Test Framework

**Runner:**
- Python Backend: `pytest`
  - Config: Default discovery (`pytest.ini` / command line invocation)
- Desktop Frontend: `playwright` (1.15.1) running headless browser end-to-end tests

**Assertion Library:**
- Python: Native Python assertions (`assert actual == expected`) with `pytest.mark.parametrize`
- Node.js: Playwright assertions (`expect(...)`)

**Run Commands:**
```bash
# Run all Python backend unit tests
python -m pytest tests/ -v

# Run a specific test suite
python -m pytest tests/shop_event/test_item.py -v

# Run desktop webapp tests
cd webapp && npm test
```

## Test File Organization

**Location:**
- Python tests: Dedicated `tests/` directory mirroring feature domains:
  - `tests/island/`
  - `tests/island_handler/`
  - `tests/meowfficer/`
  - `tests/shop_event/`
- Webapp tests: `webapp/tests/` (`webapp/tests/app.spec.js`)

**Naming:**
- Files: `test_<feature>.py`
- Test classes: `Test<FeatureName>` (e.g. `TestCounterOcrAfterProcess`, `TestProductionPlanCalculator`)
- Test methods: `test_<behavior_or_scenario>` (e.g. `test_letter_revision`, `test_fixup_documented_examples`)

## Test Structure

**Suite Organization:**
```python
import pytest
from module.shop_event.item import CounterOcr

class TestCounterOcrAfterProcess:
    """Test pure string post-processing without image/model dependencies."""

    ocr = CounterOcr([], name='Test_counter_ocr')

    @pytest.mark.parametrize('raw, expected', [
        ('14/15', '14/15'),
        ('D', '0'),
        ('B', '8'),
        ('I4/IS', '14/15'),
        ('55', '5/5'),
    ])
    def test_letter_revision(self, raw, expected):
        assert self.ocr.after_process(raw) == expected
```

**Patterns:**
- **Parametrization:** Heavy usage of `@pytest.mark.parametrize` to test extensive ranges of character revisions, mathematical edge cases, and threshold variations.
- **Fixture Stubs:** Using lightweight subclasses or dict stubs to mock complex state (e.g., `AllUnlockedTechnology(dict)` in `test_production_plan_calculator.py`).

## Mocking

**Approach:**
- Physical device connections (`Device`, `AdbClient`) and live OCR models (`cnocr`, `mxnet`) are **not** spun up during standard unit testing.
- Tests target pure analytical, planning, and string-processing functions.
- Class inheritance and mock dictionary fixtures provide deterministic input states.

**What to Mock:**
- External ADB socket calls and screenshot acquisition.
- Network API calls (AzurStats, OnePush, remote updater).
- Game client UI responses.

**What NOT to Mock:**
- Mathematical algorithms (island production linear solving, route cost functions).
- Configuration parser logic and deep dictionary helpers (`module/config/deep.py`).
- OCR regex and string sanitization pipelines.

## Fixtures and Factories

**Test Fixtures:**
```python
@pytest.fixture(scope='module')
def all_tech_koi_solved():
    calc = make_calculator(
        AllUnlockedTechnology(),
        restaurant_settings={601: {'grade': 'gold', 'waitress_slots': ('Chao_Ho', 'none')}},
        daily_profit_lower_limit=10,
    )
    calc.solve_production_plan()
    return calc
```

## Coverage

**Requirements:**
- No strict global coverage threshold enforced via CI.
- Focus is on zero-regression verification for pure algorithmic modules (math calculators, OCR parsers, minigame planners).

## Test Types

**Unit Tests:**
- Scope: In-memory algorithmic calculators, string transformers, configuration parsing.
- Execution: Fast (< 5 seconds for complete `tests/` suite).

**End-to-End Tests:**
- Webapp: Automated Electron launching and UI verification via Playwright (`webapp/tests/app.spec.js`).
- Game Automation: Typically validated interactively by developers on live Android emulators due to visual non-determinism of the live game.

---

*Testing analysis: 2026-09-11*
