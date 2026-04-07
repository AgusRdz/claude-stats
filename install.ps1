#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Repo       = "AgusRdz/claude-stats"
$InstallDir = if ($env:CLAUDE_STATS_INSTALL_DIR) {
    $env:CLAUDE_STATS_INSTALL_DIR
} else {
    "$env:LOCALAPPDATA\Programs\claude-stats"
}

# Detect architecture
$Arch = if (
    [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -eq
    [System.Runtime.InteropServices.Architecture]::Arm64
) { "arm64" } else { "amd64" }

$Binary = "claude-stats-windows-$Arch.exe"

# Get latest version
if (-not $env:CLAUDE_STATS_VERSION) {
    $Release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest"
    $env:CLAUDE_STATS_VERSION = $Release.tag_name
}

if (-not $env:CLAUDE_STATS_VERSION) {
    Write-Error "failed to determine latest version"
    exit 1
}

$Url         = "https://github.com/$Repo/releases/download/$($env:CLAUDE_STATS_VERSION)/$Binary"
$Destination = Join-Path $InstallDir "claude-stats.exe"

Write-Host "installing claude-stats $($env:CLAUDE_STATS_VERSION) (windows/$Arch)..."

# Create install dir
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# Download binary
Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing

Write-Host "installed claude-stats to $Destination"
Write-Host ""

# Add to user PATH if not already present
$UserPath        = [Environment]::GetEnvironmentVariable("PATH", "User")
$CleanInstallDir = $InstallDir.TrimEnd("\")
$PathParts       = $UserPath -split ";" | ForEach-Object { $_.TrimEnd("\") }

if ($PathParts -notcontains $CleanInstallDir) {
    $NewUserPath = "$InstallDir;$UserPath"
    [Environment]::SetEnvironmentVariable("PATH", $NewUserPath, "User")
    Write-Host "added $InstallDir to PATH"
}

# Update current session PATH so claude-stats is usable immediately
$CurrentPathParts = $env:PATH -split ";" | ForEach-Object { $_.TrimEnd("\") }
if ($CurrentPathParts -notcontains $CleanInstallDir) {
    $env:PATH = "$InstallDir;$env:PATH"
}

# Broadcast PATH change to running processes (Windows-specific)
$HWND_BROADCAST = [IntPtr]0xffff
$WM_SETTINGCHANGE = 0x001a
$MethodDefinition = @'
[DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
public static extern IntPtr SendMessageTimeout(
    IntPtr hWnd, uint Msg, IntPtr wParam, string lParam,
    uint fuFlags, uint uTimeout, out IntPtr lpdwResult);
'@
$User32 = Add-Type -MemberDefinition $MethodDefinition -Name "User32" -Namespace "Win32" -PassThru
$result = [IntPtr]::Zero
$User32::SendMessageTimeout(
    $HWND_BROADCAST, $WM_SETTINGCHANGE,
    [IntPtr]::Zero, "Environment",
    2, 100, [ref]$result
) | Out-Null

Write-Host ""
Write-Host "done! run: claude-stats"
