# Technology Stack

**Analysis Date:** 2026-09-11

## Languages

**Primary:**
- Python 3.7.6 64-bit - Core backend automation engine, task scheduler, CV algorithms, OCR, and device communication (`alas.py`, `module/`, `campaign/`, `dev_tools/`)
- TypeScript 4.4.2 - Desktop GUI application frontend and Electron preload/main process orchestration (`webapp/packages/`)
- JavaScript (Node.js) - Electron build pipelines, build scripts, development server (`webapp/scripts/`, `webapp/electron-builder.config.js`)

**Secondary:**
- HTML / CSS (SCSS/CSS3) - WebUI templates, PyWebIO widgets, and Vue component styles (`webapp/packages/renderer/`, `module/webui/`)
- Shell / Batch (`.bat`, `.sh`) - Platform startup scripts, Git hooks, ADB patchers, installer bundles (`dev_tools/alas2.bat`, `deploy/`)
- Lua - Game data unpacking / parsing tools for reading client configurations (`dev_tools/slpp.py`)

## Runtime

**Environment:**
- CPython 3.7.6 (Target production runtime, specifically x86_64 Windows/Linux/Docker/AidLux)
- Node.js >= 14.14 / npm >= 7.7 (Desktop WebApp build environment)
- Electron 15.1.0 (Desktop client GUI wrapper)
- Android Debug Bridge (ADB) daemon & socket server (`adbutils` bundled adb binaries)

**Package Manager:**
- Python: `pip` (dependency sources defined in `requirements-in.txt` compiled to `requirements.txt`)
- Node.js: `npm` / `yarn` (lockfiles: `webapp/package-lock.json`, `webapp/yarn.lock` present)

## Frameworks

**Core Automation & Computer Vision:**
- OpenCV (`opencv-python`): Image processing, template matching (`cv2.matchTemplate`), color space conversion, denoising (`cv2.fastNlMeansDenoising`)
- NumPy (1.16.6) & SciPy (1.4.1): Matrix representations of screen frames, numerical distance computation, coordinate transformation
- Pillow (`PIL`): Image cropping, format encoding/decoding, save operations
- imageio (2.27.0): GIF recording and visual debugging sequences

**OCR (Optical Character Recognition):**
- cnocr (1.2.2): Character and text recognition engine
- mxnet (1.6.0): Neural network runtime powering cnocr model inference
- al_ocr (`module/ocr/al_ocr.py`): Alas-specific OCR wrapper and digit/character sanitization

**Device Communication & Automation:**
- adbutils (0.11.0): High-level ADB client protocol implementation
- uiautomator2 (2.16.17) & uiautomator2cache (0.3.0.1): Android UI Automator driver and hierarchy dumper
- MaaTouch, minitouch, scrcpy, nemu_ipc, ldopengl: High-performance click/touch and frame acquisition submodules (`module/device/method/`)

**Web Service & GUI Server:**
- Starlette (0.14.2) & Uvicorn (0.17.6): ASGI web server and routing framework (`gui.py`, `module/webui/app.py`)
- PyWebIO (1.6.2): Interactive web UI component rendering and event dispatching
- alas-webapp (0.3.7): Static assets and web server bundles
- ZeroRPC (0.6.3) & PyZMQ (22.3.0): RPC bridge between main script and dedicated OCR microservice

**Frontend Desktop UI (Webapp):**
- Vue 3 (3.2.19) & Vue Router (4.0.11): Reactive frontend component architecture
- Vite (2.6.2): Frontend bundler and HMR dev server
- Ant Design Icons Vue (6.0.1): Icon library for desktop client

## Key Dependencies

**Critical:**
- `opencv-python`: Foundational vision layer for all UI state detection and button matching (`module/base/utils.py`, `module/base/button.py`)
- `adbutils`: Core Android connection bridge over TCP/USB sockets (`module/device/connection.py`)
- `mxnet` & `cnocr`: In-game text recognition for timers, item counters, combat stats, and fleet names (`module/ocr/`)
- `pyyaml`: Configuration serialisation for user configs and deployment settings (`module/config/`)
- `pydantic`: Schema validation and type parsing for configurations (`module/config/argument/`)
- `inflection`: String casing conversions between camelCase tasks and snake_case method handlers (`alas.py`)

**Infrastructure & Utilities:**
- `rich` (11.2.0): CLI formatting, colored log outputs, rule dividers, and status tables (`module/logger.py`)
- `onepush` (1.4.0): Multi-channel push notification service for crash and task reporting (`module/notify/`)
- `pypresence` (4.2.1): Discord Rich Presence integration (`module/webui/discord_presence.py`)
- `psutil` (5.9.3): Process inspection, emulator lifecycle monitoring, and resource management (`module/device/method/utils.py`)
- `jellyfish` (0.11.2): Approximate string matching for OCR text corrections (`module/ocr/ocr.py`)

## Configuration

**Environment & Setup:**
- Deployment config: `config/deploy.yaml` (copied from templates such as `config/deploy.template-cn.yaml` or `config/deploy.template.yaml`)
- Per-instance task config: `config/{config_name}.json` (e.g. `config/alas.json`), generated from `config/template.json`
- Code generation: `module/config/code_generator.py` compiles `config/template.json` into typed Python accessors in `module/config/config_generated.py`
- Hot-reloading: `module/config/watcher.py` watches file system change timestamps to trigger runtime reload without restarting process

**Build & Tooling:**
- WebApp bundling: `webapp/package.json` with `npm run build` using Vite (`webapp/scripts/build.js`)
- Electron distribution: `electron-builder.config.js` producing directory distributions and portable executables
- Requirements generation: `dev_tools/requirements_updater.py` updating pinned versions from `requirements-in.txt`

## Platform Requirements

**Development:**
- Windows 10/11 64-bit or Linux x86_64
- Python 3.7.6 64-bit (or pyenv / conda environment pinned to 3.7.x)
- Node.js 14.x - 18.x with npm / yarn
- Git with submodules support

**Production:**
- Native Windows 64-bit desktop environment with Android emulator (MuMu, LDPlayer, Nox, BlueStacks, MEmu, WSA)
- Headless Linux / Docker container with remote emulator ADB connection (`docker-compose.yml`)
- ARM64 Android device with AidLux / Termux (`config/deploy.template-AidLux-cn.yaml`)
- Fixed display resolution requirement: Game client MUST be set to 1280x720 landscape (16:9 ratio)

---

*Stack analysis: 2026-09-11*
