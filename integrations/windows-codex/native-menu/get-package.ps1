# Dot-source this helper. A completed download is promoted only after size/SHA verification.
function Get-TokenBotsPackage {
    param([Parameter(Mandatory=$true)][string]$Url,
          [Parameter(Mandatory=$true)][string]$Destination,
          [Parameter(Mandatory=$true)][string]$Sha256,
          [Parameter(Mandatory=$true)][long]$Size,
          [ValidateRange(1,5)][int]$Attempts = 3,
          [ValidateRange(0,30)][int]$RetryDelay = 3)
    $ErrorActionPreference = 'Stop'
    if ($Sha256 -notmatch '^[a-f0-9]{64}$' -or $Size -le 0) { throw 'Invalid package descriptor.' }
    $uri = [uri]$Url
    $protocol = if ($uri.Scheme -eq 'https') { '=https' } elseif ($uri.Scheme -eq 'http' -and $uri.IsLoopback) { '=http' } else { throw 'HTTPS is required for package downloads.' }
    $parent = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $lock = $null
    try {
        try { $lock = [IO.File]::Open(($Destination + '.lock'),'OpenOrCreate','ReadWrite','None') }
        catch { throw 'Another installer is using this download. Close the other installer and retry.' }
        function Test-Package([string]$Path) {
            return ((Test-Path -LiteralPath $Path -PathType Leaf) -and
                (Get-Item -LiteralPath $Path).Length -eq $Size -and
                (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -eq $Sha256)
        }
        if (Test-Package $Destination) {
            Write-Host 'Using verified cached official desktop package.'
            return $Destination
        }
        if (Test-Path -LiteralPath $Destination) {
            Move-Item -LiteralPath $Destination -Destination ($Destination + '.invalid-' + [guid]::NewGuid().ToString('N'))
        }
        $partial = $Destination + '.partial'
        if ((Test-Path -LiteralPath $partial) -and (Get-Item -LiteralPath $partial).Length -ge $Size) {
            if (Test-Package $partial) {
                Move-Item -LiteralPath $partial -Destination $Destination
                return $Destination
            }
            Move-Item -LiteralPath $partial -Destination ($partial + '.invalid-' + [guid]::NewGuid().ToString('N'))
        }
        if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
            throw 'Windows curl.exe is unavailable. Download the official package in your browser and pass its MSIX path to install-native.cmd.'
        }
        for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
            $offset = if (Test-Path -LiteralPath $partial) { (Get-Item -LiteralPath $partial).Length } else { 0 }
            Write-Host ('Downloading official desktop package: {0:N1} / {1:N1} MB; attempt {2}/{3}. Downloads resume after interruption.' -f ($offset / 1MB),($Size / 1MB),$attempt,$Attempts)
            # No curl --retry: it can rewind an interrupted transfer. Each invocation
            # obtains the current file length with -C -, including after a restart.
            # Allow slow but progressing downloads; bound connection/stall/total time.
            & curl.exe --fail --location --show-error --progress-bar --continue-at - --connect-timeout 30 --max-time 14400 --speed-time 120 --speed-limit 1024 --proto $protocol --proto-redir $protocol $Url --output $partial
            $downloadExit = $LASTEXITCODE
            if ($downloadExit -eq 0) {
                if (-not (Test-Package $partial)) {
                    Move-Item -LiteralPath $partial -Destination ($partial + '.invalid-' + [guid]::NewGuid().ToString('N'))
                    throw 'Downloaded package failed size/SHA256 verification. It was set aside; run the installer again or use the offline package.'
                }
                Move-Item -LiteralPath $partial -Destination $Destination
                return $Destination
            }
            if ($downloadExit -eq 33 -and $offset -gt 0) {
                # The server ignored Range. Never append a full response to a prefix.
                Move-Item -LiteralPath $partial -Destination ($partial + '.no-range-' + [guid]::NewGuid().ToString('N'))
                Write-Host 'This server cannot resume. Retrying a clean download; the old prefix was saved.'
            }
            if ($attempt -lt $Attempts) { Start-Sleep -Seconds $RetryDelay }
        }
        throw ('Download interrupted. Progress is saved in ' + $partial + '. Run the same installer to resume, or download the MSIX in your browser and pass its path to install-native.cmd.')
    } finally { if ($lock) { $lock.Dispose() } }
}
