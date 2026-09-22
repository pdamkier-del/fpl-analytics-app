param(
    [Parameter(Mandatory=$true)]
    [string]$InstallDir
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$runtimeDir = Join-Path $InstallDir 'runtime'
$pythonExe = Join-Path $runtimeDir 'python.exe'

function Test-FplPython {
    if (-not (Test-Path $pythonExe)) { return $false }
    try {
        & $pythonExe -c "import sys, http.server, json, pathlib; print(sys.version)" *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

if (Test-FplPython) {
    Write-Host 'Portable Python runtime is already ready.'
    exit 0
}

if (Test-Path $runtimeDir) {
    Remove-Item $runtimeDir -Recurse -Force
}
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

$machineArch = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
if ($machineArch -match 'ARM64') {
    $package = 'python-3.13.15-embed-arm64.zip'
} elseif ($machineArch -match 'AMD64|x86_64') {
    $package = 'python-3.13.15-embed-amd64.zip'
} else {
    $package = 'python-3.13.15-embed-win32.zip'
}

$url = "https://www.python.org/ftp/python/3.13.15/$package"
$tempZip = Join-Path $env:TEMP ("fpl-python-" + [Guid]::NewGuid().ToString('N') + '.zip')

try {
    Write-Host ''
    Write-Host 'Downloading the portable FPL runtime from Python.org...'
    Write-Host $url
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $tempZip

    Write-Host 'Extracting runtime...'
    Expand-Archive -Path $tempZip -DestinationPath $runtimeDir -Force

    if (-not (Test-FplPython)) {
        throw 'The downloaded Python runtime could not be started.'
    }

    Write-Host 'Portable runtime installed successfully.'
} finally {
    if (Test-Path $tempZip) {
        Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
    }
}
