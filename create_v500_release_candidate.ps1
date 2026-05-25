Param(
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"

$ReleaseVersion = "v5.0.0"
$TagName = "v5.0.0"
$ReleaseZipName = "ai-character-framework_v5.0.0.zip"
$RequiredPackageExtras = @(
    "install.bat",
    "run.bat"
)

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "=== $Title ==="
}

function Run-Command {
    param(
        [Parameter(Mandatory=$true)][string]$Exe,
        [Parameter(Mandatory=$true)][string[]]$ArgumentList,
        [string]$WorkingDirectory = (Get-Location).Path
    )

    if ($ArgumentList.Count -eq 0) {
        throw "Refusing to run command with empty arguments: $Exe"
    }

    Push-Location $WorkingDirectory
    try {
        Write-Host ""
        Write-Host ("> " + $Exe + " " + ($ArgumentList -join " "))
        & $Exe @ArgumentList
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $Exe $($ArgumentList -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

function Test-IgnorableReleaseLocalChange {
    param([string]$StatusLine)

    $Patterns = @(
        "^\?\? create_v500_release_candidate\.ps1$",
        "^\?\? fw_v500_final_release_commands\.md$",
        "^\?\? release/$",
        "^\?\? release\\$",
        "^\?\? release/ai-character-framework_v5\.0\.0\.zip$",
        "^\?\? release\\ai-character-framework_v5\.0\.0\.zip$",
        "^\?\? \.release_build/",
        "^\?\? \.release_build\\"
    )

    foreach ($Pattern in $Patterns) {
        if ($StatusLine -match $Pattern) {
            return $true
        }
    }

    return $false
}

function Run-FinalVerification {
    param([string]$WorkingDirectory)

    $Commands = @(
        @{ Exe = "python"; ArgumentList = @("-m", "compileall", "-q", ".") },
        @{ Exe = "python"; ArgumentList = @("scripts/smoke_public_facade.py") },
        @{ Exe = "python"; ArgumentList = @("scripts/smoke_app_sdk.py") },
        @{ Exe = "python"; ArgumentList = @("scripts/smoke_voice_output_real_tts_opt_in_boundary.py") },
        @{ Exe = "python"; ArgumentList = @("scripts/smoke_voice_output_artifact_result_contract.py") },
        @{ Exe = "python"; ArgumentList = @("scripts/smoke_voice_output_real_provider_execution_guard.py") },
        @{ Exe = "python"; ArgumentList = @("scripts/smoke_voice_output_host_app_handoff.py") },
        @{ Exe = "python"; ArgumentList = @("scripts/smoke_voice_output_v500_release_readiness.py") },
        @{ Exe = "python"; ArgumentList = @("scripts/smoke_voice_output_v500_package_readiness.py") },
        @{ Exe = "python"; ArgumentList = @("scripts/check_release_package.py") },
        @{ Exe = "python"; ArgumentList = @("examples/app_voice_output_integration.py") }
    )

    foreach ($Command in $Commands) {
        Run-Command -Exe $Command.Exe -ArgumentList $Command.ArgumentList -WorkingDirectory $WorkingDirectory
    }
}

Write-Section "Checking repository root"
$RepoRootRaw = (& git rev-parse --show-toplevel)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($RepoRootRaw)) {
    throw "This script must be run from inside the AI-Character-Framework git repository."
}
$RepoRoot = (Resolve-Path $RepoRootRaw.Trim()).Path
Set-Location $RepoRoot
Write-Host "repo_root: $RepoRoot"

if (-not (Test-Path (Join-Path $RepoRoot "framework"))) {
    throw "Expected framework directory was not found. Are you in the framework repo root?"
}
if (-not (Test-Path (Join-Path $RepoRoot "scripts/check_release_package.py"))) {
    throw "Expected release package checker was not found."
}

Write-Section "Checking git status"
$StatusLines = @(& git status --porcelain)
if ($LASTEXITCODE -ne 0) {
    throw "git status failed."
}

$BlockingStatus = @()
foreach ($Line in $StatusLines) {
    if ([string]::IsNullOrWhiteSpace($Line)) {
        continue
    }

    if (Test-IgnorableReleaseLocalChange -StatusLine $Line) {
        Write-Host "[INFO] Ignoring local release helper/artifact: $Line"
    }
    else {
        $BlockingStatus += $Line
    }
}

if ($BlockingStatus.Count -gt 0) {
    Write-Host "Blocking git status lines:"
    foreach ($Line in $BlockingStatus) {
        Write-Host "  $Line"
    }
    throw "Working tree is not clean. Commit or remove local changes before creating the fixed release zip."
}
Write-Host "[OK] git status is clean for release purposes"

Write-Section "Checking release tag"
$ExistingTag = (& git tag --list $TagName)
if ($LASTEXITCODE -ne 0) {
    throw "git tag check failed."
}
if (-not [string]::IsNullOrWhiteSpace(($ExistingTag -join ""))) {
    throw "Tag already exists: $TagName"
}
Write-Host "[OK] tag is available: $TagName"

Write-Section "Checking package extra files"
foreach ($RelativePath in $RequiredPackageExtras) {
    $SourcePath = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path $SourcePath -PathType Leaf)) {
        throw "Required package extra file is missing in the working tree: $RelativePath"
    }
    Write-Host "[OK] package extra exists: $RelativePath"
}

