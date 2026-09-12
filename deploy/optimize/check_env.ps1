<#
.SYNOPSIS
    Alas 弱机与模拟器运行环境自动化体检与自愈脚本 (AzurLaneAutoScript Environment Checker)

.DESCRIPTION
    针对老旧双核移动平台 (如 i5-4210H + GTX 960M/HD 4600) 在 7x24h 挂机时的关键环境指标进行自动化排查：
    1. Check-GpuTopology: 显卡拓扑枚举与 Windows 图形首选项 (DirectX UserGpuPreferences)
    2. Check-TdrDelay: WDDM TDR 驱动超时恢复注册表参数 (TdrDelay, TdrDdiDelay, TdrLevel)
    3. Check-MuMuConfig: MuMu 12 四重级联路径查找、NemuIPC external_renderer_ipc.dll 探测与后台保活配置校验
    4. Check-PageFileAndMemory: 物理/虚拟内存余量与 PageFile 是否驻留于 SSD

.PARAMETER Fix
    以管理员权限执行一键自愈：写入 TdrDelay=8 注册表，并自动写入探测到的 MuMu/Thorium/Alas GPU 首选项。

.PARAMETER Help
    显示帮助说明。
#>

[CmdletBinding()]
param(
    [switch]$Fix,
    [switch]$Help
)

$ErrorActionPreference = "Continue"

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Detailed
    exit 0
}

# ---------------------------------------------------------------------------
# 权限判定与自愈提权处理 (Fix 模式)
# ---------------------------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($Fix -and -not $isAdmin) {
    Write-Host "[INFO] 修复模式 (-Fix) 需要管理员权限，正在请求 UAC 提权..." -ForegroundColor Cyan
    try {
        $procPath = (Get-Process -Id $PID).Path
        Start-Process -FilePath $procPath -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Fix"
        exit 0
    }
    catch {
        Write-Host "[ERROR] 请求管理员提权失败: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 格式化输出辅助函数
# ---------------------------------------------------------------------------
function Write-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor DarkCyan
    Write-Host "  $Title" -ForegroundColor White
    Write-Host ("=" * 72) -ForegroundColor DarkCyan
}

function Write-Status {
    param(
        [ValidateSet("PASS", "WARN", "FAIL", "INFO")]
        [string]$Level,
        [string]$Message
    )
    switch ($Level) {
        "PASS" { Write-Host "  [PASS] " -ForegroundColor Green -NoNewline }
        "WARN" { Write-Host "  [WARN] " -ForegroundColor Yellow -NoNewline }
        "FAIL" { Write-Host "  [FAIL] " -ForegroundColor Red -NoNewline }
        "INFO" { Write-Host "  [INFO] " -ForegroundColor Cyan -NoNewline }
    }
    Write-Host $Message
}

