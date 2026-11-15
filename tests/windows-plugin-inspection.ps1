$ErrorActionPreference='Stop'
# The preceding runtime test leaves the real app open. Inspect the native
# plugin surface with the synthetic API-key profile; do not claim OAuth access.
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Drawing,System.Windows.Forms
[Windows.Forms.SendKeys]::SendWait('{ESC}{ESC}')
Start-Sleep -Seconds 2
function Snapshot([string]$label){
 $root=[Windows.Automation.AutomationElement]::RootElement
 $all=$root.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
 $names=@();foreach($el in $all){try{if($el.Current.Name){$names+=$el.Current.Name}}catch{}}
 $names|Set-Content -Encoding UTF8 ('reports/plugin-'+$label+'.txt')
 $bounds=[Windows.Forms.Screen]::PrimaryScreen.Bounds;$bmp=New-Object Drawing.Bitmap($bounds.Width,$bounds.Height);$g=[Drawing.Graphics]::FromImage($bmp)
 $g.CopyFromScreen($bounds.Location,[Drawing.Point]::Empty,$bounds.Size);$bmp.Save((Join-Path $PWD ('reports/plugin-'+$label+'.png')));$g.Dispose();$bmp.Dispose()
 return $all
}
$all=Snapshot 'before'
$opened=$false
foreach($name in @('Plugins','Skills','插件','技能')){
 foreach($el in $all){
  if($el.Current.Name-ne $name -or $el.Current.IsOffscreen -or -not $el.Current.IsEnabled){continue}
  $pattern=$null
  if($el.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)){$pattern.Invoke();$opened=$true;break}
  if($el.TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern)){$pattern.Select();$opened=$true;break}
  # The official navigation is a link without InvokePattern on this build.
  # Use its observed visible bounds, as in the preceding native runtime test.
  $rect=$el.Current.BoundingRectangle
  if($rect.Width -gt 0 -and $rect.Height -gt 0){
   [NativeTestMouse]::SetCursorPos([int]($rect.X+$rect.Width/2),[int]($rect.Y+$rect.Height/2))|Out-Null
   [NativeTestMouse]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
   [NativeTestMouse]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
   $opened=$true;break
  }
 }
 if($opened){break}
}
Start-Sleep -Seconds 12
$null=Snapshot 'directory'
@{directoryEntryInvoked=$opened;authMode='synthetic TokenBots API-key fixture';githubOAuthVerified=$false;catalogEntitlementsVerified=$false}|ConvertTo-Json|Set-Content reports/plugin-acceptance.json
if(-not $opened){throw 'Plugin directory entry was not reachable in native desktop'}
Write-Host 'PASS: native plugin entry opened; external account authorizations were not tested'
