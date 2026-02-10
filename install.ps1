<#
.SYNOPSIS
  Install projman (standalone binary) from GitHub Releases.

.DESCRIPTION
  Downloads the latest release asset matching the current Windows architecture
  and installs it as `projman.exe`. Also updates PATH (User or Machine).

  This script is intended for Windows PowerShell / pwsh.
  For Linux/macOS, use `get_latest_release.sh`.

.PARAMETER Owner
  GitHub repository owner. Default: wangguanran

.PARAMETER Repo
  GitHub repository name. Default: ProjectManager

.PARAMETER Token
  Optional GitHub token (helps with API rate limits / private repos).

.PARAMETER System
  Install system-wide (requires admin). Default: auto-detect.

.PARAMETER User
  Install for current user. Default: auto-detect.

.PARAMETER Prefix
  Custom install directory (overrides -System/-User).
#>

param(
    [string]$Owner = "wangguanran",
    [string]$Repo = "ProjectManager",
    [string]$Token = "",
    [switch]$System,
    [switch]$User,
    [string]$Prefix = ""
)

$ErrorActionPreference = "Stop"

function Test-IsAdmin {
    $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Detect-Arch {
    $arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    switch ($arch) {
        "X64" { return "x86_64" }
        "Arm64" { return "arm64" }
        default { return $arch.ToLowerInvariant() }
    }
}

function Resolve-InstallDir([bool]$isAdmin) {
    if ($Prefix) {
        return $Prefix
    }
    if ($System -and $User) {
        throw "Cannot use -System and -User together."
    }
    if ($System) {
        if (-not $isAdmin) {
            throw "-System requires Administrator privileges."
        }
        return (Join-Path $env:ProgramFiles "projman")
    }
    if ($User) {
        return (Join-Path $env:LOCALAPPDATA "Programs\\projman")
    }
    # auto
    if ($isAdmin) {
        return (Join-Path $env:ProgramFiles "projman")
    }
    return (Join-Path $env:LOCALAPPDATA "Programs\\projman")
}

function Ensure-PathContains([string]$dir, [string]$scope) {
    $current = [Environment]::GetEnvironmentVariable("Path", $scope)
    if (-not $current) {
        $current = ""
    }
    $parts = $current.Split(";") | Where-Object { $_ -and $_.Trim() -ne "" }
    if ($parts -contains $dir) {
        return
    }
    $newValue = ($parts + $dir) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newValue, $scope)
}

$isAdmin = Test-IsAdmin
$arch = Detect-Arch
$assetName = "projman-windows-$arch.exe"

$headers = @{
    "Accept" = "application/vnd.github.v3+json"
}
if ($Token) {
    $headers["Authorization"] = "token $Token"
}

$releaseUrl = "https://api.github.com/repos/$Owner/$Repo/releases/latest"
Write-Host "Fetching latest release from $Owner/$Repo ..."
$release = Invoke-RestMethod -Headers $headers -Uri $releaseUrl

if (-not $release.assets -or $release.assets.Count -eq 0) {
    throw "No assets found in the latest release."
}

$asset = $release.assets | Where-Object { $_.name -eq $assetName } | Select-Object -First 1
if (-not $asset) {
    Write-Host "Preferred asset not found: $assetName"
    Write-Host "Falling back to the first asset in the release."
    $asset = $release.assets | Select-Object -First 1
}

$downloadUrl = $asset.browser_download_url
Write-Host "Downloading: $($asset.name)"
$tmp = New-TemporaryFile
Invoke-WebRequest -Uri $downloadUrl -OutFile $tmp

$installDir = Resolve-InstallDir -isAdmin $isAdmin
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
$dest = Join-Path $installDir "projman.exe"
Move-Item -Force $tmp $dest

# Update PATH
$scope = "User"
if ($System -or (-not $User -and $isAdmin -and -not $Prefix)) {
    $scope = "Machine"
}
Ensure-PathContains -dir $installDir -scope $scope

# Update current session PATH
$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = @($machinePath, $userPath) -join ";"

Write-Host "Installed: $dest"
Write-Host "PATH updated ($scope): $installDir"
Write-Host "Verifying:"
& $dest --version