# ---------------------------------------------------------------------------
# 1. 显卡拓扑与图形性能首选项检测 (Check-GpuTopology)
# ---------------------------------------------------------------------------
function Check-GpuTopology {
    Write-Header "1. GPU 硬件拓扑与 Windows 图形首选项检测"

    # 1.1 枚举显卡
    try {
        $gpus = Get-CimInstance Win32_VideoController -ErrorAction Stop
        foreach ($gpu in $gpus) {
            $ramGB = if ($gpu.AdapterRAM) { [math]::Round($gpu.AdapterRAM / 1GB, 2) } else { "N/A" }
            Write-Status "INFO" ("检测到显示适配器: {0} (显存: {1} GB, 驱动版本: {2})" -f $gpu.Name, $ramGB, $gpu.DriverVersion)
        }
    }
    catch {
        Write-Status "WARN" "获取显卡硬件拓扑失败: $($_.Exception.Message)"
    }

    # 1.2 检测 UserGpuPreferences
    $regPrefPath = "HKCU:\Software\Microsoft\DirectX\UserGpuPreferences"
    $prefProps = $null
    if (Test-Path $regPrefPath) {
        try {
            $prefProps = (Get-ItemProperty -Path $regPrefPath -ErrorAction SilentlyContinue).psobject.Properties
        } catch {}
    }

    # 判定 MuMuPlayer.exe
    $mumuPref = $prefProps | Where-Object { $_.Name -like "*MuMuPlayer.exe" }
    if ($mumuPref) {
        if ($mumuPref.Value -like "*GpuPreference=2;*") {
            Write-Status "PASS" ("MuMuPlayer 图形首选项正确配置为高性能独显: {0} -> {1}" -f (Split-Path $mumuPref.Name -Leaf), $mumuPref.Value)
        } else {
            Write-Status "WARN" ("MuMuPlayer 未配置为独显高性能 (当前: {0})，可能导致核显争抢或性能下降。" -f $mumuPref.Value)
        }
    } else {
        Write-Status "WARN" "Windows 图形首选项中未发现 MuMuPlayer.exe 显式绑定（建议设为高性能独显）。"
    }

    # 判定 thorium.exe
    $thoriumPref = $prefProps | Where-Object { $_.Name -like "*thorium.exe" }
    if ($thoriumPref) {
        if ($thoriumPref.Value -like "*GpuPreference=1;*") {
            Write-Status "PASS" ("Thorium 浏览器已正确绑定至节能核显: {0} -> {1}" -f (Split-Path $thoriumPref.Name -Leaf), $thoriumPref.Value)
        } else {
            Write-Status "WARN" ("Thorium 浏览器当前首选项为 {0}，建议绑定至节能核显 (GpuPreference=1;) 以释放独显显存。" -f $thoriumPref.Value)
        }
    } else {
        Write-Status "INFO" "Windows 图形首选项中未记录 thorium.exe（若未安装或未使用 Thorium 可忽略）。"
    }

    # 判定 AzurLaneAutoScript.exe
    $alasPref = $prefProps | Where-Object { $_.Name -like "*AzurLaneAutoScript.exe" }
    if ($alasPref) {
        if ($alasPref.Value -like "*GpuPreference=1;*") {
            Write-Status "PASS" ("Alas 桌面端已绑定至节能核显: {0} -> {1}" -f (Split-Path $alasPref.Name -Leaf), $alasPref.Value)
        } else {
            Write-Status "WARN" ("Alas 桌面端当前首选项为 {0}，建议绑定至节能核显 (GpuPreference=1;)。" -f $alasPref.Value)
        }
    } else {
        Write-Status "INFO" "Windows 图形首选项中未记录 AzurLaneAutoScript.exe。"
    }

    return @{
        MuMuPref = $mumuPref
        ThoriumPref = $thoriumPref
        AlasPref = $alasPref
    }
}

# ---------------------------------------------------------------------------
# 2. WDDM TDR 崩溃防范检测 (Check-TdrDelay)
# ---------------------------------------------------------------------------
function Check-TdrDelay {
    Write-Header "2. WDDM TDR 驱动超时恢复注册表检测"

    $tdrRegPath = "HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
    $tdrDelay = $null
    $tdrDdiDelay = $null
    $tdrLevel = $null

    if (Test-Path $tdrRegPath) {
        $regData = Get-ItemProperty -Path $tdrRegPath -ErrorAction SilentlyContinue
        if ($regData) {
            $tdrDelay = $regData.TdrDelay
            $tdrDdiDelay = $regData.TdrDdiDelay
            $tdrLevel = $regData.TdrLevel
        }
    }

    if ($null -ne $tdrDelay -and $tdrDelay -ge 8) {
        Write-Status "PASS" ("TdrDelay={0}s, TdrDdiDelay={1}s, TdrLevel={2} (防崩溃延长延迟已生效，显著抵御 TDR 141)" -f $tdrDelay, $tdrDdiDelay, $tdrLevel)
        return $true
    } elseif ($null -eq $tdrDelay) {
        Write-Status "WARN" "TdrDelay 未显式设置 (系统默认 2 秒)。双显卡高负载硬解或重切时容易触发 TDR 141 驱动重置黑屏。建议延长至 8 秒。"
        return $false
    } else {
        Write-Status "WARN" ("当前 TdrDelay={0}s 小于推荐值 8 秒。建议调整至 8 秒。" -f $tdrDelay)
        return $false
    }
}

