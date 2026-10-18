# Exercise the real Windows inspector against a synthetic ASAR, without launching it.
$ErrorActionPreference = 'Stop'
$root = Join-Path ([IO.Path]::GetTempPath()) ('tokenbot-inspect-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $root 'resources') -Force | Out-Null
try {
    $inspector = Join-Path $root 'inspect-native-menu.ps1'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '..\integrations\windows-codex\inspect-native-menu.ps1') -Destination $inspector
    $exe = Join-Path $root 'Codex.exe'
    [IO.File]::WriteAllText($exe, 'Not executable; fixture metadata only.')
    $content = [Text.Encoding]::UTF8.GetBytes('profileDropdown.usage modelProviderName chatgpt ambientUsage')
    $entry = @{size=$content.Length; offset='0'; integrity=@{algorithm='SHA256'; hash='fixture'}}
    $tree = @{files=@{webview=@{files=@{assets=@{files=@{'profile-dropdown-fixture.js'=$entry}}}}}}
    $json = [Text.Encoding]::UTF8.GetBytes(($tree | ConvertTo-Json -Depth 15 -Compress))
    $paddedSize = [int]([Math]::Ceiling($json.Length / 4.0) * 4)
    $stream = New-Object IO.MemoryStream
    foreach ($n in @(4, (8 + $paddedSize), (4 + $paddedSize), $json.Length)) {
        $bytes = [BitConverter]::GetBytes([uint32]$n); $stream.Write($bytes, 0, 4)
    }
    $stream.Write($json, 0, $json.Length)
    while ($stream.Length -lt (16 + $paddedSize)) { $stream.WriteByte(0) }
    $stream.Write($content, 0, $content.Length)
    $asar = Join-Path $root 'resources\app.asar'
    [IO.File]::WriteAllBytes($asar, $stream.ToArray()); $stream.Dispose()
    $before = (Get-FileHash -LiteralPath $asar).Hash
    & $inspector -AppPath $exe
    $report = Get-Content -Raw -LiteralPath (Join-Path $root 'TokenBots-native-menu-report.json') | ConvertFrom-Json
    $app = @($report.applications | Where-Object { $_.path -like '*tokenbot-inspect-*' })[0]
    if (-not $app -or $app.archive.profileBundles.Count -ne 1) { throw 'Archive inspection failed.' }
    $marker = $app.archive.profileBundles[0]
    if (-not ($marker.usageLabel -and $marker.providerNameBranch -and $marker.chatgptAuthBranch -and $marker.ambientUsage)) { throw 'Expected menu evidence missing.' }
    if ((Get-FileHash -LiteralPath $asar).Hash -ne $before) { throw 'Application archive was modified.' }
    # A truncated archive must be reported, never rewritten or used as a patch target.
    [IO.File]::WriteAllText($asar, 'broken')
    & $inspector -AppPath $exe
    $report = Get-Content -Raw -LiteralPath (Join-Path $root 'TokenBots-native-menu-report.json') | ConvertFrom-Json
    if (-not ($report.issues -match 'archive could not be inspected')) { throw 'Corrupt archive was not reported.' }
    Write-Host 'Windows read-only installation inspection passed.'
} finally {
    # Only this test-created temporary fixture directory is removed.
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