Write-Section "Running final verification on committed working tree"
Run-FinalVerification -WorkingDirectory $RepoRoot

$ReleaseDir = Join-Path $RepoRoot "release"
$ReleaseZipPath = Join-Path $ReleaseDir $ReleaseZipName
$BuildRoot = Join-Path $RepoRoot ".release_build"
$StageDir = Join-Path $BuildRoot "v5.0.0_stage"
$ExtractDir = Join-Path $BuildRoot "v5.0.0"
$HeadArchivePath = Join-Path $BuildRoot "v5.0.0_head.zip"

Write-Section "Preparing release directories"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null

if (Test-Path $ReleaseZipPath) {
    if (-not $Overwrite) {
        throw "Release zip already exists: $ReleaseZipPath. Re-run with -Overwrite if you intentionally want to replace it."
    }
    Remove-Item $ReleaseZipPath -Force
}
if (Test-Path $StageDir) {
    Remove-Item $StageDir -Recurse -Force
}
if (Test-Path $ExtractDir) {
    Remove-Item $ExtractDir -Recurse -Force
}
if (Test-Path $HeadArchivePath) {
    Remove-Item $HeadArchivePath -Force
}
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null

Write-Section "Creating source stage from committed HEAD"
Run-Command -Exe "git" -ArgumentList @("archive", "--format=zip", "--output=$HeadArchivePath", "HEAD") -WorkingDirectory $RepoRoot
Expand-Archive -Path $HeadArchivePath -DestinationPath $StageDir -Force
Write-Host "[OK] staged committed HEAD at: $StageDir"

Write-Section "Adding explicit package extras"
foreach ($RelativePath in $RequiredPackageExtras) {
    $SourcePath = Join-Path $RepoRoot $RelativePath
    $DestinationPath = Join-Path $StageDir $RelativePath
    $DestinationParent = Split-Path -Parent $DestinationPath
    if (-not (Test-Path $DestinationParent)) {
        New-Item -ItemType Directory -Force -Path $DestinationParent | Out-Null
    }
    Copy-Item -Path $SourcePath -Destination $DestinationPath -Force
    Write-Host "[OK] added package extra: $RelativePath"
}

Write-Section "Creating fixed release zip from staged package"
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($StageDir, $ReleaseZipPath)
Write-Host "[OK] created fixed release zip: $ReleaseZipPath"

Write-Section "Extracting fixed release zip for final verification"
New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null
Expand-Archive -Path $ReleaseZipPath -DestinationPath $ExtractDir -Force
Write-Host "[OK] extracted to: $ExtractDir"

Write-Section "Running final verification against fixed release zip contents"
Run-FinalVerification -WorkingDirectory $ExtractDir

Write-Section "Release candidate is verified"
Write-Host "release_zip: $ReleaseZipPath"
Write-Host ""
Write-Host "Next manual commands after reviewing the verified zip:"
Write-Host "git tag -a $TagName -m `"Release $ReleaseVersion`""
Write-Host "git push origin $TagName"
