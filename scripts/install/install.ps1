# Claude Forge — Unified Installer (Windows PowerShell)
#
# Interactive installer that handles every scenario from one entry point:
#   Fresh install / Full reinstall / Refresh framework / Refresh v3.
#
# Usage:
#   .\scripts\install\install.ps1                                    # interactive
#   .\scripts\install\install.ps1 -ProjectPath C:\src\myapp          # interactive, preset path
#   .\scripts\install\install.ps1 -Mode refresh-v3 -Yes -ProjectPath C:\src\myapp
#
# -Mode options: full | refresh | refresh-v3
# -Yes auto-confirms the "Proceed?" prompt.
# -Backup forces backup ON (default for refresh modes).
# -NoBackup skips the pre-refresh snapshot (faster, irreversible).
#
# Backup behavior: refresh / refresh-v3 modes back up the existing .claude\
# to backups\<timestamp>\ before overwriting. Default ON; interactive runs
# prompt for the choice when an existing .claude\ is found.
#
# refresh-v3: additive Forge Flow v3 upgrade — drops in v3 framework surfaces,
# removes legacy .claude/cross-repo/ (backed up), preserves all user content,
# then runs verify.sh --fix (or skips with a notice if bash is unavailable).

param(
    [string]$ProjectPath = "",
    [string]$Mode = "",
    [switch]$Yes,
    [switch]$Backup,
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"

$ScriptDir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrameworkDir   = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$BackupStamp    = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupsCreated = 0
$script:BackupEnabled = $true   # default ON; toggled by Backup/NoBackup switches

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Color { param([string]$Text, [string]$Color = "White"); Write-Host $Text -ForegroundColor $Color }
function Say-Ok      { param([string]$m) Write-Color "OK   $m" Green }
function Say-Warn    { param([string]$m) Write-Color "WARN $m" Yellow }
function Say-Fail    { param([string]$m) Write-Color "FAIL $m" Red }
function Say-Step    { param([string]$m) Write-Color "->   $m" Blue }

# --- Visual progress helpers ---
$script:PhasesTotal     = 0
$script:PhasesDone      = 0
$script:InstallStartTime = Get-Date

function Set-Phases { param([int]$Total) $script:PhasesTotal = $Total; $script:PhasesDone = 0 }

function Write-Banner {
    Write-Color "" Cyan
    Write-Color "=================================================================" Cyan
    Write-Color "              Claude Forge - Unified Installer                   " Cyan
    Write-Color "=================================================================" Cyan
    Write-Color "" Cyan
}

function Write-Section { param([string]$t)
    $script:PhasesDone++
    Write-Host ""
    Write-Color "-----------------------------------------------------------------" Cyan
    if ($script:PhasesTotal -gt 0) {
        Write-Color ("[{0}/{1}] {2}" -f $script:PhasesDone, $script:PhasesTotal, $t) Cyan
        # Also drive the built-in PowerShell progress bar
        $pct = [int](($script:PhasesDone / $script:PhasesTotal) * 100)
        Write-Progress -Activity "Claude Forge install" -Status $t -PercentComplete $pct
    } else {
        Write-Color $t Cyan
    }
    Write-Color "-----------------------------------------------------------------" Cyan
}

# Run a script block and show a "spinning" status in the progress bar.
# Falls back to plain invocation if Write-Progress is unavailable.
function Invoke-WithSpinner {
    param([string]$Label, [scriptblock]$Action)
    $start = Get-Date
    Write-Color ("  -> {0}" -f $Label) Blue
    try {
        Write-Progress -Activity "Claude Forge install" -Status $Label -PercentComplete -1 -CurrentOperation "running..."
    } catch { }
    & $Action
    $rc = $LASTEXITCODE
    $elapsed = [int]((Get-Date) - $start).TotalSeconds
    if ($rc -eq 0 -or $null -eq $rc) {
        Write-Color ("  OK {0} ({1}s)" -f $Label, $elapsed) Green
    } else {
        Write-Color ("  FAIL {0} ({1}s, exit {2})" -f $Label, $elapsed, $rc) Red
    }
}

function Get-BackupRoot { Join-Path $script:PROJECT_DIR ".claude\backups\$BackupStamp" }

# Directory names excluded from snapshot copies: the backups/ tree itself
# (avoids embedding every prior snapshot plus racing this in-progress copy)
# and other heavyweight machine-local dirs that don't belong in a portable
# snapshot.
$script:BackupExcludeDirs = @(
    'backups', 'worktrees',
    '.venv', '__pycache__', '.pytest_cache', 'venv',
    'node_modules', '.DS_Store'
)

function Backup-File {
    param([string]$SourcePath)
    if (-not (Test-Path $SourcePath)) { return }
    if (-not $script:BackupEnabled) { return }
    $root = Get-BackupRoot
    if (-not (Test-Path $root)) { New-Item -Path $root -ItemType Directory -Force | Out-Null }
    $rel  = $SourcePath.Replace($script:PROJECT_DIR, "").TrimStart("\", "/")
    $dest = Join-Path $root $rel

    if (Test-Path $SourcePath -PathType Container) {
        # Per-file recursive copy with computed destination paths, same
        # exclude-prefix pattern used by the refresh-v3 framework copy above.
        # Avoids PowerShell Copy-Item -Recurse's nested-dir bug and lets us
        # skip excluded directories entirely instead of copying then pruning.
        Get-ChildItem -Path $SourcePath -Recurse -File -Force | ForEach-Object {
            $itemRel = $_.FullName.Substring($SourcePath.Length).TrimStart('\', '/')
            foreach ($excl in $script:BackupExcludeDirs) {
                if ($itemRel -eq $excl -or $itemRel -like "$excl\*" -or $itemRel -like "$excl/*" -or
                    $itemRel -like "*\$excl\*" -or $itemRel -like "*/$excl/*") { return }
            }
            $itemDest = Join-Path $dest $itemRel
            $itemDestParent = Split-Path -Parent $itemDest
            if (-not (Test-Path $itemDestParent)) { New-Item -Path $itemDestParent -ItemType Directory -Force | Out-Null }
            Copy-Item -Path $_.FullName -Destination $itemDest -Force
        }
    } else {
        $destParent = Split-Path -Parent $dest
        if (-not (Test-Path $destParent)) { New-Item -Path $destParent -ItemType Directory -Force | Out-Null }
        Copy-Item -Path $SourcePath -Destination $dest -Force
    }
    $script:BackupsCreated++
    Remove-OldBackups
}

# Keep only the 5 newest timestamped snapshot dirs directly under
# .claude\backups\ (lexicographic sort == chronological for the
# yyyyMMdd-HHmmss pattern). 5 is a deliberate hardcode for the solo-dev
# default; make it a flag only if someone actually asks for more history.
function Remove-OldBackups {
    $backupsRoot = Join-Path $script:PROJECT_DIR ".claude\backups"
    if (-not (Test-Path $backupsRoot)) { return }
    $entries = @(Get-ChildItem -Path $backupsRoot -Directory -Force | Where-Object {
        $_.Name -match '^\d{8}-\d{6}$'
    } | Sort-Object Name)
    $count = $entries.Count
    if ($count -le 5) { return }
    $toRemove = @($entries | Select-Object -First ($count - 5))
    foreach ($dir in $toRemove) {
        Remove-Item -Path $dir.FullName -Recurse -Force
    }
    Say-Ok "Pruned $($toRemove.Count) old backup snapshot(s) (keep-last-5)"
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

function Invoke-Preflight {
    Write-Section "Preflight"
    $failed = $false

    $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
    if (-not $pythonCmd) { $pythonCmd = Get-Command python -ErrorAction SilentlyContinue }
    if ($pythonCmd) {
        $ver  = & $pythonCmd.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        $okPy = & $pythonCmd.Source -c "import sys; print(1 if sys.version_info >= (3, 10) else 0)"
        if ($okPy -eq "1") { Say-Ok "python $ver (>=3.10 required)" }
        else               { Say-Fail "python $ver found, but 3.10+ is required"; $failed = $true }
    } else {
        Say-Fail "python3 not found on PATH — memory pipeline will not run"
        $failed = $true
    }
    $script:PYTHON = $pythonCmd

    $claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
    if ($claudeCmd) { Say-Ok "claude CLI found ($($claudeCmd.Source))" }
    else {
        Say-Warn "claude CLI not found on PATH — memory flush/compile will fail until installed"
        Write-Host "   Install: https://docs.anthropic.com/en/docs/claude-code"
    }

    if (Get-Command git -ErrorAction SilentlyContinue) { Say-Ok "git available" }
    else { Say-Warn "git not found — some features will be unavailable" }

    if ($failed) {
        Write-Host ""
        Say-Warn "Preflight failed."
        $cont = Read-Host "Continue anyway? [y/N]"
        if ($cont -notmatch '^[Yy]$') { exit 1 }
    }
}

# ---------------------------------------------------------------------------
# Target selection and state detection
# ---------------------------------------------------------------------------

function Select-ProjectDir {
    param([string]$Preset)
    Write-Section "Target project"

    if ($Preset) { $script:PROJECT_DIR = $Preset }
    else {
        Write-Host "Enter the absolute path to your project directory."
        $script:PROJECT_DIR = Read-Host "> "
    }

    if (-not (Test-Path $script:PROJECT_DIR -PathType Container)) {
        Say-Fail "Directory does not exist: $script:PROJECT_DIR"
        exit 1
    }
    $script:PROJECT_DIR = (Resolve-Path $script:PROJECT_DIR).Path

    if ($script:PROJECT_DIR -eq $FrameworkDir) {
        Say-Fail "Refusing to install into the framework repo itself."
        exit 1
    }

    Say-Ok "Project directory: $script:PROJECT_DIR"
}

function Invoke-DetectState {
    $script:HAS_CLAUDE          = [int](Test-Path (Join-Path $script:PROJECT_DIR ".claude") -PathType Container)
    $script:HAS_PROJECT_MEMORY  = [int](Test-Path (Join-Path $script:PROJECT_DIR "docs\project-memory") -PathType Container)
    $script:HAS_SETTINGS        = [int](Test-Path (Join-Path $script:PROJECT_DIR ".claude\settings.json"))
    $script:HAS_LEGACY_SETTINGS = [int](Test-Path (Join-Path $script:PROJECT_DIR "hooks\settings.json"))

    Write-Section "Detected state"
    if ($script:HAS_CLAUDE)         { Say-Ok ".claude/ present" } else { Say-Warn ".claude/ absent" }
    if ($script:HAS_PROJECT_MEMORY) { Say-Ok "docs/project-memory/ present" } else { Say-Warn "docs/project-memory/ absent" }
    if ($script:HAS_SETTINGS)       { Say-Ok ".claude/settings.json present" } else { Say-Warn ".claude/settings.json absent (hooks won't fire)" }
    if ($script:HAS_LEGACY_SETTINGS){ Say-Warn "Legacy hooks/settings.json at project root (Claude Code does NOT read this)" }
}

# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------

function Select-Mode {
    if ($script:PRESET_MODE) {
        $normalized = switch -Regex ($script:PRESET_MODE.ToLower()) {
            '^full$'                              { "full"; break }
            '^(refresh|refresh-framework)$'       { "refresh-framework"; break }
            '^(refresh-v3|v3-upgrade)$'           { "refresh-v3"; break }
            default {
                Say-Fail "Unknown -Mode value: $($script:PRESET_MODE) (expected: full, refresh, refresh-v3)"
                exit 1
            }
        }
        $script:INSTALL_MODE = $normalized
        Write-Section "Installation mode"
        Say-Ok "Selected mode: $script:INSTALL_MODE (from -Mode)"
        return
    }

    Write-Section "Installation mode"

    Write-Host "Based on the detected state, choose an action:"
    Write-Host ""
    if ($script:HAS_CLAUDE -eq 0) {
        Write-Host "  1) Fresh install                — new project, no existing .claude/"
    } else {
        Write-Host "  1) Full reinstall               — back up .claude/ to .claude_old/ and overwrite"
    }
    Write-Host "  2) Refresh framework files      — update .claude/ in-place (also removes framework-retired files; backed up first)"
    Write-Host "  3) Quit"
    Write-Host ""
    Write-Host "  (Forge Flow v3 upgrade: re-run with -Mode refresh-v3)"
    Write-Host ""

    $default = if ($script:HAS_CLAUDE -eq 0) { "1" } else { "2" }
    $choice = Read-Host "Select [1-3] (default: $default)"
    if (-not $choice) { $choice = $default }

    switch ($choice) {
        "1" { $script:INSTALL_MODE = "full" }
        "2" { $script:INSTALL_MODE = "refresh-framework" }
        "3" { Write-Host "Cancelled."; exit 0 }
        default { Say-Fail "Invalid choice"; exit 1 }
    }
    Say-Ok "Selected mode: $script:INSTALL_MODE"
}

# ---------------------------------------------------------------------------
# Install step functions
# ---------------------------------------------------------------------------

function Install-FrameworkFresh {
    Say-Step "Installing framework into .claude/ (fresh)"
    $target = Join-Path $script:PROJECT_DIR ".claude"
    New-Item -Path $target -ItemType Directory -Force | Out-Null

    # Top-level excludes (entire tree): .git, .github, daily/, docs/project-memory/,
    # plus caches/artifacts that must never land in a consumer's .claude/.
    # scripts/ is descended into so we can skip install/
    $topLevelExcludes = @(
        ".git", ".github", "daily",
        ".venv", ".pytest_cache", "__pycache__", "_archive",
        ".DS_Store", ".remember", ".forge", ".superpowers", ".vscode"
    )
    Get-ChildItem -Path $FrameworkDir -Force | Where-Object {
        $_.Name -notin $topLevelExcludes
    } | ForEach-Object {
        $destItem = Join-Path $target $_.Name
        if ($_.PSIsContainer -and $_.Name -eq "scripts") {
            # Copy scripts/ but skip scripts/install
            New-Item -Path $destItem -ItemType Directory -Force | Out-Null
            Get-ChildItem -Path $_.FullName -Force | Where-Object {
                $_.Name -notin @("install")
            } | ForEach-Object {
                Copy-Item -Path $_.FullName -Destination (Join-Path $destItem $_.Name) -Recurse -Force
            }
        } elseif ($_.PSIsContainer -and $_.Name -eq "docs") {
            # Copy docs/ but skip docs/project-memory (project root)
            New-Item -Path $destItem -ItemType Directory -Force | Out-Null
            Get-ChildItem -Path $_.FullName -Force | Where-Object {
                $_.Name -ne "project-memory"
            } | ForEach-Object {
                Copy-Item -Path $_.FullName -Destination (Join-Path $destItem $_.Name) -Recurse -Force
            }
        } else {
            Copy-Item -Path $_.FullName -Destination $destItem -Recurse -Force
        }
    }

    # Clean up stray dirs from prior installs that put daily/ under .claude/
    Remove-Item -Path (Join-Path $target "daily") -Recurse -Force -ErrorAction SilentlyContinue

    Install-CutPathsManifest
    Say-Ok "Framework copied to .claude/"
}

function Install-CutPathsManifest {
    # scripts/install/ is skipped above (the installer never ships itself),
    # but forge doctor's orphans check needs the retired-paths ledger to do
    # its job on consumer installs. Ship just this one file.
    $src = Join-Path $FrameworkDir "scripts\install\cut-paths.txt"
    $dst = Join-Path $script:PROJECT_DIR ".claude\scripts\install\cut-paths.txt"
    if (-not (Test-Path $src)) { return }
    $dstDir = Split-Path -Parent $dst
    if (-not (Test-Path $dstDir)) { New-Item -Path $dstDir -ItemType Directory -Force | Out-Null }
    Copy-Item -Path $src -Destination $dst -Force
    Say-Ok "Installed cut-paths.txt manifest (enables doctor's orphans check)"
}

function Install-FrameworkOverwrite {
    Say-Step "Backing up existing .claude/ -> .claude_old/"
    $oldDir = Join-Path $script:PROJECT_DIR ".claude_old"
    if (Test-Path $oldDir) {
        Say-Warn ".claude_old/ already exists."
        $ow = Read-Host "Overwrite existing backup? [y/N]"
        if ($ow -match '^[Yy]$') { Remove-Item -Path $oldDir -Recurse -Force }
        else { Say-Fail "Cannot proceed — backup directory in the way."; exit 1 }
    }
    Move-Item -Path (Join-Path $script:PROJECT_DIR ".claude") -Destination $oldDir
    Say-Ok "Backed up to $oldDir"

    Install-FrameworkFresh
    New-RestorationScript
}

function Install-FrameworkRefresh {
    Say-Step "Refreshing framework files in .claude/ (preserving user content)"
    $target = Join-Path $script:PROJECT_DIR ".claude"
    if (Test-Path $target) {
        if ($script:BackupEnabled) {
            Invoke-WithSpinner "Snapshotting current .claude/ to backups/" { Backup-File $target }
        } else {
            Say-Warn "Skipping snapshot (-NoBackup) — refresh is not reversible in place"
        }
    }
    New-Item -Path $target -ItemType Directory -Force | Out-Null

    # Preserve: active sessions, progress notes, settings.json, backups, daily/
    $preserve = @(
        "memories\sessions\active",
        "memories\sessions\completed",
        "memories\progress-notes.md",
        "settings.json",
        "settings.local.json",
        "backups"
    )

    $topLevelExcludes = @(
        ".git", ".github", "daily",
        ".venv", ".pytest_cache", "__pycache__", "_archive",
        ".DS_Store", ".remember", ".forge", ".superpowers", ".vscode"
    )
    Get-ChildItem -Path $FrameworkDir -Force | Where-Object {
        $_.Name -notin $topLevelExcludes
    } | ForEach-Object {
        $relName = $_.Name
        $destItem = Join-Path $target $relName
        if ($_.PSIsContainer -and $relName -eq "scripts") {
            New-Item -Path $destItem -ItemType Directory -Force | Out-Null
            Get-ChildItem -Path $_.FullName -Force | Where-Object {
                $_.Name -notin @("install")
            } | ForEach-Object {
                Copy-Item -Path $_.FullName -Destination (Join-Path $destItem $_.Name) -Recurse -Force
            }
        } elseif ($_.PSIsContainer -and $relName -eq "docs") {
            New-Item -Path $destItem -ItemType Directory -Force | Out-Null
            Get-ChildItem -Path $_.FullName -Force | Where-Object { $_.Name -ne "project-memory" } | ForEach-Object {
                Copy-Item -Path $_.FullName -Destination (Join-Path $destItem $_.Name) -Recurse -Force
            }
        } elseif ($_.PSIsContainer -and $relName -eq "memories") {
            # Copy memories, but skip session files and progress-notes.md
            New-Item -Path $destItem -ItemType Directory -Force | Out-Null
            Get-ChildItem -Path $_.FullName -Force -Recurse | ForEach-Object {
                $srcFull = $_.FullName
                $relSub = $srcFull.Substring($FrameworkDir.Length).TrimStart("\", "/")
                $skipIt = $false
                foreach ($p in $preserve) { if ($relSub -like "$p*") { $skipIt = $true; break } }
                if (-not $skipIt) {
                    $destFull = Join-Path $target $relSub
                    $destParent = Split-Path -Parent $destFull
                    if (-not (Test-Path $destParent)) { New-Item -Path $destParent -ItemType Directory -Force | Out-Null }
                    if (-not $_.PSIsContainer) { Copy-Item -Path $srcFull -Destination $destFull -Force }
                }
            }
        } else {
            Copy-Item -Path $_.FullName -Destination $destItem -Recurse -Force
        }
    }
    # Clean up stray dirs from prior installs
    Remove-Item -Path (Join-Path $target "daily") -Recurse -Force -ErrorAction SilentlyContinue
    Install-CutPathsManifest
    Say-Ok "Framework files refreshed (settings.json preserved — merge step runs next)"
}

function New-RestorationScript {
    $path = Join-Path $script:PROJECT_DIR ".claude_restore.ps1"
    $content = @'
# Claude Forge Restoration Script
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$old  = Join-Path $here ".claude_old"
$cur  = Join-Path $here ".claude"
if (-not (Test-Path $old)) { Write-Host "No .claude_old/ backup found."; exit 1 }
$r = Read-Host "Delete $cur and restore $old ? [y/N]"
if ($r -notmatch '^[Yy]$') { Write-Host "Cancelled."; exit 0 }
if (Test-Path $cur) { Remove-Item -Path $cur -Recurse -Force }
Move-Item -Path $old -Destination $cur
Remove-Item -Path (Join-Path $here ".claude_restore.ps1")
Write-Host "Restoration complete."
'@
    Set-Content -Path $path -Value $content
    Say-Ok "Created restoration script: .claude_restore.ps1"
}

function Install-SessionDirs {
    Say-Step "Initializing session directories"
    $active    = Join-Path $script:PROJECT_DIR ".claude\memories\sessions\active"
    $completed = Join-Path $script:PROJECT_DIR ".claude\memories\sessions\completed"
    New-Item -Path $active    -ItemType Directory -Force | Out-Null
    New-Item -Path $completed -ItemType Directory -Force | Out-Null
    New-Item -Path (Join-Path $active    ".gitkeep") -ItemType File -Force | Out-Null
    New-Item -Path (Join-Path $completed ".gitkeep") -ItemType File -Force | Out-Null
    Say-Ok "Session directories ready"
}

function Install-ProjectMemory {
    Say-Step "Installing docs/project-memory/"
    $target = Join-Path $script:PROJECT_DIR "docs\project-memory"
    $src    = Join-Path $FrameworkDir "templates\project-memory"

    if (Test-Path $target) {
        Say-Warn "docs/project-memory/ already exists"
        $ow = Read-Host "Overwrite template files? [y/N]"
        if ($ow -notmatch '^[Yy]$') { Say-Ok "Keeping existing project memory files"; return }
        Backup-File $target
    }

    New-Item -Path $target -ItemType Directory -Force | Out-Null
    if (Test-Path $src -PathType Container) {
        foreach ($f in @("bugs.md","decisions.md","key-facts.md","patterns.md")) {
            $s = Join-Path $src $f
            if (Test-Path $s) { Copy-Item -Path $s -Destination (Join-Path $target $f) -Force }
        }
        Say-Ok "Installed template files to docs/project-memory/"
    } else {
        Say-Warn "Template dir missing — created empty docs/project-memory/"
    }

    $resetDir = Join-Path $script:PROJECT_DIR ".claude\templates\project-memory"
    if (Test-Path $src -PathType Container) {
        if (-not (Test-Path $resetDir)) { New-Item -Path $resetDir -ItemType Directory -Force | Out-Null }
        Copy-Item -Path (Join-Path $src "*") -Destination $resetDir -Recurse -Force
    }

    $indexPath = Join-Path $target "index.md"
    if (-not (Test-Path $indexPath)) {
        $indexContent = @"
# Project Memory Index

> Auto-generated catalog of all project knowledge.
> This file is injected at session start for instant context.

## Summary

| Category | Count | Last Updated |
|----------|-------|--------------|
| Bugs | 0 | - |
| Decisions | 0 | - |
| Patterns | 0 | - |
| Key Facts | 0 | - |

## Recent Entries

_No entries yet._
"@
        Set-Content -Path $indexPath -Value $indexContent
        Say-Ok "Created docs/project-memory/index.md"
    }
}

function Install-Settings {
    Say-Step "Wiring .claude/settings.json (the only location Claude Code reads)"
    $fw = Join-Path $FrameworkDir "hooks\settings.json"
    $pr = Join-Path $script:PROJECT_DIR ".claude\settings.json"
    if (-not (Test-Path $fw)) { Say-Warn "Framework hook template missing: $fw"; return }

    $claudeDir = Join-Path $script:PROJECT_DIR ".claude"
    if (-not (Test-Path $claudeDir)) { New-Item -Path $claudeDir -ItemType Directory -Force | Out-Null }

    if (Test-Path $pr) {
        if (-not $script:PYTHON) {
            Say-Warn "python unavailable — skipped settings.json merge"
            return
        }
        Backup-File $pr
        $merge = @'
import json, sys
from pathlib import Path
framework = json.loads(Path(sys.argv[1]).read_text())
project = json.loads(Path(sys.argv[2]).read_text())
fw_hooks = framework.get("hooks", {})
pr_hooks = project.setdefault("hooks", {})
for event, entries in fw_hooks.items():
    pr_hooks[event] = entries
fw_perms = framework.get("permissions", {}).get("allow", [])
pr_perms = project.setdefault("permissions", {}).setdefault("allow", [])
for p in fw_perms:
    if p not in pr_perms:
        pr_perms.append(p)
Path(sys.argv[2]).write_text(json.dumps(project, indent=2) + "\n")
'@
        $merge | & $script:PYTHON.Source - $fw $pr
        Say-Ok "Merged hooks & permissions into .claude/settings.json"
    } else {
        Copy-Item -Path $fw -Destination $pr -Force
        Say-Ok "Installed .claude/settings.json"
    }

    if ($script:HAS_LEGACY_SETTINGS) {
        Say-Warn "Found $(Join-Path $script:PROJECT_DIR 'hooks\settings.json') — Claude Code does NOT read this location."
        Write-Host "   Its hooks are merged into .claude/settings.json. You may delete the legacy file."
    }
}

function Install-Schema {
    $src = Join-Path $FrameworkDir "MEMORY-SCHEMA.md"
    $dst = Join-Path $script:PROJECT_DIR "MEMORY-SCHEMA.md"
    if (-not (Test-Path $src)) { return }
    if (Test-Path $dst) { Say-Ok "MEMORY-SCHEMA.md already present (kept)"; return }
    Copy-Item -Path $src -Destination $dst -Force
    Say-Ok "Installed MEMORY-SCHEMA.md"
}

function Install-Daily {
    $dir = Join-Path $script:PROJECT_DIR "daily"
    if (-not (Test-Path $dir)) { New-Item -Path $dir -ItemType Directory -Force | Out-Null }
    $gi = Join-Path $dir ".gitignore"
    if (-not (Test-Path $gi)) {
        Set-Content -Path $gi -Value "# Daily conversation logs - per-user, not committed`n*`n!.gitignore"
    }
    Say-Ok "daily/ directory ready (gitignored)"
}

function Clear-StrayDirs {
    # Delete legacy copies of daily/ that landed under .claude/ from older
    # full/refresh installs. Runtime always reads these from the project root.
    $stray = @(
        (Join-Path $script:PROJECT_DIR ".claude\daily"),
        (Join-Path $script:PROJECT_DIR ".claude\docs\project-memory")
    )
    $found = $false
    foreach ($d in $stray) {
        if (Test-Path $d) {
            Backup-File $d
            Remove-Item -Path $d -Recurse -Force -ErrorAction SilentlyContinue
            $found = $true
        }
    }
    if ($found) { Say-Ok "Removed legacy copies under .claude/ (runtime uses project root)" }
}

function Update-GitIgnore {
    $gi = Join-Path $script:PROJECT_DIR ".gitignore"
    if (-not (Test-Path $gi)) { return }
    $content = Get-Content $gi -Raw
    if ($content -notmatch "(?m)^daily/") {
        Add-Content -Path $gi -Value "`n# Per-user generated data`ndaily/`n.claude/tmp/"
        Say-Ok "Updated project .gitignore with daily/ entries"
        $content = Get-Content $gi -Raw
    }
    # Registry mutation lock sidecar — machine-local, never committed.
    # See registry_ops.registry_write_lock docstring: intentionally never deleted.
    if ($content -notmatch "(?m)^docs/tasks/\.registry\.lock") {
        Add-Content -Path $gi -Value "`n# Forge Flow registry lock sidecar — machine-local, never committed`ndocs/tasks/.registry.lock"
        Say-Ok "Updated project .gitignore with docs/tasks/.registry.lock entry"
    }
}

# The project-context skeleton written below the framework import when the
# project slot is empty. Carries only what the model cannot infer from code;
# points to reference/01-system-overview.md as the source-of-truth (no dup).
function Get-ProjectSkeleton {
    return @'
<!-- forge-flow:project-context -->
## Project context

> Fill in the sections below. Document only what Claude **cannot infer from the
> code** — intent, gotchas, version quirks, hard rules. Everything obvious from
> reading the source is wasted tokens. The full intent & architecture live in
> `.claude/reference/01-system-overview.md` (Tier-2 source-of-truth) — keep this
> a <=3-line pitch plus pointers, not a duplicate.

### Identity
<!-- One line: what is this project, in plain terms. -->

### Why it exists
<!-- 2-3 lines: the problem it solves / the value it delivers. Not visible in code. -->

### Architecture (deviations only)
<!-- Only the parts that DEPART from convention. Skip anything a reader infers from structure. -->

### Version quirks & pins
<!-- "This library version behaves this way / is real, don't reinvent it." Tribal knowledge. -->

### Global invariants & anti-patterns
<!-- Verifiable hard rules: "never bypass X", "all auth errors route through Y", "parameterize all SQL". -->

### See also
<!-- - Full intent & architecture: .claude/reference/01-system-overview.md -->
'@
}

# Should we inject the skeleton? Already-handled (return $false) when either the
# project-context sentinel is present (we scaffolded it once — never touch again,
# the idempotency + clobber guard) or the user hand-wrote project content. Only a
# sentinel-free, substantively-empty slot returns $true.
function Test-RootClaudeMdSlotEmpty {
    param([string]$RootMd)
    $raw = Get-Content -Path $RootMd -Raw
    if ($raw -like '*<!-- forge-flow:project-context -->*') { return $false }
    $importLine = '@.claude/CLAUDE.md'
    $lines = Get-Content -Path $RootMd
    $seen = $false
    $remainder = @()
    foreach ($line in $lines) {
        if ($seen) {
            if ($line -match '<!-- forge-flow:framework-import -->') { continue }
            if ($line -match '^>\s') { continue }
            if ($line -match '<!--') { continue }
            if ($line -match '^\s*$') { continue }
            if ($line -match '^#') { continue }
            $remainder += $line
        }
        if ($line -like "*$importLine*") { $seen = $true }
    }
    return ($remainder.Count -eq 0)
}

# Inject the project-context skeleton iff the project slot is empty. Idempotent:
# once the user fills any section, this is a no-op on every future refresh.
function Set-RootClaudeMdProjectSlot {
    param([string]$RootMd)
    if (Test-RootClaudeMdSlotEmpty -RootMd $RootMd) {
        $skeleton = Get-ProjectSkeleton
        Add-Content -Path $RootMd -Value ($skeleton + "`n")
        Say-Ok "Scaffolded project-context skeleton in $RootMd"
        Say-Warn "ACTION NEEDED: $RootMd has an empty project section."
        Write-Host "   Fill the 'Project context' headers (or run /refresh-project-context to draft them)."
        Write-Host "   Claude starts every session here - without it, the project is invisible to the model."
    } else {
        Say-Ok "Root CLAUDE.md project section already populated (left untouched)"
    }
}

function Install-RootClaudeMdImport {
    # Ensure the project root has a CLAUDE.md that imports the framework's
    # rules via @.claude/CLAUDE.md. Claude Code reliably auto-loads root
    # CLAUDE.md; auto-discovery of .claude/CLAUDE.md is version-dependent and
    # has been observed to skip silently in consumer projects. The @-import
    # makes the framework wiring explicit and version-independent.
    #
    # Independently of which case wires the import, we then ensure the PROJECT
    # SLOT is populated: empty slot (fresh, or import-only project) gets
    # the project-context skeleton so the root file is never blank on the project.
    Say-Step "Wiring root CLAUDE.md -> @.claude/CLAUDE.md"
    $rootMd = Join-Path $script:PROJECT_DIR "CLAUDE.md"
    $importLine = '@.claude/CLAUDE.md'
    $managedMarker = '<!-- forge-flow:framework-import -->'
    $projectName = Split-Path -Leaf $script:PROJECT_DIR

    if (-not (Test-Path $rootMd)) {
        $newContent = @"
# $projectName

$managedMarker
$importLine
$managedMarker

"@
        Set-Content -Path $rootMd -Value $newContent -NoNewline
        Say-Ok "Created $rootMd with framework import"
        Set-RootClaudeMdProjectSlot -RootMd $rootMd
        return
    }

    $existing = Get-Content -Path $rootMd -Raw
    if ($existing -like "*$importLine*") {
        Say-Ok "Root CLAUDE.md already imports framework (idempotent no-op)"
        Set-RootClaudeMdProjectSlot -RootMd $rootMd
        return
    }

    if ($Yes) {
        $addImport = $true
    } else {
        Say-Warn "Existing $rootMd does not import .claude/CLAUDE.md"
        Write-Host "   Framework rules will not load reliably without this import."
        $addChoice = Read-Host "Prepend '$importLine' to existing root CLAUDE.md? [Y/n]"
        if ($addChoice -match '^[Nn]$') { $addImport = $false } else { $addImport = $true }
    }

    if ($addImport) {
        $prepend = "$managedMarker`n$importLine`n$managedMarker`n`n"
        Set-Content -Path $rootMd -Value ($prepend + $existing) -NoNewline
        Say-Ok "Prepended framework import to existing $rootMd"
        Set-RootClaudeMdProjectSlot -RootMd $rootMd
    } else {
        Say-Warn "Skipped - framework rules may not auto-load. Add manually:"
        Write-Host "   $importLine"
    }
}

# ---------------------------------------------------------------------------
# v3-specific install steps (Forge Flow refresh-v3 upgrade)
# ---------------------------------------------------------------------------

function Install-V3CrossRepoCleanup {
    $crossRepoDir   = Join-Path $script:PROJECT_DIR ".claude\cross-repo"
    $legacyScript   = Join-Path $script:PROJECT_DIR ".claude\scripts\install\add-cross-repo.sh"
    $legacyScriptPs = Join-Path $script:PROJECT_DIR ".claude\scripts\install\add-cross-repo.ps1"

    if (-not (Test-Path $crossRepoDir) -and -not (Test-Path $legacyScript) -and -not (Test-Path $legacyScriptPs)) {
        Say-Ok "No legacy .claude/cross-repo/ — skipping cleanup"
        return
    }

    Say-Step "Removing legacy .claude/cross-repo/ (replaced by Specialist Export Artifact pattern)"

    $backupRoot = Join-Path (Get-BackupRoot) "cross-repo"
    $notesFile  = Join-Path $script:PROJECT_DIR ".claude\v3-migration-notes.md"

    if (Test-Path $crossRepoDir) {
        $parent = Split-Path -Parent $backupRoot
        if (-not (Test-Path $parent)) { New-Item -Path $parent -ItemType Directory -Force | Out-Null }
        Copy-Item -Path $crossRepoDir -Destination $backupRoot -Recurse -Force
        $script:BackupsCreated++
        Say-Ok "Backed up $crossRepoDir -> $backupRoot"
    }

    $now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $entries = if (Test-Path $backupRoot) {
        (Get-ChildItem -Path $backupRoot -Recurse -Depth 1 | ForEach-Object { $_.FullName.Replace($backupRoot, "").TrimStart("\","/") }) -join "`n"
    } else { "(no entries — only legacy script(s) found)" }

    $notes = @"
# v3 Migration Notes — Cross-repo Cleanup

> Auto-generated by install.ps1 -Mode refresh-v3 on $now.

The legacy ``.claude/cross-repo/`` configuration was removed during the v3
upgrade and replaced by the **Specialist Export Artifact** pattern.

## What was removed

- ``.claude/cross-repo/`` (backed up to ``$($backupRoot.Replace($script:PROJECT_DIR + '\', ''))``)
- ``.claude/scripts/install/add-cross-repo.sh`` / ``.ps1`` (no longer ships in v3)

## What to do next

If sibling projects depended on cross-repo, vendor each project's ``EXPERT.md``
instead. From the home project:

    python3 .claude/scripts/forge/forge.py specialist add <name> --domain "..."

Then vendor the generated ``EXPERT.md`` into consumer projects via git submodule,
copy-with-sync, or symlink.

## Original cross-repo entries (for reference)

``````
$entries
``````
"@
    Set-Content -Path $notesFile -Value $notes

    if (Test-Path $crossRepoDir)   { Remove-Item -Path $crossRepoDir   -Recurse -Force }
    if (Test-Path $legacyScript)   { Remove-Item -Path $legacyScript   -Force }
    if (Test-Path $legacyScriptPs) { Remove-Item -Path $legacyScriptPs -Force }

    Say-Ok "Cleanup complete; notes at .claude/v3-migration-notes.md"
}

function Install-V3FrameworkFiles {
    Say-Step "Copying v3 framework surfaces into .claude/ (preserving user content)"
    $target = Join-Path $script:PROJECT_DIR ".claude"
    if (Test-Path $target) {
        if ($script:BackupEnabled) {
            Invoke-WithSpinner "Snapshotting current .claude/ to backups/" { Backup-File $target }
        } else {
            Say-Warn "Skipping snapshot (-NoBackup) — refresh-v3 is not reversible in place"
        }
    }
    if (-not (Test-Path $target)) { New-Item -Path $target -ItemType Directory -Force | Out-Null }

    # Exclude paths under the framework root that must NOT be copied to .claude/.
    # Matches install.sh rsync --exclude semantics: each entry is a path relative
    # to the framework root. A directory exclude also blocks all of its contents.
    $excludePaths = @(
        '.git', '.github', '.gitignore', '_archive', 'daily',
        'ISA.md',                                  # framework's own ISA, not consumers'
        'scripts\install',                         # the installer itself
        'scripts\preflight\_local_shims.sh',      # user-extended shim
        'docs',                                    # framework dev-repo docs only
        'backups',
        'settings.json', 'settings.local.json',
        'memories\sessions\active', 'memories\sessions\completed', 'memories\progress-notes.md',
        'agents\specialists',                      # user-owned project specialists
        'knowledge', 'worktrees',
        'mcp-servers',                              # user-extended MCP servers
        '.venv', '.pytest_cache', '__pycache__',
        '.DS_Store', '.remember', '.forge', '.superpowers', '.vscode'
    )
    # Framework-root files that the project may customise — preserve if they
    # already exist (refresh = don't clobber). Fresh installs still get the
    # framework version because the destination won't exist yet.
    $preserveIfExists = @('CLAUDE.md')

    # Walk every file in the framework recursively. Per-file copy with computed
    # destination paths avoids PowerShell Copy-Item's nested-dir bug (dst/dir/dir/)
    # when Copy-Item -Recurse targets an already-existing directory.
    Get-ChildItem -Path $FrameworkDir -Recurse -File -Force | ForEach-Object {
        $rel = $_.FullName.Substring($FrameworkDir.Length).TrimStart('\','/')

        # Skip __pycache__/.pyc noise outright
        if ($rel -like '*\__pycache__\*' -or $rel -like '*/__pycache__/*' -or $rel -like '*.pyc') { return }

        # Skip if rel matches any exclude path (exact file match or directory prefix).
        foreach ($pat in $excludePaths) {
            if ($rel -eq $pat -or $rel.StartsWith("$pat\") -or $rel.StartsWith("$pat/")) { return }
        }

        $dest = Join-Path $target $rel
        if ($preserveIfExists -contains $rel -and (Test-Path $dest)) { return }

        $destParent = Split-Path -Parent $dest
        if (-not (Test-Path $destParent)) { New-Item -Path $destParent -ItemType Directory -Force | Out-Null }
        Copy-Item -Path $_.FullName -Destination $dest -Force
    }

    # Belt-and-suspenders: stray legacy paths under .claude/.
    Remove-Item -Path (Join-Path $target "daily") -Recurse -Force -ErrorAction SilentlyContinue

    Say-Ok "v3 framework files in place"
}

function Guard-SkillCollisions {
    # Parity with install.sh guard_skill_collisions. Back up any consumer skill
    # at skills\<name>\ whose dir name collides with an incoming framework skill
    # AND whose contents differ, before Install-V3FrameworkFiles' force-copy
    # overwrites it. `.local`-suffixed skills are never at risk (the framework
    # ships no `.local` skill, so the source walk never produces one), so skip
    # them. Run BEFORE Install-V3FrameworkFiles.
    $consumerSkills  = Join-Path $script:PROJECT_DIR ".claude\skills"
    $frameworkSkills = Join-Path $FrameworkDir "skills"
    if (-not (Test-Path $consumerSkills) -or -not (Test-Path $frameworkSkills)) {
        Say-Ok "No skill name collisions (consumer skills safe)"
        return
    }
    $backupRoot = Join-Path (Get-BackupRoot) "skill-collisions"
    $collisions = 0
    foreach ($cdir in (Get-ChildItem -Path $consumerSkills -Directory -Force)) {
        $name = $cdir.Name
        if ($name -like '*.local') { continue }   # protected convention
        $fdir = Join-Path $frameworkSkills $name
        if (-not (Test-Path $fdir)) { continue }   # no framework skill of this name
        # Same name on both sides — only act if contents differ.
        $cHash = (Get-ChildItem $cdir.FullName -Recurse -File -Force | Get-FileHash -Algorithm SHA256 | ForEach-Object Hash | Sort-Object) -join ''
        $fHash = (Get-ChildItem $fdir -Recurse -File -Force | Get-FileHash -Algorithm SHA256 | ForEach-Object Hash | Sort-Object) -join ''
        if ($cHash -ne $fHash) {
            if (-not (Test-Path $backupRoot)) { New-Item -Path $backupRoot -ItemType Directory -Force | Out-Null }
            Copy-Item -Path $cdir.FullName -Destination (Join-Path $backupRoot $name) -Recurse -Force
            Say-Warn "Skill name collision: consumer skills\$name\ differs from the framework's — refresh will overwrite it."
            Write-Host "   Backed up your copy to: $(Join-Path $backupRoot $name)"
            Write-Host "   To keep it across future refreshes, rename it to skills\$name.local\ (invoked as /$name.local)."
            $collisions++
        }
    }
    if ($collisions -gt 0) { Say-Warn "$collisions skill collision(s) backed up before refresh - see messages above." }
    else                   { Say-Ok "No skill name collisions (consumer skills safe)" }
}

function Install-V3SeedSpecialists {
    # The v3 framework ships a README.md + .gitkeep at agents\specialists\ to
    # document the user-owned-never-replaced guarantee. Install-V3FrameworkFiles
    # excludes that path to preserve user specialists — but that also blocks
    # seeding when the dir is empty/missing. Seed explicitly here.
    $dst = Join-Path $script:PROJECT_DIR ".claude\agents\specialists"
    if (-not (Test-Path $dst)) { New-Item -Path $dst -ItemType Directory -Force | Out-Null }
    $seeded = $false
    $srcReadme  = Join-Path $FrameworkDir "agents\specialists\README.md"
    $dstReadme  = Join-Path $dst "README.md"
    $dstGitkeep = Join-Path $dst ".gitkeep"
    if (-not (Test-Path $dstReadme) -and (Test-Path $srcReadme)) {
        Copy-Item -Path $srcReadme -Destination $dstReadme -Force
        $seeded = $true
    }
    if (-not (Test-Path $dstGitkeep)) {
        New-Item -Path $dstGitkeep -ItemType File -Force | Out-Null
        $seeded = $true
    }
    if ($seeded) { Say-Ok "Seeded agents\specialists\ scaffold (README + .gitkeep)" }
    else         { Say-Ok "agents\specialists\ scaffold already present" }
}

function Install-V3CutV2Cleanup {
    Say-Step "Removing v2 framework files cut in v3 (cleanup)"

    $cleanupRoot = Join-Path $script:PROJECT_DIR ".claude"
    $backupRoot  = Join-Path (Get-BackupRoot) "cut-v2"
    $removed     = 0
    $backedUp    = $false

    function Backup-ThenRemove {
        param([string]$SourcePath)
        if (-not (Test-Path $SourcePath)) { return $false }
        $rel  = $SourcePath.Substring($script:cleanupRoot.Length).TrimStart("\","/")
        $dest = Join-Path $script:backupRoot $rel
        $destParent = Split-Path -Parent $dest
        if (-not (Test-Path $destParent)) { New-Item -Path $destParent -ItemType Directory -Force | Out-Null }
        Copy-Item -Path $SourcePath -Destination $dest -Recurse -Force
        Remove-Item -Path $SourcePath -Recurse -Force
        return $true
    }

    # Make outer-scope vars accessible to the helper.
    $script:cleanupRoot = $cleanupRoot
    $script:backupRoot  = $backupRoot

    # 13 cut framework agents (v3 keeps: architect, project-manager,
    # quality-engineer, security-boss, devops). Their summaries also go.
    $cutAgents = @(
        "analyst", "api-tester", "build-resolver", "doc-updater", "e2e-runner",
        "orchestrator", "performance-enhancer", "refactor-cleaner", "scrum-master",
        "tdd-guide", "ux-designer", "visual-mistro", "whimsy"
    )
    foreach ($a in $cutAgents) {
        if (Backup-ThenRemove (Join-Path $cleanupRoot "agents\$a.md"))            { $removed++; $backedUp = $true }
        if (Backup-ThenRemove (Join-Path $cleanupRoot "agents\summaries\$a.md")) { $removed++; $backedUp = $true }
    }

    # commands\ — entire directory cut in v3 (ISC-12 + ISC-13).
    if (Backup-ThenRemove (Join-Path $cleanupRoot "commands")) { $removed++; $backedUp = $true }

    # features\ — empty placeholder dir in v2; cut in v3.
    if (Backup-ThenRemove (Join-Path $cleanupRoot "features")) { $removed++; $backedUp = $true }

    # skills\cross-repo\ — replaced by Specialist Export Artifact pattern.
    if (Backup-ThenRemove (Join-Path $cleanupRoot "skills\cross-repo")) { $removed++; $backedUp = $true }

    if ($removed -gt 0) {
        Say-Ok "Removed $removed v2 cut framework path(s); backups at $($backupRoot.Substring($script:PROJECT_DIR.Length + 1))"
        if ($backedUp) { $script:BackupsCreated++ }
    } else {
        Say-Ok "No v2 cut framework files present (clean)"
    }
}

# Read the cut-paths manifest (one relative path per line, # comments allowed)
# and remove each listed path from the consumer's .claude\ tree. Honors
# -NoBackup; refuses to touch user-owned roots; rejects absolute paths and
# `..` traversals. Mirror of install.sh:install_v3_cleanup_cut_paths.
# See scripts/install/README.md for the maintainer workflow.
function Install-V3CleanupCutPaths {
    Say-Step "Removing framework-cut paths (cut-paths.txt)"

    $manifest = Join-Path $ScriptDir "cut-paths.txt"
    if (-not (Test-Path $manifest)) {
        Say-Warn "cut-paths manifest not found at $manifest — skipping"
        return
    }

    $cleanupRoot = Join-Path $script:PROJECT_DIR ".claude"
    $backupRoot  = Join-Path (Get-BackupRoot) "cut-paths"
    $removed     = 0
    $backedUp    = $false

    # Anti-clobber denylist (ISC-10).
    $protectedRoots = @(
        "agents/specialists",
        "docs/tasks",
        "docs/project-memory",
        "daily"
    )

    foreach ($raw in (Get-Content $manifest)) {
        $rel = $raw.Trim()
        if ([string]::IsNullOrEmpty($rel)) { continue }
        if ($rel.StartsWith("#"))          { continue }

        # Reject absolute paths (ISC-11): leading /, leading \, or Windows
        # drive letter (e.g. C:\).
        if ($rel.StartsWith("/") -or $rel.StartsWith("\") -or ($rel -match '^[A-Za-z]:[\\/]')) {
            Say-Fail "cut-paths manifest rejected: absolute path not allowed: '$rel'"
            throw "cut-paths manifest rejected: absolute path: $rel"
        }
        # Reject `..` traversal (ISC-11).
        if ($rel -match '\.\.') {
            Say-Fail "cut-paths manifest rejected: '..' traversal not allowed: '$rel'"
            throw "cut-paths manifest rejected: traversal: $rel"
        }

        # Normalize separators and strip trailing slash for comparison.
        $relNorm = $rel.Replace("\", "/").TrimEnd("/")

        # Denylist enforcement (ISC-10).
        $protected = $null
        foreach ($guard in $protectedRoots) {
            if ($relNorm -eq $guard -or $relNorm.StartsWith("$guard/")) {
                $protected = $guard
                break
            }
        }
        if ($protected) {
            Say-Fail "cut-paths manifest rejected: '$rel' is under protected user-owned root '$protected/' (denylist)"
            throw "cut-paths manifest rejected: protected root: $rel"
        }

        # Build the consumer path (use OS separator).
        $relForPath = $relNorm.Replace("/", [System.IO.Path]::DirectorySeparatorChar)
        $src = Join-Path $cleanupRoot $relForPath
        if (-not (Test-Path $src)) { continue }

        if ($script:BackupEnabled) {
            $dest = Join-Path $backupRoot $relForPath
            $destParent = Split-Path -Parent $dest
            if (-not (Test-Path $destParent)) {
                New-Item -Path $destParent -ItemType Directory -Force | Out-Null
            }
            Copy-Item -Path $src -Destination $dest -Recurse -Force
            Remove-Item -Path $src -Recurse -Force
            $relBackup = $backupRoot.Substring($script:PROJECT_DIR.Length + 1)
            Write-Host "  cut: $relNorm (backed up to $relBackup/$relNorm)"
            $backedUp = $true
        } else {
            Remove-Item -Path $src -Recurse -Force
            Write-Host "  cut: $relNorm (removed)"
        }
        $removed++
    }

    if ($removed -gt 0) {
        if ($backedUp) {
            $relBackup = $backupRoot.Substring($script:PROJECT_DIR.Length + 1)
            Say-Ok "Removed $removed cut path(s); backups at $relBackup"
            $script:BackupsCreated++
        } else {
            Say-Ok "Removed $removed cut path(s)"
        }
    } else {
        Say-Ok "No framework-cut paths present (clean)"
    }
}

function Install-V3VerifyFix {
    $verifyBash = Join-Path $ScriptDir "verify.sh"
    if (-not (Test-Path $verifyBash)) {
        Say-Warn "verify.sh not found — skipping --fix step"
        return
    }
    $bash = Get-Command bash -ErrorAction SilentlyContinue
    if (-not $bash) {
        Say-Warn "bash not on PATH — skipping verify.sh --fix (Windows users: install Git for Windows or use WSL)"
        return
    }
    Say-Step "Running verify.sh --fix to auto-fix trivial drift"
    # Bash on Windows comes in two flavours with different POSIX path mappings:
    #   WSL (system32\bash.exe)     : C:\foo -> /mnt/c/foo
    #   Git Bash / Cygwin / MSYS    : C:\foo -> /c/foo
    # Detect which we're on; otherwise bash treats backslashes as escapes.
    $bashSrcLower = $bash.Source.ToLower()
    $isWslBash = ($bashSrcLower -like '*\system32\*') -or ($bashSrcLower -like '*\windowsapps\*')
    function ConvertTo-BashPath {
        param([string]$WinPath, [bool]$Wsl)
        if ($WinPath -match '^([A-Za-z]):[\\/](.*)$') {
            $drive = $matches[1].ToLower()
            $rest  = $matches[2].Replace('\', '/')
            if ($Wsl) { return "/mnt/$drive/$rest" } else { return "/$drive/$rest" }
        }
        return $WinPath.Replace('\', '/')
    }
    $projectBashPath = ConvertTo-BashPath $script:PROJECT_DIR $isWslBash
    # verify.sh may be checked out with CRLF (Windows git default), which bash
    # chokes on. Strip CRs into a temp copy and run that. Avoids the PowerShell
    # 5.1 native-command quoting minefield with bash -c.
    $rawSh = [System.IO.File]::ReadAllText($verifyBash)
    $cleanSh = $rawSh -replace "`r`n", "`n" -replace "`r", "`n"
    # IMPORTANT: write the cleaned copy as a sibling of verify.sh so its
    # SCRIPT_DIR/FRAMEWORK_DIR relative traversal (../..) still resolves to
    # the framework root. A %TEMP% location would break that.
    $tempSh = Join-Path (Split-Path -Parent $verifyBash) (".verify-clean-{0}.sh" -f ([guid]::NewGuid().ToString('N')))
    [System.IO.File]::WriteAllText($tempSh, $cleanSh, (New-Object System.Text.UTF8Encoding($false)))
    $tempShBash = ConvertTo-BashPath $tempSh $isWslBash
    try {
        & $bash.Source $tempShBash $projectBashPath --fix
    } finally {
        Remove-Item -Path $tempSh -Force -ErrorAction SilentlyContinue
    }
    if ($LASTEXITCODE -eq 0) { Say-Ok "verify.sh --fix completed" }
    else                     { Say-Warn "verify.sh reported issues — review the output above" }
}

# ---------------------------------------------------------------------------
# Orchestration per mode
# ---------------------------------------------------------------------------

function Invoke-Full {
    Set-Phases 10
    Write-Section "Running: Full install"
    if ($script:HAS_CLAUDE) {
        Write-Section "Backing up existing .claude/"
        Install-FrameworkOverwrite
    } else {
        Write-Section "Installing framework files"
        Install-FrameworkFresh
    }
    Write-Section "Session directories"
    Install-SessionDirs
    Write-Section "Project memory"
    Install-ProjectMemory
    Write-Section "Wiring settings.json"
    Install-Settings
    Write-Section "Memory schema doc"
    Install-Schema
    Write-Section "Daily logs directory"
    Install-Daily
    Write-Section ".gitignore"
    Update-GitIgnore
    Write-Section "Root CLAUDE.md framework import"
    Install-RootClaudeMdImport
    Write-Section "Cleanup stray dirs"
    Clear-StrayDirs
}

function Invoke-Refresh {
    Set-Phases 9
    Write-Section "Running: Refresh framework files"
    Install-FrameworkRefresh
    Write-Section "Removing framework-retired paths"
    Install-V3CleanupCutPaths
    Write-Section "Session directories"
    Install-SessionDirs
    Write-Section "Wiring settings.json"
    Install-Settings
    Write-Section "Memory schema doc"
    Install-Schema
    Write-Section "Daily logs directory"
    Install-Daily
    Write-Section ".gitignore"
    Update-GitIgnore
    Write-Section "Root CLAUDE.md framework import"
    Install-RootClaudeMdImport
    Write-Section "Cleanup stray dirs"
    Clear-StrayDirs
}

function Invoke-RefreshV3 {
    Set-Phases 15
    Write-Section "Running: Forge Flow v3 upgrade (refresh-v3)"
    if ($script:HAS_CLAUDE -eq 0) {
        Say-Warn ".claude/ not present — refresh-v3 expects an existing install."
        Say-Warn "For a fresh install, use -Mode full instead."
    }
    Write-Section "Cross-repo cleanup"
    Install-V3CrossRepoCleanup
    Write-Section "Skill collision guard"
    Guard-SkillCollisions
    Write-Section "Framework files (rsync)"
    Install-V3FrameworkFiles
    Write-Section "Cutting v2 leftovers"
    Install-V3CutV2Cleanup
    Write-Section "Cutting framework-removed paths"
    Install-V3CleanupCutPaths
    Write-Section "Seeding specialists/ scaffold"
    Install-V3SeedSpecialists
    Write-Section "Session directories"
    Install-SessionDirs
    Write-Section "Wiring settings.json"
    Install-Settings
    Write-Section "Memory schema doc"
    Install-Schema
    Write-Section "Daily logs directory"
    Install-Daily
    Write-Section ".gitignore"
    Update-GitIgnore
    Write-Section "Root CLAUDE.md framework import"
    Install-RootClaudeMdImport
    Write-Section "Cleanup stray dirs"
    Clear-StrayDirs
    Write-Section "Verify and fix"
    Install-V3VerifyFix
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

function Write-Summary {
    $script:PhasesTotal = 0  # final summary banner — no counter
    try { Write-Progress -Activity "Claude Forge install" -Completed } catch { }
    Write-Section "Done"
    $elapsed = [int]((Get-Date) - $script:InstallStartTime).TotalSeconds
    Say-Ok "Installation mode: $script:INSTALL_MODE"
    Say-Ok "Project: $script:PROJECT_DIR"
    Say-Ok "Total time: ${elapsed}s"
    if ($script:BackupsCreated -gt 0) {
        Say-Ok "Backups: $script:BackupsCreated file(s) saved to $(Get-BackupRoot)"
    }
    Write-Host ""
    Write-Color "Next steps:" Cyan
    Write-Host ""
    switch ($script:INSTALL_MODE) {
        "full" {
            if ($script:HAS_CLAUDE) {
                Write-Host "  1. cd `"$script:PROJECT_DIR`""
                Write-Host "  2. claude"
                Write-Host "  3. Run /migrate inside Claude Code to merge your old .claude/ config"
                Write-Host "  4. If something goes wrong: .\\.claude_restore.ps1"
            } else {
                Write-Host "  1. cd `"$script:PROJECT_DIR`""
                Write-Host "  2. claude"
                Write-Host "  3. Run /new-project or /new-project --current"
            }
        }
        "refresh-framework" {
            if ($script:BackupsCreated -gt 0) {
                Write-Host "  1. Review diffs of any files in $(Get-BackupRoot)"
                Write-Host "  2. cd `"$script:PROJECT_DIR`"; claude"
            } else {
                Write-Host "  1. cd `"$script:PROJECT_DIR`"; claude"
                Write-Host "  (No backup taken - refresh is not reversible in place.)"
            }
        }
        "refresh-v3" {
            Write-Host "  1. Review .claude/v3-migration-notes.md (if present - cross-repo cleanup notes)"
            if ($script:BackupsCreated -gt 0) {
                Write-Host "  2. Review backups at $(Get-BackupRoot)"
                Write-Host "  3. cd `"$script:PROJECT_DIR`"; claude"
                Write-Host "  4. Verify .claude/ALGORITHM/LATEST and .claude/CLAUDE.md reflect the current framework version"
                Write-Host "  5. Run python3 .claude/scripts/forge/forge.py specialist list"
            } else {
                Write-Host "  2. cd `"$script:PROJECT_DIR`"; claude"
                Write-Host "  3. Verify .claude/ALGORITHM/LATEST and .claude/CLAUDE.md reflect the current framework version"
                Write-Host "  4. Run python3 .claude/scripts/forge/forge.py specialist list"
                Write-Host "  (No backup taken - refresh is not reversible in place.)"
            }
        }
    }
    Write-Host ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

$script:PRESET_MODE = $Mode

Write-Banner

# Verify we're inside the framework repo. v2 required skills/; v3 builds
# incrementally so the spine (scripts/forge/) is the stable signature.
if (-not (Test-Path (Join-Path $FrameworkDir "CLAUDE.md")) -or -not (Test-Path (Join-Path $FrameworkDir "scripts\forge") -PathType Container)) {
    Say-Fail "Must be run from inside the forgeFlow repository. Expected framework at: $FrameworkDir"
    exit 1
}
Say-Ok "Framework at: $FrameworkDir"

Invoke-Preflight
Select-ProjectDir -Preset $ProjectPath
Invoke-DetectState
Select-Mode

# --- Backup decision (refresh modes back up existing .claude\) ---
# Resolution order:
#   1. Explicit -Backup / -NoBackup switches — wins
#   2. Interactive prompt (default Yes) on refresh / refresh-v3
#   3. Default ON otherwise
if ($Backup -and $NoBackup) {
    Say-Fail "-Backup and -NoBackup are mutually exclusive"
    exit 1
}
if ($Backup) {
    $script:BackupEnabled = $true
    Say-Ok "Backup: ON (-Backup)"
} elseif ($NoBackup) {
    $script:BackupEnabled = $false
    Say-Warn "Backup: OFF (-NoBackup) — you cannot revert this refresh in place"
} else {
    if ($script:INSTALL_MODE -eq "refresh-framework" -or $script:INSTALL_MODE -eq "refresh-v3") {
        if ($Yes) {
            $script:BackupEnabled = $true
            Say-Ok "Backup: ON (-Yes default — pass -NoBackup to skip)"
        } elseif ($script:HAS_CLAUDE) {
            Write-Host ""
            Write-Host "Refresh will overwrite framework files in $script:PROJECT_DIR\.claude\"
            Write-Host "A backup snapshots the current .claude\ to backups\$BackupStamp\"
            Write-Host "before the refresh — lets you diff or roll back per file."
            $b = Read-Host "Back up existing .claude\ before refresh? [Y/n]"
            if ($b -match '^[Nn]$') {
                $script:BackupEnabled = $false
                Say-Warn "Backup: OFF — refresh will not be reversible in place"
            } else {
                $script:BackupEnabled = $true
                Say-Ok "Backup: ON — snapshot will land at backups\$BackupStamp\"
            }
        }
    }
}

Write-Host ""
if ($Yes) {
    Say-Ok "Proceeding with $script:INSTALL_MODE (-Yes)"
} else {
    $go = Read-Host "Proceed with $script:INSTALL_MODE? [Y/n]"
    if ($go -match '^[Nn]$') { Write-Host "Cancelled."; exit 0 }
}

switch ($script:INSTALL_MODE) {
    "full"              { Invoke-Full }
    "refresh-framework" { Invoke-Refresh }
    "refresh-v3"        { Invoke-RefreshV3 }
}

Write-Summary
