# Codebase Concerns

**Analysis Date:** 2026-09-11

## Tech Debt

**Python 3.7 & Apache MXNet Dependency Lock:**
- Issue: Alas relies heavily on `cnocr==1.2.2` and `mxnet==1.6.0` (`requirements-in.txt`), pinning the entire production runtime to Python 3.7.6 64-bit. Apache MXNet officially entered the Apache Attic (retired) in 2023 and lacks prebuilt binary wheels for modern Python releases (3.10–3.13) and newer operating systems.
- Files: `requirements-in.txt`, `config/deploy.template.yaml:30`, `module/ocr/al_ocr.py`.
- Impact: Blocks upgrading to contemporary Python features (native pattern matching, enhanced typing, asyncio improvements), prevents seamless setup on newer Linux distros, and requires bundling a frozen Python 3.7 toolkit.
- Fix approach: Migrate OCR engine to an ONNX Runtime-based stack (such as RapidOCR, PaddleOCR ONNX, or modern CNOCR 2.x) that runs natively across Python 3.8–3.12 without MXNet.

**Legacy Campaign Code Accumulation (Repository Bloat):**
- Issue: Over 130 past event campaign scripts dating back to 2018 remain committed in `campaign/` (e.g., `campaign/event_20200227_cn/`, `campaign/war_archives_20180607_cn/`).
- Files: `campaign/*` (134 directories, 76KB `campaign/Readme.md`).
- Impact: Increases git clone transfer size (several gigabytes), slows down workspace tooling, and pollutes search results with unmaintained and deprecated map routines.
- Fix approach: Archive non-recurring historical events into a separate data package or download-on-demand assets repository, retaining only active War Archives and current major event maps.

## Known Bugs & Edge Cases

**ADB Server Hijacking & Port Conflict:**
- Symptoms: Sudden ADB disconnection, `ConnectionResetError`, or emulator instance loss during execution.
- Files: `module/device/connection.py`, `config/deploy.template.yaml:49-60`.
- Trigger: Third-party Android emulators (Nox, LDPlayer, MEmu, MuMu) shipping different bundled versions of `adb.exe` that kill and restart the local 5037 daemon.
- Workaround: The `ReplaceAdb: true` setting aggressively overrides emulator ADB binaries with Alas's bundled ADB client, but requires administrative/write permissions and may conflict with other developer tools.

**Accidental Config Stalling after Server Maintenance:**
- Symptoms: In rare conditions, tasks stall indefinitely or fail to re-read updated settings after game servers recover from maintenance.
- Files: `alas.py:563-568`.
- Workaround: Forced cache invalidation via `del_cached_property(self, 'config')` in `loop()`.

## Security Considerations

**Unauthenticated Local API & Remote Tunneling:**
- Risk: The WebUI defaults to binding on `0.0.0.0:22267` without a mandatory password (`gui.py:33, 57`). When users activate reverse SSH tunneling (`RemoteAccess`) without configuring `--key`, the control panel becomes publicly exposed.
- Files: `gui.py`, `module/webui/remote_access.py`, `module/webui/pin.py`.
- Current mitigation: Warning logged in terminal; optional PIN setting exists.
- Recommendations: Enforce random or user-specified password protection whenever `RemoteAccess` or external network binding is enabled.

**Credential & Account Exposure in Logs:**
- Risk: Game client UID, nickname, and account info could be leaked if raw logs or screenshots are shared in bug reports.
- Files: `module/handler/sensitive_info.py`, `module/logger.py`.
- Current mitigation: Built-in `handle_sensitive_image` blurs UID and account areas before saving to `log/error/`.
- Recommendations: Audit redaction coordinates periodically whenever Yostar/Bilibili modifies main menu layouts.

## Performance Bottlenecks

**OCR Model Initialization & Memory Overhead:**
- Problem: Importing MXNet and CNOCR models consumes 300MB–800MB RAM per Alas instance.
- Files: `module/base/base.py:67-100` (`early_ocr_import`), `module/ocr/rpc.py`.
- Cause: MXNet loads deep learning weight graphs into process memory. Running multiple Alas instances concurrently leads to heavy memory multiplication.
- Improvement path: Leverage the built-in standalone OCR microservice (`UseOcrServer: true`, port 22268) to share a single OCR process across all running bot instances.

**High-Frequency Image Template Matching in Tight Loops:**
- Problem: CPU spikes during complex map detection or dense button polling.
- Files: `module/base/base.py:appear`, `module/map_detection/utils.py`.
- Cause: Full-frame `cv2.matchTemplate` executed every 100–300ms.
- Improvement path: Restrict search windows to localized bounding boxes (`Button.area`) rather than full 1280x720 scans whenever screen context is known.

## Fragile Areas

**Strict 1280x720 Screen Resolution Coupling:**
- Files: `module/device/screenshot.py:94-96`, `module/base/button.py`.
- Why fragile: Every single button bounding box, OCR crop region, and map tile homography matrix assumes a fixed 1280x720 canvas. A 1080p or non-16:9 aspect ratio breaks button detection completely.
- Safe modification: Must maintain the 1280x720 resolution requirement in documentation and validate device resolution during startup (`check_screen_size`).

**Client UI Redesigns & Multi-Server Font Discrepancies:**
- Files: `module/ui/page.py`, `module/ui/ui.py:40-45`, `assets/cn/`, `assets/en/`, `assets/jp/`.
- Why fragile: Yostar/Bilibili updates occasionally alter navigation menus or button textures. Localization text length differences (notably English title wrapping) frequently invalidate color/similarity checks.
- Test coverage: Zero automated UI regression tests; relies on manual developer patching.

## Test Coverage Gaps

**Core Combat and Map State Machines:**
- What's not tested: `module/combat/combat.py`, `module/campaign/run.py`, `module/map/map.py`.
- Files: Entire `module/campaign/` and `module/combat/`.
- Risk: Refactoring map navigation or combat loops could cause subtle softlocks or infinite retreat-advance loops in production.
- Priority: High.

**Device & Input Drivers:**
- What's not tested: MaaTouch, minitouch, DroidCast, and scrcpy capture drivers.
- Files: `module/device/method/*.py`.
- Risk: Changes to connection retries or buffer management can cause hardware desynchronization or undetected hangs.
- Priority: Medium.

---

*Concerns audit: 2026-09-11*
