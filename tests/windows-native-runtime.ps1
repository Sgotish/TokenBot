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
name = "TokenBots partner"
base_url = "http://127.0.0.1:18791/v1"
wire_api = "responses"
experimental_bearer_token = "fixture-only-not-a-real-key"
requires_openai_auth = false
'@ | Set-Content -Encoding ASCII (Join-Path $env:CODEX_HOME 'config.toml')
'{"OPENAI_API_KEY":"fixture-only-not-a-real-key"}' | Set-Content -Encoding ASCII (Join-Path $env:CODEX_HOME 'auth.json')
# Model an existing desktop user in this disposable test profile.
'{"electron-persisted-atom-state":{"electron:onboarding-projectless-completed":true}}' | Set-Content -Encoding ASCII (Join-Path $env:CODEX_HOME '.codex-global-state.json')
'{"origin":"http://127.0.0.1:18791","key":"fixture-only-not-a-real-key","testOnlyLocalOrigin":true}' | Set-Content -Encoding ASCII (Join-Path $appDir 'resources\tokenbots-native.json')
$fixture = Start-Process python -ArgumentList 'tests/native_fixture_server.py' -PassThru
$app = Start-Process (Join-Path $appDir 'ChatGPT.exe') -ArgumentList '--force-renderer-accessibility' -WorkingDirectory $appDir -RedirectStandardOutput (Join-Path $PWD 'reports\native-stdout.txt') -RedirectStandardError (Join-Path $PWD 'reports\native-stderr.txt') -PassThru
Start-Sleep -Seconds 35
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
Add-Type @'
using System.Runtime.InteropServices;
public class NativeTestMouse {
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint flags,uint x,uint y,uint data,System.UIntPtr extra);
}
'@
function Invoke-Visible([string]$name) {
    $condition = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty, $name)
    $elements = [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Descendants,$condition)
    foreach ($element in $elements) {
        if ($element.Current.IsOffscreen -or -not $element.Current.IsEnabled) { continue }
        $pattern = $null
        if ($element.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)) { $pattern.Invoke(); return $true }
        if ($element.TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern)) { $pattern.Select(); return $true }
        if ($element.TryGetCurrentPattern([Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)) { $pattern.Toggle(); return $true }
        $rect = $element.Current.BoundingRectangle
        if ($rect.Width -gt 0 -and $rect.Height -gt 0) {
            [NativeTestMouse]::SetCursorPos([int]($rect.X+$rect.Width/2),[int]($rect.Y+$rect.Height/2)) | Out-Null
            [NativeTestMouse]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
            [NativeTestMouse]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
            return $true
        }
    }
    return $false
}
if (Invoke-Visible 'Engineering') {
    Start-Sleep -Seconds 1
    $null = Invoke-Visible 'Continue'
    Start-Sleep -Seconds 8
}
$opened = Invoke-Visible 'Open profile menu'
if ($opened) { Start-Sleep -Seconds 5 }
Add-Type -AssemblyName System.Drawing, System.Windows.Forms
function Save-NativeEvidence([string]$suffix) {
$bounds = [Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object Drawing.Bitmap($bounds.Width,$bounds.Height)
$graphics = [Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location,[Drawing.Point]::Empty,$bounds.Size)
$bitmap.Save((Join-Path $PWD ('reports\native-' + $suffix + '.png')))
$graphics.Dispose(); $bitmap.Dispose()
$root = [Windows.Automation.AutomationElement]::RootElement
$all = $root.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
$names = @(); foreach ($element in $all) { try { if ($element.Current.Name) { $names += $element.Current.Name } } catch {} }
$names | Set-Content -Encoding UTF8 ('reports/native-' + $suffix + '-ui.txt')
return $names
}
$names = Save-NativeEvidence 'menu'
Get-Process ChatGPT,Codex -ErrorAction SilentlyContinue | Select-Object ProcessName,Id,MainWindowTitle | Format-Table
if (-not (Get-Process ChatGPT -ErrorAction SilentlyContinue)) { throw 'Custom client did not stay running. See logs and screenshot.' }
if (-not $opened) { throw 'Native profile menu was not reachable.' }
if (-not ($names -match '94%')) { throw 'Real native menu did not show fixture remaining usage.' }

$usageLabel = -join ([char[]](0x4f7f,0x7528,0x60c5,0x51b5))
$usageName = $names | Where-Object { $_.StartsWith($usageLabel) } | Select-Object -First 1
if (-not $usageName -or -not (Invoke-Visible $usageName)) { throw 'Cannot expand native usage details.' }
Start-Sleep -Seconds 2
$details = Save-NativeEvidence 'details'
if (-not ($details -match '97%')) { throw 'Native usage windows did not expand.' }
if (-not (Invoke-Visible 'Pro')) { throw 'Native Pro selector unavailable.' }
Start-Sleep -Seconds 3
$switched = Save-NativeEvidence 'pro'
if (-not ($switched -match 'Pro 81%')) { throw 'Native Pro selection did not update remaining usage.' }

# A new upstream value must reach the already-open menu without reopening it.
Start-Sleep -Seconds 35
$refreshed = Save-NativeEvidence 'auto-refresh'
if (-not ($refreshed -match 'Pro 80%')) { throw 'Open native menu did not refresh changed quota automatically.' }

# The original model/effort controls must remain available in the custom client.
$null = Invoke-Visible 'Open profile menu'
Start-Sleep -Seconds 1
$composer = Save-NativeEvidence 'composer'

$effortButton = $composer | Where-Object { $_ -eq 'Select effort' -or $_ -match '^6\.1 Sol (Light|Standard|Extended|Heavy|Max|Ultra)$' } | Select-Object -First 1
if (-not $effortButton -or -not (Invoke-Visible $effortButton)) { throw 'Native effort control unavailable.' }
Start-Sleep -Seconds 2
$picker = Save-NativeEvidence 'model-control'
if (-not (Invoke-Visible 'Select model')) { throw 'Native model selector unavailable.' }
Start-Sleep -Seconds 2
$modelNames = Save-NativeEvidence 'models'
foreach ($model in @('6.1','Astra','6 Sol','6 Luna','5.6 Sol','Terra','5.6 Luna')) {
  if (-not ($modelNames | Where-Object { $_.Replace('-',' ').Contains($model) })) { throw ('Model picker missing ' + $model) }
}
$astra = $modelNames | Where-Object { $_ -match 'Astra' } | Select-Object -First 1
if (-not (Invoke-Visible $astra)) { throw 'Cannot select Astra from the native menu.' }
Start-Sleep -Seconds 2
$astraNames = Save-NativeEvidence 'astra-selected'
# This client exposes its custom power control by its accessible value name,
# not UIA RangeValuePattern. The live status describes the selection; the
# focusable menu item is named Power. Use its documented Left/Right interaction.
$powerName = $astraNames | Where-Object { $_ -match '^6 Astra .+, 1 of [0-9]+\.$' } | Select-Object -First 1
if (-not $powerName) { throw 'Native Astra power control unavailable.' }
$stepCount = [int]([regex]::Match($powerName, 'of ([0-9]+)').Groups[1].Value)
$condition = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty, 'Power')
$power = [Windows.Automation.AutomationElement]::RootElement.FindFirst([Windows.Automation.TreeScope]::Descendants,$condition)
$power.SetFocus()
for ($step=1; $step -lt $stepCount; $step++) { [Windows.Forms.SendKeys]::SendWait('{RIGHT}'); Start-Sleep -Milliseconds 250 }
Start-Sleep -Seconds 2
$effortNames = Save-NativeEvidence 'astra-max-effort'
if (-not ($effortNames | Where-Object { $_ -match ('^6 Astra .+, ' + $stepCount + ' of ' + $stepCount + '\.$') })) {
  throw 'Native Astra reasoning control did not reach its highest supported level.'
}
