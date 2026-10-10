# PowerShell 7+; single src-tauri crate, no downloads or global configuration changes.
param([ValidateSet('format', 'lint', 'test', 'build', 'all')][string]$Stage = 'all')
$oldErrorPreference = $ErrorActionPreference
$ErrorActionPreference = 'Stop'
$oldNativePreference = $PSNativeCommandUseErrorActionPreference
$PSNativeCommandUseErrorActionPreference = $false
$oldPath = $env:PATH
$oldToolchain = $env:RUSTUP_TOOLCHAIN
$oldAutoInstall = $env:RUSTUP_AUTO_INSTALL
$oldLocation = Get-Location
$script:ExitCode = 1

function Invoke-Tool {
    param([string]$Tool, [string[]]$Arguments)
    $output = & $Tool @Arguments 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        $output | ForEach-Object { Write-Host "$_" }
        $script:ExitCode = $code
        throw "native tool failed: $Tool (exit $code)"
    }
    return $output
}

try {
    if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7+ is required' }
    Set-Location (Join-Path $PSScriptRoot '..')
    if (!(Test-Path 'rust-toolchain.toml' -PathType Leaf)) { throw 'missing rust-toolchain.toml' }
    if ((Get-Content 'rust-toolchain.toml' -Raw) -notmatch '(?m)^channel = "1\.92\.0"\r?$') {
        throw 'requires pinned Rust 1.92.0'
    }
    $env:RUSTUP_AUTO_INSTALL = '0'
    $rustup = (Get-Command rustup -CommandType Application).Source
    $rustupVersion = [string](Invoke-Tool $rustup @('--version'))
    Write-Host $rustupVersion
    if ($rustupVersion -notmatch '^rustup ([0-9]+\.[0-9]+\.[0-9]+) ' -or
        [version]$Matches[1] -lt [version]'1.28.2') { throw 'requires rustup 1.28.2 or newer' }
    # List installed full names first; even rustup which can bootstrap.
    $installed = Invoke-Tool $rustup @('toolchain', 'list')
    $toolchain = $installed | ForEach-Object { ([string]$_ -split '\s+')[0] } |
        Where-Object { $_ -match '^1\.92\.0-[a-zA-Z0-9_]+-[a-zA-Z0-9_]+-[a-zA-Z0-9_-]+$' } |
        Select-Object -First 1
    if (!$toolchain) { throw 'Rust 1.92.0 must already be installed' }
    $cargo = [string](Invoke-Tool $rustup @('which', '--toolchain', $toolchain, 'cargo'))
    $rustc = [string](Invoke-Tool $rustup @('which', '--toolchain', $toolchain, 'rustc'))
    $fmt = [string](Invoke-Tool $rustup @('which', '--toolchain', $toolchain, 'cargo-fmt'))
    $clippy = [string](Invoke-Tool $rustup @('which', '--toolchain', $toolchain, 'cargo-clippy'))
    foreach ($tool in @($cargo, $rustc, $fmt, $clippy)) {
        if (!(Test-Path $tool -PathType Leaf)) { throw "tool must already be installed: $tool" }
        Write-Host "tool: $tool"
    }
    $env:PATH = (Split-Path $cargo) + [IO.Path]::PathSeparator + $env:PATH
    $env:RUSTUP_TOOLCHAIN = $toolchain
    $version = [string](Invoke-Tool $rustc @('--version'))
    Write-Host $version
    if ($version -notmatch '^rustc 1\.92\.0 ') { throw 'requires Rust 1.92.0' }
    foreach ($tool in @($cargo, $fmt, $clippy)) {
        Invoke-Tool $tool @('--version') | ForEach-Object { Write-Host "$_" }
    }
    $manifest = 'src-tauri/Cargo.toml'
    foreach ($file in @($manifest, 'src-tauri/src/main.rs', 'src-tauri/src/lib.rs', 'src-tauri/Cargo.lock')) {
        if (!(Test-Path $file -PathType Leaf)) { throw "missing manifest/source/Cargo.lock: $file" }
        if ([string]::IsNullOrWhiteSpace((Get-Content $file -Raw))) { throw "empty manifest/source/Cargo.lock: $file" }
    }
    $steps = if ($Stage -eq 'all') { @('format', 'lint', 'test', 'build') } else { @($Stage) }
    foreach ($step in $steps) {
        Write-Host "stage: $step"
        switch ($step) {
            'format' { Invoke-Tool $cargo @('fmt', '--manifest-path', $manifest, '--check') }
            'lint' { Invoke-Tool $cargo @('clippy', '--manifest-path', $manifest, '--locked', '--all-targets', '--', '-D', 'warnings') }
            'test' {
                $listing = Invoke-Tool $cargo @('test', '--manifest-path', $manifest, '--locked', '--', '--list')
                $listing | ForEach-Object { Write-Host "$_" }
                if (($listing -join "`n") -notmatch '(?m): test\r?$') { throw 'no tests discovered' }
                $output = Invoke-Tool $cargo @('test', '--manifest-path', $manifest, '--locked')
                $output | ForEach-Object { Write-Host "$_" }
                if (($output -join "`n") -notmatch 'test result: ok\. [1-9][0-9]* passed;') { throw 'no tests executed' }
            }
            'build' { Invoke-Tool $cargo @('build', '--manifest-path', $manifest, '--locked') }
        }
    }
    exit 0
} catch {
    Write-Error $_ -ErrorAction Continue
    exit $script:ExitCode
} finally {
    $env:PATH = $oldPath
    $env:RUSTUP_TOOLCHAIN = $oldToolchain
    $env:RUSTUP_AUTO_INSTALL = $oldAutoInstall
    $PSNativeCommandUseErrorActionPreference = $oldNativePreference
    $ErrorActionPreference = $oldErrorPreference
    Set-Location $oldLocation
}
