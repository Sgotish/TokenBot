$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Force reports | Out-Null
# Start with the previous production UI adapter, preserving original backups.
$legacy=Join-Path $env:RUNNER_TEMP 'legacy-native'
New-Item -ItemType Directory -Path $legacy | Out-Null
Copy-Item integrations/windows-codex/native-menu/* $legacy
foreach ($name in @('component.js','backend.cjs')) {
    $content=git show "1fd0d4a:integrations/windows-codex/native-menu/$name"
    [IO.File]::WriteAllText((Join-Path $legacy $name),($content -join "`n"),(New-Object Text.UTF8Encoding($false)))
}
$output=@(& (Join-Path $legacy 'install.ps1') -PrepareOnly)
$app=$output[-1]
if (-not (Test-Path (Join-Path $app '.tokenbots-custom-copy'))) { throw 'No reviewed desktop installation' }
$env:CODEX_HOME=Join-Path $env:RUNNER_TEMP 'ota-menu-profile'
New-Item -ItemType Directory -Force $env:CODEX_HOME | Out-Null
$key='fixture-only-not-a-real-key'
'{"origin":"https://pilot.tokenbots.top","key":"fixture-only-not-a-real-key"}' | Set-Content -Encoding ASCII (Join-Path $app 'resources\tokenbots-native.json')
@'
model = "gpt-6.1-sol"
model_provider = "tokenbots_test"
[model_providers.tokenbots_test]
name = "TokenBots test"
base_url = "http://127.0.0.1:18791/v1"
wire_api = "responses"
experimental_bearer_token = "fixture-only-not-a-real-key"
requires_openai_auth = false
'@ | Set-Content -Encoding ASCII (Join-Path $env:CODEX_HOME 'config.toml')
'{"OPENAI_API_KEY":"fixture-only-not-a-real-key"}' | Set-Content -Encoding ASCII (Join-Path $env:CODEX_HOME 'auth.json')
'{"electron-persisted-atom-state":{"electron:onboarding-projectless-completed":true}}' | Set-Content -Encoding ASCII (Join-Path $env:CODEX_HOME '.codex-global-state.json')
$id=([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($key)))).Replace('-','').Substring(0,16).ToLowerInvariant()
$privateProfile=Join-Path $env:USERPROFILE ('.tokenbots-native-homes\'+$id)
New-Item -ItemType Directory -Force $privateProfile | Out-Null
Copy-Item (Join-Path $env:CODEX_HOME 'config.toml') (Join-Path $privateProfile 'config.toml')
$sentinel=Join-Path $privateProfile 'customer-project.txt'
[IO.File]::WriteAllText($sentinel,'Keep customer project')
[IO.File]::WriteAllText((Join-Path $app 'launch-tokenbots.ps1'),'Start-Process -FilePath (Join-Path $PSScriptRoot ''ChatGPT.exe'')')
$package=Join-Path $env:RUNNER_TEMP 'repair-package'
New-Item -ItemType Directory $package | Out-Null
foreach($name in @('enable-ota.ps1','ota-client.cjs','update-existing.ps1')) { Copy-Item (Join-Path 'integrations/windows-codex/native-menu' $name) $package }
Copy-Item tests/fixtures/menu-ota-2026110602.json (Join-Path $package 'ota-seed.json')
$env:OTA_TEST_PACKAGE=$package
node -e 'const fs=require("fs"),path=require("path"),o=require("./integrations/windows-codex/native-menu/ota-client.cjs"),r=o.verify(fs.readFileSync("tests/fixtures/menu-ota-2026110602.json"));fs.writeFileSync(path.join(process.env.OTA_TEST_PACKAGE,"browser-asset.json"),JSON.stringify(r.assets[0]));'
if($LASTEXITCODE-ne 0){throw 'Candidate verification failed'}
$asset=Get-Content -Raw (Join-Path $package 'browser-asset.json') | ConvertFrom-Json
curl.exe --fail --silent --show-error --max-time 120 $asset.url -o (Join-Path $package 'browser-tools.zip')
if($LASTEXITCODE-ne 0){throw 'Runtime download failed'}
# Actual repair entrypoint, no access to real customer credentials or inference.
& (Join-Path $package 'update-existing.ps1') -AppDirectory $app
if([IO.File]::ReadAllText($sentinel)-ne 'Keep customer project'){throw 'Customer project changed'}
$ota=Join-Path $app 'tokenbots-ota'
if((Get-Content -Raw (Join-Path $ota 'installed')).Trim()-ne '2026110602'){throw 'Wrong installed version'}
$exeHash=(Get-FileHash (Join-Path $app 'ChatGPT.exe')).Hash
& (Join-Path $package 'update-existing.ps1') -AppDirectory $app
if((Get-FileHash (Join-Path $app 'ChatGPT.exe')).Hash-ne $exeHash){throw 'Repeated repair changed installed binary'}
Write-Host 'PASS: real reviewed client overwritten, signed asset verified, repeat repair idempotent, customer project preserved'
# Serve the signed candidate only to this disposable runner. No production feed switch.
Copy-Item tests/fixtures/menu-ota-2026110602.json (Join-Path $env:RUNNER_TEMP 'candidate.json')
$server=Start-Process python -ArgumentList @('-m','http.server','18792','--bind','127.0.0.1','--directory',('"'+$env:RUNNER_TEMP+'"')) -PassThru
$updater=Join-Path $app 'ota-client.cjs'
$originalUpdater=[IO.File]::ReadAllText($updater)
[IO.File]::WriteAllText($updater,$originalUpdater.Replace('https://tokenbots.top/static/windows-ota-v1.json','http://127.0.0.1:18792/candidate.json'),(New-Object Text.UTF8Encoding($false)))
'{"origin":"http://127.0.0.1:18791","key":"fixture-only-not-a-real-key","testOnlyLocalOrigin":true}' | Set-Content -Encoding ASCII (Join-Path $app 'resources\tokenbots-native.json')
$fixture=Start-Process python -ArgumentList 'tests/native_fixture_server.py' -PassThru
Start-Process (Join-Path $app 'ChatGPT.exe') -ArgumentList '--force-renderer-accessibility' -WorkingDirectory $app | Out-Null
Start-Sleep -Seconds 30
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Drawing,System.Windows.Forms
Add-Type @'
using System.Runtime.InteropServices;
public class OtaMouse {
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,System.UIntPtr e);
}
'@
function Invoke-Visible([string]$name) {
 $condition=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty,$name)
 $all=[Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Descendants,$condition)
 foreach($el in $all){if($el.Current.IsOffscreen-or -not $el.Current.IsEnabled){continue};$rect=$el.Current.BoundingRectangle
 if($rect.Width-gt 0){[OtaMouse]::SetCursorPos([int]($rect.X+$rect.Width/2),[int]($rect.Y+$rect.Height/2))|Out-Null;[OtaMouse]::mouse_event(2,0,0,0,[UIntPtr]::Zero);[OtaMouse]::mouse_event(4,0,0,0,[UIntPtr]::Zero);return $true}}
 return $false
}
function Evidence([string]$label){
 $all=[Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
 $names=@();foreach($el in $all){try{if($el.Current.Name){$names+=$el.Current.Name}}catch{}}
 $names|Set-Content -Encoding UTF8 ('reports/ota-menu-'+$label+'.txt')
 $bounds=[Windows.Forms.Screen]::PrimaryScreen.Bounds;$bmp=New-Object Drawing.Bitmap($bounds.Width,$bounds.Height);$g=[Drawing.Graphics]::FromImage($bmp)
 $g.CopyFromScreen($bounds.Location,[Drawing.Point]::Empty,$bounds.Size);$bmp.Save((Join-Path $PWD ('reports/ota-menu-'+$label+'.png')));$g.Dispose();$bmp.Dispose()
 return $names
}
try{
 if(Invoke-Visible 'Engineering'){Start-Sleep 1;$null=Invoke-Visible 'Continue';Start-Sleep 8}
 if(-not(Invoke-Visible 'Open profile menu')){$null=Evidence 'failed-open';throw 'Cannot open actual desktop profile menu'}
 Start-Sleep 2
 $check=-join([char[]](0x68c0,0x67e5,0x66f4,0x65b0))
 if(-not(Invoke-Visible $check)){$null=Evidence 'failed-check';throw 'Native Check updates button unavailable'}
 Start-Sleep 5
 $names=Evidence 'latest'
 $latest=-join([char[]](0x5df2,0x7ecf,0x68c0,0x67e5,0x8fc7))
 if(-not($names-match $latest)){throw 'Native latest-version success not displayed'}
 if(-not($names-match 'Last update')){throw 'Native install timestamp missing'}
 Stop-Process -Id $server.Id -Force
 $null=Invoke-Visible $check;Start-Sleep 5
 $names=Evidence 'offline'
 $failed=-join([char[]](0x68c0,0x67e5,0x5931,0x8d25))
 if(-not($names-match $failed)){throw 'Offline check did not show failure'}
 Write-Host 'PASS: actual Windows menu, signed-candidate latest check, persistent timestamps, offline error; no model requests'
}finally{
 Get-Process ChatGPT -ErrorAction SilentlyContinue|Where-Object{$_.Path-eq(Join-Path $app 'ChatGPT.exe')}|Stop-Process -Force
 Stop-Process -Id $fixture.Id -Force -ErrorAction SilentlyContinue
 Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
 [IO.File]::WriteAllText($updater,$originalUpdater,(New-Object Text.UTF8Encoding($false)))
}
