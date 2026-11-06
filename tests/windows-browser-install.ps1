$ErrorActionPreference = 'Stop'
$app = Join-Path $env:LOCALAPPDATA 'TokenBots\Codex-native\ci-fixture'
$homePath = $null
try {
    New-Item -ItemType Directory -Force -Path (Join-Path $app 'resources\cua_node\bin') | Out-Null
    New-Item -ItemType File -Path (Join-Path $app '.tokenbots-custom-copy') | Out-Null
    Copy-Item (Get-Command node.exe).Source (Join-Path $app 'resources\cua_node\bin\node.exe')
    $fixtureKey = 'fixture-' + [guid]::NewGuid().ToString('N')
    @{origin='https://pilot.tokenbots.top';key=$fixtureKey} | ConvertTo-Json | Set-Content (Join-Path $app 'resources\tokenbots-native.json')
    $id = ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($fixtureKey)))).Replace('-','').Substring(0,16).ToLowerInvariant()
    $homePath = Join-Path $env:USERPROFILE ('.tokenbots-native-homes\' + $id)
    New-Item -ItemType Directory -Force -Path $homePath | Out-Null
    [IO.File]::WriteAllText((Join-Path $homePath 'config.toml'), 'model="gpt-6-astra"')
    & ./integrations/windows-codex/browser-tools/enable-browser.ps1 -AppDirectory $app
    & ./integrations/windows-codex/browser-tools/enable-browser.ps1 -AppDirectory $app
    & node ./tests/browser-tools-smoke.cjs $homePath
    if ($LASTEXITCODE -ne 0) { throw 'Real Edge acceptance failed' }
} finally {
    if ($homePath) { Remove-Item -LiteralPath $homePath -Recurse -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $app -Recurse -Force -ErrorAction SilentlyContinue
}
