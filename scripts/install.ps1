# PowerShell Installer for Tool Background Daemon
[CmdletBinding()]
param (
    [string]$InstallDir = "C:\Program Files\tool-daemon",
    [string]$RepoUrl = "https://github.com/orpheezt/tool-daemon.git"
)

$ErrorActionPreference = "Stop"

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "        Tool Background Daemon Windows Installer     " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

# 1. Workspace detection
$ParentDir = $null
if (-not [string]::IsNullOrEmpty($PSScriptRoot)) {
    $ParentDir = Split-Path -Path $PSScriptRoot -Parent
}
$TempDir = $null

if ($ParentDir -and (Test-Path (Join-Path $ParentDir "pyproject.toml"))) {
    $SourceDir = $ParentDir
    Write-Host "→ Using local source workspace: $SourceDir" -ForegroundColor Green
} elseif (Test-Path (Join-Path $PWD "pyproject.toml")) {
    $SourceDir = $PWD
    Write-Host "→ Using local source workspace: $SourceDir" -ForegroundColor Green
} else {
    Write-Host "→ Fetching repository source code..." -ForegroundColor Yellow
    $TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.IO.Path]::GetRandomFileName())

    $HasGit = $false
    try {
        $null = & git --version 2>$null
        if ($LASTEXITCODE -eq 0) { $HasGit = $true }
    } catch {
        $HasGit = $false
    }

    if ($HasGit) {
        git clone --depth 1 $RepoUrl $TempDir
        $SourceDir = $TempDir
    } else {
        Write-Host "→ Git not found or unavailable. Downloading repository ZIP archive..." -ForegroundColor Yellow
        $ZipUrl = ($RepoUrl -replace '\.git$', '') + "/archive/refs/heads/master.zip"
        $ZipFile = Join-Path ([System.IO.Path]::GetTempPath()) "$([System.IO.Path]::GetRandomFileName()).zip"
        Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipFile
        Expand-Archive -Path $ZipFile -DestinationPath $TempDir -Force
        Remove-Item $ZipFile -ErrorAction SilentlyContinue

        $Extracted = Get-ChildItem -Path $TempDir | Select-Object -First 1
        if ($Extracted -and $Extracted.PSIsContainer) {
            $SourceDir = $Extracted.FullName
        } else {
            $SourceDir = $TempDir
        }
    }
}

try {
    # 2. Ensure uv is installed
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "→ Package manager 'uv' not found. Installing uv..." -ForegroundColor Yellow
        irm https://astral.sh/uv/install.ps1 | iex
        $env:Path = "$env:USERPROFILE\.cargo\bin;$env:USERPROFILE\.local\bin;" + $env:Path
    }

    # 3. Build wheel artifact
    Write-Host "→ Building distribution wheel artifact..." -ForegroundColor Yellow
    Set-Location $SourceDir
    uv build --wheel --out-dir "$SourceDir\dist"

    $WheelFile = Get-ChildItem -Path "$SourceDir\dist\*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $WheelFile) {
        throw "Failed to build or locate wheel artifact in $SourceDir\dist"
    }
    Write-Host "✓ Built wheel: $($WheelFile.Name)" -ForegroundColor Green

    # 4. Target directory creation
    if (-not (Test-Path $InstallDir)) {
        Write-Host "→ Creating installation directory $InstallDir..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    # 5. Read .python-version
    $PythonVer = "3.14"
    $PythonVersionFile = Join-Path $SourceDir ".python-version"
    if (Test-Path $PythonVersionFile) {
        $PythonVer = (Get-Content $PythonVersionFile).Trim()
    }

    # 6. Create virtual environment
    $VenvDir = Join-Path $InstallDir ".venv"
    Write-Host "→ Creating virtual environment (Python $PythonVer) at $VenvDir..." -ForegroundColor Yellow
    uv venv --allow-existing --python $PythonVer $VenvDir

    # 7. Install wheel package into venv
    Write-Host "→ Installing wheel into virtual environment..." -ForegroundColor Yellow
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        $VenvPython = Join-Path $VenvDir "bin\python.exe"
    }
    uv pip install --python $VenvPython $WheelFile.FullName

    # 8. Add to PATH automatically
    $VenvBinDir = Join-Path $VenvDir "Scripts"
    if (-not (Test-Path $VenvBinDir)) {
        $VenvBinDir = Join-Path $VenvDir "bin"
    }

    Write-Host "→ Adding executable directory to PATH..." -ForegroundColor Yellow

    # Update current session environment PATH
    if (-not ($env:Path -split ';' -contains $VenvBinDir)) {
        $env:Path = "$VenvBinDir;$env:Path"
    }

    # Update persistent User environment PATH
    try {
        $UserPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
        $UserPathEntries = if ($UserPath) { $UserPath -split ';' } else { @() }
        if (-not ($UserPathEntries -contains $VenvBinDir)) {
            $NewUserPath = if ($UserPath) { "$VenvBinDir;$UserPath" } else { $VenvBinDir }
            [Environment]::SetEnvironmentVariable("Path", $NewUserPath, [EnvironmentVariableTarget]::User)
            Write-Host "✓ Added $VenvBinDir to User PATH permanently" -ForegroundColor Green
        } else {
            Write-Host "✓ $VenvBinDir is already in User PATH" -ForegroundColor Green
        }
    } catch {
        Write-Host "! Could not update persistent User PATH: $_" -ForegroundColor Yellow
    }

    Write-Host "=====================================================" -ForegroundColor Cyan
    Write-Host "✓ Successfully installed tool-daemon to $InstallDir" -ForegroundColor Green
    Write-Host "✓ Virtual environment: $VenvDir" -ForegroundColor Green
    Write-Host "✓ Executable added to PATH: $VenvBinDir" -ForegroundColor Green
    Write-Host "=====================================================" -ForegroundColor Cyan
}
finally {
    if ($TempDir -and (Test-Path $TempDir)) {
        Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
    }
}
