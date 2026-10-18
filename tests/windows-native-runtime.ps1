param([Parameter(Mandatory=$true)][string]$AppDirectory)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force reports | Out-Null
$appDir = (Resolve-Path $AppDirectory).Path
$env:CODEX_HOME = Join-Path $env:RUNNER_TEMP 'tokenbots-codex-home'
New-Item -ItemType Directory -Force $env:CODEX_HOME | Out-Null
@'
model = "gpt-6.1-sol"
model_provider = "tokenbots_partner_20261016"
[model_providers.tokenbots_partner_20261016]
name = "TokenBots Partner Test"
base_url = "http://127.0.0.1:18791/v1"
wire_api = "responses"
experimental_bearer_token = "fixture-only-not-a-real-key"
requires_openai_auth = false
'@ | Set-Content -Encoding UTF8 (Join-Path $env:CODEX_HOME 'config.toml')
'{"OPENAI_API_KEY":"fixture-only-not-a-real-key"}' | Set-Content -Encoding UTF8 (Join-Path $env:CODEX_HOME 'auth.json')
'{"origin":"http://127.0.0.1:18791","key":"fixture-only-not-a-real-key","testOnlyLocalOrigin":true}' | Set-Content -Encoding ASCII (Join-Path $appDir 'resources\tokenbots-native.json')
$fixture = Start-Process python -ArgumentList 'tests/native_fixture_server.py' -PassThru
$app = Start-Process (Join-Path $appDir 'ChatGPT.exe') -ArgumentList '--force-renderer-accessibility' -WorkingDirectory $appDir -RedirectStandardOutput (Join-Path $PWD 'reports\native-stdout.txt') -RedirectStandardError (Join-Path $PWD 'reports\native-stderr.txt') -PassThru
Start-Sleep -Seconds 35
New-Item -ItemType Directory -Force reports | Out-Null
Add-Type -AssemblyName System.Drawing, System.Windows.Forms
$bounds = [Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object Drawing.Bitmap($bounds.Width,$bounds.Height)
$graphics = [Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location,[Drawing.Point]::Empty,$bounds.Size)
$bitmap.Save((Join-Path $PWD 'reports\native-desktop.png'))
$graphics.Dispose(); $bitmap.Dispose()
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$root = [Windows.Automation.AutomationElement]::RootElement
$all = $root.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
$names = @(); foreach ($element in $all) { try { if ($element.Current.Name) { $names += $element.Current.Name } } catch {} }
$names | Set-Content -Encoding UTF8 reports/native-ui.txt
Get-Process ChatGPT,Codex -ErrorAction SilentlyContinue | Select-Object ProcessName,Id,MainWindowTitle | Format-Table
if (-not (Get-Process ChatGPT -ErrorAction SilentlyContinue)) { throw 'Custom client did not stay running. See logs and screenshot.' }
# Launch alone is not menu acceptance; retain artifacts for the next UI step.
