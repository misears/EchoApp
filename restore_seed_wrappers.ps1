[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [string]$BackupTimestamp = '20260724_083943',
    [switch]$KeepCurrentFlattenedCopy = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$workspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$seedsRoot = Join-Path $workspaceRoot 'seeds'
$backupRoot = Join-Path $seedsRoot (Join-Path '_wrapper_backups' $BackupTimestamp)

$repos = @(
    'ACE-Step-1.5-main',
    'Retrieval-based-Voice-Conversion-WebUI-main',
    'FFmpeg-master',
    'demucs-main'
)

if (-not (Test-Path -LiteralPath $backupRoot)) {
    throw "Backup folder not found: $backupRoot"
}

$suffix = Get-Date -Format 'yyyyMMdd_HHmmss'

foreach ($repo in $repos) {
    $currentPath = Join-Path $seedsRoot $repo
    $backupOuterPath = Join-Path $backupRoot ($repo + '__outer')
    $quarantinePath = Join-Path $backupRoot ($repo + '__flat_current_' + $suffix)

    Write-Host "\n[$repo]"

    if (-not (Test-Path -LiteralPath $backupOuterPath)) {
        Write-Warning "Backup outer folder missing, skipping: $backupOuterPath"
        continue
    }

    if (-not (Test-Path -LiteralPath $currentPath)) {
        Write-Warning "Current flattened folder missing, skipping: $currentPath"
        continue
    }

    if ($KeepCurrentFlattenedCopy) {
        Write-Host "Moving current folder to: $quarantinePath"
        if ($PSCmdlet.ShouldProcess($currentPath, "Move current flattened folder to $quarantinePath")) {
            Move-Item -LiteralPath $currentPath -Destination $quarantinePath
        }
    }
    else {
        Write-Host "Removing current folder: $currentPath"
        if ($PSCmdlet.ShouldProcess($currentPath, 'Remove current flattened folder')) {
            Remove-Item -LiteralPath $currentPath -Recurse -Force
        }
    }

    $didRestore = $false
    Write-Host "Restoring wrapper backup: $backupOuterPath -> $currentPath"
    if ($PSCmdlet.ShouldProcess($backupOuterPath, "Restore wrapper backup to $currentPath")) {
        Move-Item -LiteralPath $backupOuterPath -Destination $currentPath
        $didRestore = $true
    }

    if ($didRestore) {
        $innerPath = Join-Path $currentPath $repo
        if (Test-Path -LiteralPath $innerPath) {
            Write-Host "Restore verified: wrapper restored for $repo"
        }
        else {
            Write-Warning "Restore completed, but inner wrapper path not found: $innerPath"
        }
    }
}

Write-Host "\nRollback operation finished."