# ---------------------------------------------------------------------------
# 3. MuMu 12 安装路径、NemuIPC 与保活配置检测 (Check-MuMuConfig)
# ---------------------------------------------------------------------------
function Check-MuMuConfig {
    Write-Header "3. MuMu 12 模拟器安装、NemuIPC DLL 与保活配置检测"

    $mumuPath = $null

    # 1. 运行中进程探测
    $proc = Get-Process MuMuPlayer, MuMuNxDevice, MuMuVMMSVC -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Path -First 1
    if ($proc) {
        # 从可执行文件向上追溯根目录
        $dir = Split-Path $proc -Parent
        while ($dir -and (Test-Path $dir) -and -not (Test-Path (Join-Path $dir "uninstall.exe")) -and (Split-Path $dir -Parent) -ne $dir) {
            $dir = Split-Path $dir -Parent
        }
        if (Test-Path (Join-Path $dir "uninstall.exe")) {
            $mumuPath = $dir
        }
    }

    # 2. 卸载注册表探测
    if (-not $mumuPath) {
        $uninstKeys = @(
            "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayer-12.0",
            "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayer-12.0",
            "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MuMu Player 12"
        )
        foreach ($k in $uninstKeys) {
            if (Test-Path $k) {
                $loc = (Get-ItemProperty -Path $k -ErrorAction SilentlyContinue).InstallLocation
                if ($loc -and (Test-Path $loc)) {
                    $mumuPath = $loc
                    break
                }
            }
        }
    }

    # 3. MuiCache 记录探测
    if (-not $mumuPath) {
        $muiPath = "HKCU:\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
        if (Test-Path $muiPath) {
            $muiProps = (Get-ItemProperty -Path $muiPath -ErrorAction SilentlyContinue).psobject.Properties
            $mumuMui = $muiProps | Where-Object { $_.Name -like "*MuMuPlayer.exe*" -or $_.Name -like "*MuMuNxDevice.exe*" } | Select-Object -First 1
            if ($mumuMui) {
                $cleanPath = ($mumuMui.Name -split "\.FriendlyAppName|\.ApplicationCompany")[0]
                $dir = Split-Path $cleanPath -Parent
                while ($dir -and (Test-Path $dir) -and -not (Test-Path (Join-Path $dir "uninstall.exe")) -and (Split-Path $dir -Parent) -ne $dir) {
                    $dir = Split-Path $dir -Parent
                }
                if (Test-Path (Join-Path $dir "uninstall.exe")) {
                    $mumuPath = $dir
                }
            }
        }
    }

    # 4. 常见默认路径枚举
    if (-not $mumuPath) {
        $commonPaths = @(
            "C:\Program Files\Netease\MuMuPlayer-12.0",
            "D:\Program Files\Netease\MuMuPlayer-12.0",
            "E:\Program Files\Netease\MuMuPlayer-12.0",
            "C:\ProgramFiles\MuMuPlayer-12.0",
            "D:\ProgramFiles\MuMuPlayer-12.0",
            "E:\ProgramFiles\MuMuPlayer-12.0",
            "E:\Games\Chinese Game\MuMu Player 12"
        )
        foreach ($cp in $commonPaths) {
            if (Test-Path $cp) {
                $mumuPath = $cp
                break
            }
        }
    }

    if (-not $mumuPath) {
        Write-Status "INFO" "未在常见路径与注册表中发现 MuMu 模拟器（若使用其他模拟器可忽略）。"
        return $null
    }

    Write-Status "PASS" ("发现 MuMu 模拟器安装路径: {0}" -f $mumuPath)

    # 3.1 NemuIPC DLL 检查
    $dllCandidatePaths = @(
        (Join-Path $mumuPath "shell\sdk\external_renderer_ipc.dll"),
        (Join-Path $mumuPath "nx_device\12.0\shell\sdk\external_renderer_ipc.dll"),
        (Join-Path $mumuPath "nx_device\15.0\shell\sdk\external_renderer_ipc.dll"),
        (Join-Path $mumuPath "nx_main\sdk\external_renderer_ipc.dll")
    )
    $foundDll = $null
    foreach ($dp in $dllCandidatePaths) {
        if (Test-Path $dp) {
            $foundDll = $dp
            break
        }
    }
    if (-not $foundDll) {
        $searchedDll = Get-ChildItem -Path $mumuPath -Filter "external_renderer_ipc.dll" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($searchedDll) {
            $foundDll = $searchedDll.FullName
        }
    }

    if ($foundDll) {
        Write-Status "PASS" ("NemuIPC 共享内存动态库完整: {0}" -f $foundDll)
    } else {
        Write-Status "FAIL" "未在 MuMu 目录中找到 external_renderer_ipc.dll，NemuIPC 极速截图管道将无法工作。"
    }

    # 3.2 保活配置检查 customer_config.json
    $vmsPath = Join-Path $mumuPath "vms"
    $configFiles = @()
    if (Test-Path $vmsPath) {
        $configFiles += Get-ChildItem -Path $vmsPath -Filter "customer_config.json" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.DirectoryName -match "configs$" -and $_.FullName -notmatch "exportLogs" }
    }

    if ($configFiles.Count -gt 0) {
        $hasFail = $false
        foreach ($cfg in $configFiles) {
            try {
                $content = Get-Content -Path $cfg.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
                $keptLive = $null
                if ($content.customer -and $null -ne $content.customer.app_keptlive) {
                    $keptLive = $content.customer.app_keptlive
                } elseif ($null -ne $content.app_keptlive) {
                    $keptLive = $content.app_keptlive
                }

                $vmName = (Split-Path (Split-Path $cfg.DirectoryName -Parent) -Leaf)
                if ([string]$keptLive -eq "true" -or [string]$keptLive -eq "1") {
                    Write-Status "FAIL" ("虚拟机 [{0}] 开启了后台挂机保活 (customer.app_keptlive = {1})！此机制会破坏 Direct3D 交换链导致 NemuIPC 截图黑屏或回退 ADB。请在 MuMu 设置中心【运行与保活】中关闭【后台挂机保活】。" -f $vmName, $keptLive)
                    $hasFail = $true
                } else {
                    Write-Status "PASS" ("虚拟机 [{0}] 后台保活处于关闭状态 (customer.app_keptlive = {1})。" -f $vmName, $keptLive)
                }
            } catch {
                Write-Status "WARN" ("解析配置文件失败: {0} ({1})" -f $cfg.FullName, $_.Exception.Message)
            }
        }
    } else {
        Write-Status "INFO" "未在 vms 目录中找到 customer_config.json（可能尚未创建虚拟机实例）。"
    }

    return @{
        Path = $mumuPath
        Dll = $foundDll
    }
}

