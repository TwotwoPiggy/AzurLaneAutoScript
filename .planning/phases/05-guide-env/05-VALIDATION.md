---
phase: 05
slug: guide-env
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-12
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | PowerShell Parser API + pytest 7.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pwsh -NoProfile -Command "[System.Management.Automation.Language.Parser]::ParseFile('deploy/optimize/check_env.ps1', [ref]\$null, [ref]\$null)"` |
| **Full suite command** | `pwsh -NoProfile -File deploy/optimize/check_env.ps1; python -m pytest tests/unit/test_mumu_health.py` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick syntax/parser check
- **After every plan wave:** Run full validation suite (PowerShell static + execution test, pytest check)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | ENV-01 | T-05-01 | .reg 语法符合 Windows Registry 5.00，路径精确绑定 | static | `Get-Content deploy/optimize/enable_tdr_delay_8s.reg` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | ENV-02 | — | 包含 MuMu 12 性能分配与关闭后台保活核心指南 | doc | `Select-String -Path doc/low_spec_tuning_guide.md -Pattern "customer.app_keptlive"` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 2 | ENV-03 | T-05-02 | PowerShell 脚本只读执行不请求管理员提权，解析无语法错误 | integration | `[System.Management.Automation.Language.Parser]::ParseFile("deploy/optimize/check_env.ps1", [ref]$null, [ref]$null)` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 2 | ENV-02 | — | connection.py 在 MuMu 未生效 NemuIPC 时输出友好警告日志 | unit | `python -m pytest tests/unit/test_mumu_health.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `deploy/optimize/` — 创建优化脚本与配置存放目录
- [ ] `tests/unit/test_mumu_health.py` — connection.py 诊断提示的单元测试桩

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Windows 图形设置界面视觉核对 | ENV-01 | 依赖 Windows 操作系统 GUI 渲染与用户显示卡设置界面 | 打开“系统 -> 屏幕 -> 显示卡/图形设置”，核对 MuMuPlayer 绑定高性能、Thorium 绑定节能 |
| MuMu 12 设置中心界面参数核对 | ENV-02 | 模拟器独立客户端 GUI 设置 | 启动 MuMu 12 设置中心，核对 2核/3GB/DirectX/30帧/保活已关闭 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-12
