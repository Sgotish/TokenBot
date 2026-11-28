$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Force reports | Out-Null
$legacy=Join-Path $env:RUNNER_TEMP 'legacy-official-upgrade'
New-Item -ItemType Directory -Path $legacy | Out-Null
Copy-Item integrations/windows-codex/native-menu/* $legacy
$oldInstaller=git show '7112886:integrations/windows-codex/native-menu/install.ps1'
[IO.File]::WriteAllText((Join-Path $legacy 'install.ps1'),($oldInstaller -join "`n"),(New-Object Text.UTF8Encoding($false)))
$result=@(& (Join-Path $legacy 'install.ps1') -PrepareOnly)
$old=$result[-1]
$key='synthetic-official-upgrade-not-a-real-key'
$access=@{origin='https://pilot.tokenbots.top';key=$key}|ConvertTo-Json -Compress
[IO.File]::WriteAllText((Join-Path $old 'resources\tokenbots-native.json'),$access)
$id=([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($key)))).Replace('-','').Substring(0,16).ToLowerInvariant()
$profile=Join-Path $env:USERPROFILE ('.tokenbots-native-homes\'+$id)
New-Item -ItemType Directory -Force $profile | Out-Null
$env:CODEX_HOME=$profile
@'
model = "gpt-6.1-sol"
model_provider = "tokenbots_partner_20261016"
[model_providers.tokenbots_partner_20261016]
name = "TokenBots synthetic test"
base_url = "https://pilot.tokenbots.top/v1"
experimental_bearer_token = "synthetic-official-upgrade-not-a-real-key"
requires_openai_auth = false
wire_api = "responses"
'@ | Set-Content -Encoding ASCII (Join-Path $profile 'config.toml')
[IO.File]::WriteAllText((Join-Path $profile 'auth.json'),'{"OPENAI_API_KEY":"synthetic-official-upgrade-not-a-real-key"}')
$sentinel=Join-Path $profile 'sessions\2026\11\15\existing-chat.jsonl'
New-Item -ItemType Directory -Force (Split-Path $sentinel -Parent) | Out-Null
[IO.File]::WriteAllText($sentinel,'{"synthetic":"keep this existing conversation"}')
$sentinelHash=(Get-FileHash $sentinel).Hash
$authHash=(Get-FileHash (Join-Path $profile 'auth.json')).Hash
$oldHash=(Get-FileHash (Join-Path $old 'ChatGPT.exe')).Hash
$base=Join-Path $env:LOCALAPPDATA 'TokenBots\Codex-native'
[IO.File]::WriteAllText((Join-Path $base 'current-copy.txt'),$old)
$launcher="`$env:CODEX_HOME = '$($profile.Replace("'","''"))'`r`nStart-Process -FilePath (Join-Path `$PSScriptRoot 'ChatGPT.exe') -WorkingDirectory `$PSScriptRoot -ArgumentList ('--user-data-dir=`"' + (Join-Path `$env:CODEX_HOME 'desktop-data') + '`"')"
[IO.File]::WriteAllText((Join-Path $old 'launch-tokenbots.ps1'),$launcher)
$release=Join-Path $env:RUNNER_TEMP 'base-release'
New-Item -ItemType Directory -Path $release | Out-Null
Copy-Item integrations/windows-codex/native-menu/* $release
Copy-Item scripts/windows-ota/apply.ps1 $release
Copy-Item integrations/model-catalog/codex-models.json $release
node tests/ota-candidate-asset.cjs tests/fixtures/menu-ota-2026110801.json (Join-Path $release 'browser-asset.json')
if($LASTEXITCODE-ne 0){throw 'Signed browser fixture invalid'}
$browser=Get-Content -Raw (Join-Path $release 'browser-asset.json')|ConvertFrom-Json
$cache=Join-Path $old 'tokenbots-ota\assets'
New-Item -ItemType Directory -Force $cache | Out-Null
curl.exe --fail --silent --show-error --max-time 240 $browser.url -o (Join-Path $cache ($browser.sha256+'.zip'))
if($LASTEXITCODE-ne 0){throw 'Browser download failed'}
$descriptor=Get-Content -Raw (Join-Path $release 'desktop-release.json')|ConvertFrom-Json
$desktop=$descriptor.architectures.x64
# Exercise the legacy bootstrap without allowing a base change or claiming an
# installed release. The next launch uses the newly installed transport.
$env:TOKENBOTS_OTA_PROTOCOL=$null
try{& (Join-Path $release 'apply.ps1') -AppDirectory $old;throw 'Legacy updater unexpectedly applied desktop'}catch{if($_ -notmatch 'updater was upgraded'){throw}}
if((Get-FileHash (Join-Path $old 'ChatGPT.exe')).Hash-ne $oldHash){throw 'Bootstrap changed desktop'}
if(-not ([IO.File]::ReadAllText((Join-Path $old 'launch-tokenbots.ps1')).Contains('# TokenBots handover entry v2'))){throw 'Launcher bootstrap missing'}
curl.exe --fail --location --silent --show-error --max-time 360 $desktop.url -o (Join-Path $cache ($desktop.sha256+'.msix'))
if($LASTEXITCODE-ne 0){throw 'Desktop download failed'}
$env:TOKENBOTS_OTA_PROTOCOL='2';$env:TOKENBOTS_OTA_VERSION=[string]$descriptor.version
& (Join-Path $release 'apply.ps1') -AppDirectory $old
$next=[IO.File]::ReadAllText((Join-Path $base 'current-copy.txt')).Trim()
if($next-eq $old){throw 'Desktop pointer was not switched'}
if((Get-Content -Raw (Join-Path $next 'resources\owl-app.ini')) -notmatch 'AppVersion=26\.1111\.21308'){throw 'Unexpected new desktop version'}
if((Get-FileHash $sentinel).Hash-ne $sentinelHash -or (Get-FileHash (Join-Path $profile 'auth.json')).Hash-ne $authHash){throw 'Conversation or authentication changed'}
if((Get-FileHash (Join-Path $old 'ChatGPT.exe')).Hash-ne $oldHash){throw 'Rollback desktop changed'}
$cfg=Get-Content -Raw (Join-Path $profile 'config.toml')
foreach($expected in @('requires_openai_auth = false','synthetic-official-upgrade-not-a-real-key','model = "gpt-6.1-sol"')){if(-not $cfg.Contains($expected)){throw 'Existing model or login configuration changed'}}
$again=@(& (Join-Path $release 'upgrade-desktop.ps1') -AppDirectory $next -Descriptor (Join-Path $release 'desktop-release.json'))
if($again[-1]-ne $next){throw 'Repeated base upgrade is not idempotent'}
# Verify an existing desktop shortcut delegates to the committed new launcher.
$nextLauncher=Join-Path $next 'launch-tokenbots.ps1';$realLauncher=[IO.File]::ReadAllText($nextLauncher)
try{
 [IO.File]::WriteAllText($nextLauncher,"[IO.File]::WriteAllText('$($env:RUNNER_TEMP.Replace("'","''"))\handover-reached.txt','same-profile')")
 & (Join-Path $old 'launch-tokenbots.ps1')
 if(-not(Test-Path (Join-Path $env:RUNNER_TEMP 'handover-reached.txt'))){throw 'Existing shortcut did not reach new application'}
}finally{[IO.File]::WriteAllText($nextLauncher,$realLauncher)}
@{oldVersion='26.1016.51333';newVersion=$desktop.applicationVersion;signatureValidated=$true;historySentinelPreserved=$true;authPreserved=$true;oldBinaryPreserved=$true;idempotent=$true;oldShortcutRedirected=$true;customerDeviceTested=$false}|ConvertTo-Json|Set-Content reports/official-upgrade.json
"TB_UPGRADED_APP=$next"|Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
Write-Host 'PASS: signed official desktop upgraded, TokenBots login and existing profile preserved, rollback retained, old shortcut redirected'