# ---------------------------------------------------------------------------
# 4. 内存与 PageFile 虚拟内存健康度检测 (Check-PageFileAndMemory)
# ---------------------------------------------------------------------------
function Check-PageFileAndMemory {
    Write-Header "4. 物理内存与 PageFile 虚拟内存健康度检测"

    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        $totalPhysGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
        $freePhysGB  = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
        $usedPhysGB  = [math]::Round($totalPhysGB - $freePhysGB, 2)

        $totalVirtGB = [math]::Round($os.TotalVirtualMemorySize / 1MB, 2)
        $freeVirtGB  = [math]::Round($os.FreeVirtualMemory / 1MB, 2)
        $usedVirtGB  = [math]::Round($totalVirtGB - $freeVirtGB, 2)

        Write-Status "INFO" ("物理内存: 已用 {0} GB / 总计 {1} GB (空闲: {2} GB)" -f $usedPhysGB, $totalPhysGB, $freePhysGB)
        Write-Status "INFO" ("虚拟内存: 已用 {0} GB / 总计 {1} GB (空闲: {2} GB)" -f $usedVirtGB, $totalVirtGB, $freeVirtGB)
    }
    catch {
        Write-Status "WARN" "获取内存统计信息失败: $($_.Exception.Message)"
    }

    # 4.1 PageFile 盘符与 SSD 检测
    $pagefiles = Get-CimInstance Win32_PageFileUsage -ErrorAction SilentlyContinue
    if (-not $pagefiles) {
        Write-Status "WARN" "未检测到活跃的分页文件 (PageFile)。若由系统动态管理或完全禁用，内存吃紧时可能引发直接 OOM 崩溃！"
        return
    }

    $allOnSsd = $true
    foreach ($pf in $pagefiles) {
        $filePath = $pf.Name
        $driveLetter = ($filePath -split ":")[0]
        $diskType = "Unknown"

        try {
            $partition = Get-Partition -DriveLetter $driveLetter -ErrorAction SilentlyContinue
            if ($partition) {
                $disk = Get-Disk -Number $partition.DiskNumber -ErrorAction SilentlyContinue
                if ($disk) {
                    $physDisk = Get-PhysicalDisk | Where-Object DeviceId -eq $disk.Number -ErrorAction SilentlyContinue
                    if ($physDisk -and $physDisk.MediaType) {
                        $diskType = $physDisk.MediaType
                    } else {
                        $diskType = $disk.BusType
                    }
                }
            }
        } catch {}

        if ($diskType -eq "HDD") {
            Write-Status "FAIL" ("分页文件位于机械硬盘: {0} (磁盘类型: {1})！老旧平台机械盘置换虚拟内存将引发严重 100% 磁盘 I/O 假死！请务必将其移至 SSD 固态硬盘。" -f $filePath, $diskType)
            $allOnSsd = $false
        } else {
            Write-Status "PASS" ("分页文件正常驻留于固态存储: {0} (磁盘类型: {1}, 当前使用: {2} MB / 峰值: {3} MB)" -f $filePath, $diskType, $pf.CurrentUsage, $pf.PeakUsage)
        }
    }

    if ($allOnSsd) {
        Write-Status "PASS" "所有分页文件均位于高速存储设备上，无机械盘置换颠簸风险。"
    }
}

