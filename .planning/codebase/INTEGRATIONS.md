# External Integrations

**Analysis Date:** 2026-09-11

## APIs & External Services

**Push Notifications (OnePush):**
- Provider: `onepush` (1.4.0) library wrapper (`module/notify/notify.py`)
  - Supported services: Bark, DingTalk, Discord Webhook, Email (SMTP), FeiShu (Lark), ServerChan (方糖), PushPlus, PushDeer, Qmsg, Telegram Bot, Wechat Work (企业微信), GoCQHTTP, Custom Webhook
  - Auth/Configuration: User YAML snippet in `config/{instance}.json` under `Error_OnePushConfig` (e.g., `provider: telegram`, `token: ...`, `chat_id: ...`)
  - Usage: Pushes alerts on script crash, task consecutive failures (>= 3 times), human takeover requests, and major drops.

**Community Statistics Platform (AzurStats):**
- Endpoint: `https://azurstats.lyoko.io/api` (`module/statistics/azurstats.py`)
  - SDK/Client: `requests` Session with connection pooling (`HTTPAdapter(max_retries=3)`)
  - Auth: Optional user token `DropRecord_AzurStatsID`
  - Purpose: Uploads battle drops, blueprint drops, and commission results anonymously or linked to an AzurStats user account to build global drop-rate statistics.

**Discord Rich Presence:**
- Service: Discord RPC via `pypresence` (4.2.1) (`module/webui/discord_presence.py`)
  - Client ID: Hardcoded application ID registered for Alas
  - Purpose: Displays real-time Alas activity, running instance name, current task (e.g., Campaign, Research, Opsi), and elapsed time in Discord status.

**Remote Access & Reverse Tunneling:**
- Service: Reverse SSH tunneling via LocalShare (`app.azurlane.cloud`) (`module/webui/remote_access.py`)
  - Client: OpenSSH client (`ssh.exe` or system `ssh`)
  - Configuration: `Deploy.RemoteAccess` in `config/deploy.yaml`
  - Purpose: Allows users to securely manage and view the WebUI remotely from outside the local network without exposing router ports.

## Device & Emulator Integrations

**Android Debug Bridge (ADB):**
- Implementation: `adbutils.AdbClient` socket connection over `127.0.0.1:5037` (`module/device/connection.py`)
- Auto-detection & Management:
  - Scans and connects to running emulators: MuMu Player (12/X/6), LDPlayer (雷电), Nox (夜神), BlueStacks, MEmu (逍遥), WSA (Windows Subsystem for Android)
  - `ReplaceAdb` capability: Replaces outdated emulator ADB executables with bundled modern ADB to prevent server restart ping-pong.
  - Commands executed via ADB: `input tap`, `screencap`, port forwarding, package detection (`dumpsys window | grep mCurrentFocus`).

**Screen Capture Drivers (Methods):**
- `aScreenCap`: Native compiled binary pushed to device `/data/local/tmp/` (`module/device/method/ascreencap.py`)
- `DroidCast`: Custom lightweight APK streaming uncompressed frames over HTTP port forward (`module/device/method/droidcast.py`)
- `scrcpy`: Video stream capture over socket (`module/device/method/scrcpy.py`)
- `nemu_ipc`: Direct memory / IPC frame-grabbing for MuMu / Nemu emulator (`module/device/method/nemu_ipc.py`)
- `ldopengl`: Shared memory framebuffer capture for LDPlayer (`module/device/method/ldopengl.py`)
- `uiautomator2`: Fallback Android instrumentation screenshot and XML hierarchy dump (`module/device/method/uiautomator_2.py`)

**Input Injection Drivers (Methods):**
- `MaaTouch`: MAA-developed high-frequency Android touch daemon (`module/device/method/maatouch.py`)
- `minitouch`: OpenSTF touch daemon binary for rapid touch events (`module/device/method/minitouch.py`)
- `Hermit`: Alas custom input daemon (`module/device/method/hermit.py`)
- `nemu_ipc`: Direct input injection into MuMu emulator process
- Native ADB `input swipe / tap`: Universal fallback

## Data Storage

**Databases:**
- None (File-based JSON/YAML state store). No external SQL or NoSQL database required.

**File Storage:**
- Local filesystem only:
  - Config storage: `config/*.json`, `config/deploy.yaml`
  - Error dumps: `log/error/<timestamp>/` (saving last 60 screenshots and log slice)
  - Drop screenshots: `screenshots/<genre>/` (for AzurStats or local inspection)
  - Runtime logs: `log/<date>_<config_name>.txt`

**Caching & State:**
- In-memory property cache via `@cached_property` and `del_cached_property` in Python.
- Image cache in `Device.screenshot_deque` (sliding buffer of recent screenshots).

## Authentication & Identity

**WebUI Authentication:**
- Method: Simple token/password gate (`gui.py --key <password>`, `module/webui/pin.py`)
- Implementation: When password is set, WebUI prompts for PIN/password before granting dashboard access. No multi-tenant user table.

**Game Authentication:**
- Autonomous Game Login: Handled by `module/handler/login.py`
  - Interacts with game login UI buttons (server selection, login screen, account switch detection).
  - Credentials stored natively inside the Android emulator's game client data, never handled as plaintext by Alas.

## Monitoring & Observability

**Error Tracking:**
- Local error capture: On unexpected crashes or `GamePageUnknownError`, Alas captures the last 60 screenshots from circular buffer and writes sanitized logs to `log/error/<timestamp>/`.
- Sensitive Info Sanitization: `module/handler/sensitive_info.py` blurs UID, player nickname, gems, and sensitive regions from error screenshots and logs.

**Logs:**
- Rich logger configured in `module/logger.py`:
  - Console handler with syntax highlighting and task dividers
  - Rotating file logger per instance (`log/<date>_<instance>.txt`)

## CI/CD & Deployment

**Hosting & Distribution:**
- GitHub Releases (`LmeSzinc/AzurLaneAutoScript`): Main distribution channel for update zip packages and releases.
- Fast CDN & Git Mirrors: `git://git.lyoko.io/AzurLaneAutoScript` and `https://mirrors.aliyun.com/pypi/simple` for users in mainland China.

**CI Pipelines:**
- `.github/workflows/`:
  - Automated build and releases
  - Code generation check and dependency sync
  - Pre-commit linting via `simple-git-hooks` and `eslint` for `webapp/`

## Environment Configuration

**Required Environment & Arguments:**
- `WebuiHost` / `WebuiPort`: Network bind address (defaults to `0.0.0.0:22267`)
- `Emulator_Serial`: ADB serial (e.g. `127.0.0.1:5555` or `auto`)
- `Emulator_PackageName`: Azur Lane client package (auto-detected: `com.bilibili.azurlane`, `com.YoStarEN.AzurLane`, `com.YoStarJP.AzurLane`, `com.hkmanjuu.azurlane.gp`)

**Secrets Location:**
- Stored exclusively in local files: `config/{config_name}.json` and `config/deploy.yaml`.
- Git configuration explicitly ignores user config files (`config/*.json` where filename is not template) via `.gitignore`.

---

*Integration audit: 2026-09-11*
