$ErrorActionPreference = 'Stop'
$app = Join-Path $env:LOCALAPPDATA ('TokenBots\Codex-native\ota-fixture-' + [guid]::NewGuid().ToString('N'))
$profile = $null
try {
    New-Item -ItemType Directory -Force -Path (Join-Path $app 'resources\cua_node\bin') | Out-Null
    New-Item -ItemType File -Path (Join-Path $app '.tokenbots-custom-copy') | Out-Null
    $node = Join-Path $app 'resources\cua_node\bin\node.exe'
    Copy-Item (Get-Command node.exe).Source $node
    $key = 'fixture-' + [guid]::NewGuid().ToString('N')
    @{origin='https://pilot.tokenbots.top';key=$key} | ConvertTo-Json | Set-Content (Join-Path $app 'resources\tokenbots-native.json')
    $id = ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($key)))).Replace('-','').Substring(0,16).ToLowerInvariant()
    $profile = Join-Path $env:USERPROFILE ('.tokenbots-native-homes\' + $id)
    New-Item -ItemType Directory -Path $profile | Out-Null
    $config = Join-Path $profile 'config.toml'
    $original = "model=`"gpt-6-astra`"`nmodel_reasoning_effort=`"high`"`n"
    [IO.File]::WriteAllText($config,$original)
    $imageFile = Join-Path $app 'resources\tokenbots-images.cjs'
    [IO.File]::WriteAllText($imageFile,'previous image helper')
    $updater = Join-Path $app 'ota-client.cjs'
    Copy-Item ./tests/fixtures/ota-client-v1.cjs $updater
    $release = (Resolve-Path ./tests/fixtures/browser-ota-2026110601.json).Path
    & $node $updater stage $app $release
    if ($LASTEXITCODE -ne 0) { throw 'Old updater rejected compatible signed release' }
    & $node $updater apply $app
    if ($LASTEXITCODE -eq 0) { throw 'Old updater marked missing asset installed' }
    if ([IO.File]::ReadAllText($config) -ne $original) { throw 'Bootstrap changed customer config' }
    $ota = Join-Path $app 'tokenbots-ota'
    if (Test-Path (Join-Path $ota 'installed')) { throw 'Failed bootstrap was marked installed' }
    & $node -e "if(typeof require(process.argv[1]).prepare!=='function')process.exit(1)" $updater
    if ($LASTEXITCODE -ne 0) {
        $diagnostic = Join-Path $app 'bootstrap-diagnostic'
        New-Item -ItemType Directory -Path $diagnostic | Out-Null
        & $node ./tests/windows-ota-prepare.cjs extract $release $diagnostic
        & (Join-Path $diagnostic 'apply.ps1') -AppDirectory $app
        throw 'Transport bootstrap did not install the new updater'
    }
    Write-Host 'PASS: legacy updater bootstrapped transport, preserved original client config'
    # Real HTTPS asset download using the signed candidate before production feed changes.
    & $node ./tests/windows-ota-prepare.cjs $updater $ota $release
    if ($LASTEXITCODE -ne 0) { throw 'Signed HTTPS asset preparation failed' }
    # Deliberate second-step failure proves browser registration is also rolled back.
    $broken = Join-Path $app 'rollback-fixture'
    New-Item -ItemType Directory -Path $broken | Out-Null
    & $node ./tests/windows-ota-prepare.cjs extract $release $broken
    Set-Content -LiteralPath (Join-Path $broken 'enable-images.ps1') -Value "throw 'intentional rollback test'"
    $failed = $false
    try { & (Join-Path $broken 'apply.ps1') -AppDirectory $app } catch { $failed=$true }
    if (-not $failed) { throw 'Rollback test did not fail' }
    if ([IO.File]::ReadAllText($config) -ne $original -or [IO.File]::ReadAllText($imageFile) -ne 'previous image helper') { throw 'Rollback failed to restore previous files' }
    if (Test-Path (Join-Path $profile 'skills\tokenbots-browser-check')) { throw 'Rollback left a new skill installed' }
    Write-Host 'PASS: injected failure restored config, image helper and skills'
    & $node $updater apply $app
    if ($LASTEXITCODE -ne 0) { throw 'OTA apply failed' }
    if ((Get-Content -Raw (Join-Path $ota 'installed')).Trim() -ne '2026110601') { throw 'Installed version mismatch' }
    $hash = (Get-FileHash $config).Hash
    & $node $updater apply $app
    if ($LASTEXITCODE -ne 0 -or (Get-FileHash $config).Hash -ne $hash) { throw 'Repeated startup changed config' }
    & node ./tests/browser-tools-smoke.cjs $profile --installed
    if ($LASTEXITCODE -ne 0) { throw 'OTA-installed browser failed real Edge click' }
    Write-Host 'PASS: signed OTA installed, restart idempotent, actual Edge tool verified'
} finally {
    if ($profile) { Remove-Item -LiteralPath $profile -Recurse -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $app -Recurse -Force -ErrorAction SilentlyContinue
}
