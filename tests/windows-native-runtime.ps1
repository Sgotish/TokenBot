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
New-Item -ItemType Directory -Force reports | Out-Null
Add-Type -AssemblyName System.Drawing, System.Windows.Forms
$bounds = [Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object Drawing.Bitmap($bounds.Width,$bounds.Height)
$graphics = [Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location,[Drawing.Point]::Empty,$bounds.Size)
$bitmap.Save((Join-Path $PWD 'reports\native-desktop.png'))
$graphics.Dispose(); $bitmap.Dispose()
$root = [Windows.Automation.AutomationElement]::RootElement
$all = $root.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
$names = @(); foreach ($element in $all) { try { if ($element.Current.Name) { $names += $element.Current.Name } } catch {} }
$names | Set-Content -Encoding UTF8 reports/native-ui.txt
Get-Process ChatGPT,Codex -ErrorAction SilentlyContinue | Select-Object ProcessName,Id,MainWindowTitle | Format-Table
if (-not (Get-Process ChatGPT -ErrorAction SilentlyContinue)) { throw 'Custom client did not stay running. See logs and screenshot.' }
if (-not $opened) { throw 'Native profile menu was not reachable.' }
if (-not ($names -match '94%')) { throw 'Real native menu did not show fixture remaining usage.' }