# ---------------------------------------------------------------------------
# 5. 自愈修复模式执行 (-Fix)
# ---------------------------------------------------------------------------
function Invoke-FixRoutine {
    param(
        $mumuInfo,
        $gpuInfo
    )

    Write-Header "5. 执行自动化修复 (-Fix)"

    if (-not $isAdmin) {
        Write-Status "FAIL" "执行自愈需要管理员权限！请重新以管理员身份运行本脚本。"
        return
    }

    # 5.1 写入 TDR 注册表加固
    $tdrRegPath = "HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
    try {
        if (-not (Test-Path $tdrRegPath)) {
            New-Item -Path $tdrRegPath -Force | Out-Null
        }
        Set-ItemProperty -Path $tdrRegPath -Name "TdrDelay" -Value 8 -Type DWord -Force
        Set-ItemProperty -Path $tdrRegPath -Name "TdrDdiDelay" -Value 8 -Type DWord -Force
        Set-ItemProperty -Path $tdrRegPath -Name "TdrLevel" -Value 3 -Type DWord -Force
        Write-Status "PASS" "成功写入 TDR 注册表加固配置: TdrDelay=8, TdrDdiDelay=8, TdrLevel=3。"
    }
    catch {
        Write-Status "FAIL" "写入 TDR 注册表配置失败: $($_.Exception.Message)"
    }

    # 5.2 写入 UserGpuPreferences
    $gpuRegPath = "HKCU:\Software\Microsoft\DirectX\UserGpuPreferences"
    try {
        if (-not (Test-Path $gpuRegPath)) {
            New-Item -Path $gpuRegPath -Force | Out-Null
        }

        # 写入 MuMuPlayer.exe 为独显 (2)
        if ($mumuInfo -and $mumuInfo.Path) {
            $mumuExes = @(
                (Join-Path $mumuInfo.Path "shell\MuMuPlayer.exe"),
                (Join-Path $mumuInfo.Path "nx_device\12.0\shell\MuMuNxDevice.exe"),
                (Join-Path $mumuInfo.Path "nx_device\15.0\shell\MuMuNxDevice.exe")
            )
            foreach ($exe in $mumuExes) {
                if (Test-Path $exe) {
                    Set-ItemProperty -Path $gpuRegPath -Name $exe -Value "GpuPreference=2;" -Force
                    Write-Status "PASS" ("成功将 {0} 绑定至高性能独显 (GpuPreference=2;)" -f (Split-Path $exe -Leaf))
                }
            }
        }

        # 写入 Thorium 为核显 (1)
        $thoriumPath = Join-Path $env:LOCALAPPDATA "Thorium\Application\thorium.exe"
        if (Test-Path $thoriumPath) {
            Set-ItemProperty -Path $gpuRegPath -Name $thoriumPath -Value "GpuPreference=1;" -Force
            Write-Status "PASS" "成功将 Thorium 浏览器绑定至节能核显 (GpuPreference=1;)"
        }

        # 写入 AzurLaneAutoScript 为核显 (1)
        $alasRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
        $alasExe = Join-Path $alasRoot "AzurLaneAutoScript.exe"
        if (Test-Path $alasExe) {
            Set-ItemProperty -Path $gpuRegPath -Name $alasExe -Value "GpuPreference=1;" -Force
            Write-Status "PASS" "成功将 Alas 桌面端绑定至节能核显 (GpuPreference=1;)"
        }
    }
    catch {
        Write-Status "WARN" "设置 Windows 图形首选项注册表时发生警告: $($_.Exception.Message)"
    }

    Write-Host ""
    Write-Host "  [!] 提示: TDR 注册表修改已就绪，请在方便时重启计算机以使驱动层完全生效。" -ForegroundColor Cyan
}

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "========================================================================" -ForegroundColor Magenta
Write-Host "       Alas 弱机与模拟器环境自动化体检看板 (AzurLaneAutoScript)           " -ForegroundColor Magenta
Write-Host "========================================================================" -ForegroundColor Magenta

$gpuInfo  = Check-GpuTopology
$tdrPass  = Check-TdrDelay
$mumuInfo = Check-MuMuConfig
Check-PageFileAndMemory

if ($Fix) {
    Invoke-FixRoutine -mumuInfo $mumuInfo -gpuInfo $gpuInfo
}

Write-Header "体检总结与调优指引"
Write-Host "  - 详细弱机硬分流与 7x24h 协同调优指南: doc/low_spec_tuning_guide.md" -ForegroundColor Cyan
Write-Host "  - 注册表独立导入文件目录: deploy/optimize/enable_tdr_delay_8s.reg" -ForegroundColor Cyan
if (-not $Fix) {
    Write-Host "  - 若检测到 TDR 延迟不足或首选项未绑定，可以管理员身份运行:" -ForegroundColor Yellow
    Write-Host "      pwsh -File deploy/optimize/check_env.ps1 -Fix" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "体检完成。" -ForegroundColor Green
