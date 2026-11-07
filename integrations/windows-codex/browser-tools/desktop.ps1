$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
function Trace-Stage($stage) {if ($env:TOKENBOTS_DESKTOP_DEBUG -eq '1'){[Console]::Error.WriteLine($stage)}}
try {
Trace-Stage 'read-input'
$a = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:TOKENBOTS_DESKTOP_REQUEST)) | ConvertFrom-Json
$env:TOKENBOTS_DESKTOP_REQUEST = $null
Trace-Stage 'assemblies'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Trace-Stage 'compile-native'
Add-Type @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class TBDesktop {
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint flags,uint dx,uint dy,int data,UIntPtr extra);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int cmd);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h,StringBuilder s,int count);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h,out Rect r);
 public delegate bool EnumProc(IntPtr h,IntPtr p);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc c,IntPtr p);
 [StructLayout(LayoutKind.Sequential)] public struct Rect{public int left,top,right,bottom;}
 public static object[] Windows(){var r=new List<object>();EnumWindows((h,p)=>{var s=new StringBuilder(512);GetWindowText(h,s,512);Rect b;if(IsWindowVisible(h)&&s.Length>0&&GetWindowRect(h,out b))r.Add(new {handle=h.ToInt64(),title=s.ToString(),left=b.left,top=b.top,width=b.right-b.left,height=b.bottom-b.top});return true;},IntPtr.Zero);return r.ToArray();}
 [StructLayout(LayoutKind.Sequential)] public struct INPUT{public uint type;public UNION u;}
 [StructLayout(LayoutKind.Explicit)] public struct UNION{[FieldOffset(0)]public KEYBDINPUT k;[FieldOffset(0)]public MOUSEINPUT m;}
 [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT{public ushort vk,scan;public uint flags,time;public UIntPtr extra;}
 [StructLayout(LayoutKind.Sequential)] public struct MOUSEINPUT{public int dx,dy;public uint data,flags,time;public UIntPtr extra;}
 [DllImport("user32.dll",SetLastError=true)] public static extern uint SendInput(uint n,INPUT[] a,int size);
 public static void Type(string s){foreach(char c in s){var a=new INPUT[2];a[0].type=1;a[0].u.k.scan=c;a[0].u.k.flags=4;a[1]=a[0];a[1].u.k.flags=6;if(SendInput(2,a,Marshal.SizeOf(typeof(INPUT)))!=2)throw new Exception("Windows rejected input; check the foreground window and elevation");}}
}
'@
Trace-Stage 'native-ready'
[void][TBDesktop]::SetProcessDPIAware()
if (-not [Environment]::UserInteractive) { throw 'Windows desktop is not interactive. Unlock the user session.' }
$bounds = [Windows.Forms.SystemInformation]::VirtualScreen
switch ($a.action) {
 'observe' {
  Trace-Stage 'capture'
  $bmp = New-Object Drawing.Bitmap($bounds.Width,$bounds.Height)
  $g = [Drawing.Graphics]::FromImage($bmp)
  try { $g.CopyFromScreen($bounds.Left,$bounds.Top,0,0,$bounds.Size) } finally { $g.Dispose() }
  $scale = [Math]::Min(1.0,1600.0/$bounds.Width)
  $small = New-Object Drawing.Bitmap($bmp, (New-Object Drawing.Size([int]($bounds.Width*$scale),[int]($bounds.Height*$scale))))
  $stream = New-Object IO.MemoryStream
  try {$small.Save($stream,[Drawing.Imaging.ImageFormat]::Png);$png=[Convert]::ToBase64String($stream.ToArray())} finally {$stream.Dispose();$small.Dispose();$bmp.Dispose()}
  Trace-Stage 'enumerate'
  @{windows=@([TBDesktop]::Windows());foreground=[TBDesktop]::GetForegroundWindow().ToInt64();screen=@{left=$bounds.Left;top=$bounds.Top;width=$bounds.Width;height=$bounds.Height;imageScale=$scale};png=$png} | ConvertTo-Json -Depth 8 -Compress
 }
 'focus' {
  $match=@([TBDesktop]::Windows() | Where-Object {$_.handle -eq $a.window})
  if ($match.Count -ne 1) {throw 'Window is no longer available. Observe again.'}
  $h=[IntPtr][long]$a.window;[void][TBDesktop]::ShowWindow($h,9);[void][TBDesktop]::SetForegroundWindow($h)
  if ([TBDesktop]::GetForegroundWindow() -ne $h) {throw 'Windows prevented foreground activation. Select the target window.'}
  '{"ok":true}'
 }
 'click' {
  if ($null -eq $a.x -or $null -eq $a.y -or -not $bounds.Contains([int]$a.x,[int]$a.y)) {throw 'Coordinates outside desktop'}
  [void][TBDesktop]::SetCursorPos($a.x,$a.y)
  $down=2;$up=4;if ($a.button -eq 'right'){$down=8;$up=16}
  $count=1;if($a.button -eq 'double'){$count=2}
  for($i=0;$i -lt $count;$i++){[TBDesktop]::mouse_event($down,0,0,0,[UIntPtr]::Zero);[TBDesktop]::mouse_event($up,0,0,0,[UIntPtr]::Zero);if($count -eq 2){Start-Sleep -Milliseconds 70}}
  '{"ok":true}'
 }
 'type' {if ($null -eq $a.text){throw 'Text required'};[TBDesktop]::Type([string]$a.text);'{"ok":true}'}
 'key' {
  $keys=@{'ENTER'='{ENTER}';'TAB'='{TAB}';'ESC'='{ESC}';'BACKSPACE'='{BACKSPACE}';'DELETE'='{DELETE}';'CTRL+A'='^a';'CTRL+C'='^c';'CTRL+V'='^v';'CTRL+L'='^l';'CTRL+S'='^s';'ALT+F4'='%{F4}';'LEFT'='{LEFT}';'RIGHT'='{RIGHT}';'UP'='{UP}';'DOWN'='{DOWN}';'HOME'='{HOME}';'END'='{END}';'PAGEUP'='{PGUP}';'PAGEDOWN'='{PGDN}'}
  if (-not $keys.ContainsKey([string]$a.key)){throw 'Unsupported key'}
  [Windows.Forms.SendKeys]::SendWait($keys[[string]$a.key]);'{"ok":true}'
 }
 'scroll' {if($null -eq $a.amount -or [Math]::Abs([int]$a.amount) -gt 20){throw 'Invalid scroll amount'};[TBDesktop]::mouse_event(2048,0,0,([int]$a.amount*120),[UIntPtr]::Zero);'{"ok":true}'}
 default {throw 'Unknown desktop action'}
}
} catch { @{error=$_.Exception.Message} | ConvertTo-Json -Compress; exit 1 }
