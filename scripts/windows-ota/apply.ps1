param([Parameter(Mandatory=$true)][string]$AppDirectory)
$ErrorActionPreference = 'Stop'
# enable-images writes config.toml atomically. Restore the previous helper if registration fails.
$target = Join-Path $AppDirectory 'resources\tokenbots-images.cjs'
$backup = $target + '.ota-' + [guid]::NewGuid().ToString('N')
$existed = Test-Path -LiteralPath $target
if ($existed) { Copy-Item -LiteralPath $target -Destination $backup }
try {
    & (Join-Path $PSScriptRoot 'enable-images.ps1') -AppDirectory $AppDirectory
} catch {
    if ($existed) { Copy-Item -LiteralPath $backup -Destination $target -Force }
    elseif (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target }
    throw
} finally {
    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup }
}
