param([Parameter(Mandatory=$true)][string]$AppDirectory)
$ErrorActionPreference = 'Stop'
$appDir = (Resolve-Path -LiteralPath $AppDirectory).Path
if (-not (Test-Path -LiteralPath (Join-Path $appDir '.tokenbots-custom-copy'))) { throw 'Only a designated TokenBots copy can be patched.' }
if ($appDir -match '[\\/]WindowsApps[\\/]') { throw 'Cannot patch an installed Store package.' }
$asar = Join-Path $appDir 'resources\app.asar'
$backup = $asar + '.tokenbots-original'
if (Test-Path -LiteralPath $backup) { throw 'Already patched or backup exists; use a fresh copy.' }
$stream = [IO.File]::OpenRead($asar)
$patches = @{}
try {
    $reader = New-Object IO.BinaryReader($stream)
    $null = $reader.ReadUInt32(); $headerSize = $reader.ReadUInt32(); $null = $reader.ReadUInt32(); $jsonSize = $reader.ReadUInt32()
    if ($jsonSize -gt 33554432 -or $headerSize -lt ($jsonSize + 8)) { throw 'Invalid ASAR header.' }
    $tree = [Text.Encoding]::UTF8.GetString($reader.ReadBytes($jsonSize)) | ConvertFrom-Json
    $dataStart = 8L + $headerSize
    function Read-Entry($entry) {
        if ($entry.unpacked -or $entry.size -gt 33554432) { throw 'Unexpected archive entry.' }
        $stream.Position = $dataStart + [long]$entry.offset
        return [Text.Encoding]::UTF8.GetString($reader.ReadBytes([int]$entry.size))
    }
    $package = (Read-Entry $tree.files.'package.json') | ConvertFrom-Json
    if ($package.version -ne '26.1013.40934') { throw 'This release needs adaptation before patching. Original installation is unchanged.' }
    $assets = $tree.files.webview.files.assets.files
    $menuName = 'profile-dropdown-items-71a6e604645d.js'
    $entry = $assets.$menuName
    $menu = Read-Entry $entry
    $sha = [Security.Cryptography.SHA256]::Create()
    function Hash-Bytes([byte[]]$bytes) { return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant() }
    if ((Hash-Bytes ([Text.Encoding]::UTF8.GetBytes($menu))) -ne '2e9cd921b030aab1dbd26e12ac1698f4bc9c3129b442e4c65ae690f43d3574c3') { throw 'Menu differs from the reviewed release; nothing changed.' }
    $anchor = 'Pn=f?(0,$.jsx)'
    if ([regex]::Matches($menu,[regex]::Escape($anchor)).Count -ne 1) { throw 'Menu anchor is ambiguous.' }
    $menu = $menu.Replace($anchor,'Pn=n?.modelProviderName===`TokenBots Partner Test`?(0,$.jsx)(TokenBotsNativeUsage,{}):f?(0,$.jsx)')
    $menu += "`n" + [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'component.js'))
    $patches['webview/assets/' + $menuName] = [Text.Encoding]::UTF8.GetBytes($menu)
    $build = $tree.files.'.vite'.files.build.files
    $handlerName = 'browser-background-switches-DmHa3bqb.js'
    $handler = Read-Entry $build.$handlerName
    $anchor = 'o.protocol.handle(`app`,async t=>{let n=L(t.url,e);'
    if ([regex]::Matches($handler,[regex]::Escape($anchor)).Count -ne 1) { throw 'Protocol handler changed.' }
    $handler = $handler.Replace($anchor,'o.protocol.handle(`app`,async t=>{if(new URL(t.url).host===`-`&&new URL(t.url).pathname.startsWith(`/tokenbots-native/`))return require(`./tokenbots-native.cjs`).handle(t);let n=L(t.url,e);')
    $patches['.vite/build/' + $handlerName] = [Text.Encoding]::UTF8.GetBytes($handler)
    $patches['.vite/build/tokenbots-native.cjs'] = [IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'backend.cjs'))
    $build | Add-Member -NotePropertyName 'tokenbots-native.cjs' -NotePropertyValue ([pscustomobject]@{size=0;offset='0'})
    $entries = New-Object 'System.Collections.Generic.List[object]'
    function Walk($node,[string]$prefix) {
        foreach ($property in @($node.files.PSObject.Properties)) {
            $v = $property.Value; $name = $prefix + $property.Name
            if ($v.files) { Walk $v ($name + '/') }
            elseif (-not $v.unpacked -and -not $v.link) {
                $entries.Add([pscustomobject]@{name=$name;entry=$v;oldOffset=[long]$v.offset;oldSize=[long]$v.size})
            }
        }
    }
    Walk $tree ''
    $offset = 0L
    foreach ($item in $entries) {
        $entry = $item.entry; $entry.offset = [string]$offset
        if ($patches.ContainsKey($item.name)) {
            $bytes = $patches[$item.name]; $entry.size = $bytes.Length
            $blocks = @(); $blockSize = 4194304
            for ($i=0; $i -lt $bytes.Length; $i += $blockSize) {
                $length = [Math]::Min($blockSize, $bytes.Length - $i)
                $block = New-Object byte[] $length; [Array]::Copy($bytes,$i,$block,0,$length)
                $blocks += Hash-Bytes $block
            }
            $integrity = [pscustomobject]@{algorithm='SHA256';hash=(Hash-Bytes $bytes);blockSize=$blockSize;blocks=$blocks}
            $entry | Add-Member -Force -NotePropertyName integrity -NotePropertyValue $integrity
        }
        $offset += [long]$entry.size
    }
    $json = [Text.Encoding]::UTF8.GetBytes(($tree | ConvertTo-Json -Depth 100 -Compress))
    $padding = (4 - ($json.Length % 4)) % 4
    $output = [IO.File]::Create($asar + '.new')
    try {
        $writer = New-Object IO.BinaryWriter($output)
        $writer.Write([uint32]4); $writer.Write([uint32](8+$json.Length+$padding)); $writer.Write([uint32](4+$json.Length+$padding)); $writer.Write([uint32]$json.Length)
        $writer.Write($json); if ($padding) { $writer.Write((New-Object byte[] $padding)) }
        $buffer = New-Object byte[] 1048576
        foreach ($item in $entries) {
            if ($patches.ContainsKey($item.name)) { $writer.Write([byte[]]$patches[$item.name]); continue }
            $stream.Position = $dataStart + $item.oldOffset; $left = $item.oldSize
            while ($left -gt 0) {
                $count = $stream.Read($buffer,0,[int][Math]::Min($buffer.Length,$left))
                if ($count -le 0) { throw 'Truncated source archive.' }
                $writer.Write($buffer,0,$count); $left -= $count
            }
        }
        $writer.Flush()
    } finally { $output.Dispose() }
} finally { $stream.Dispose() }
Move-Item -LiteralPath $asar -Destination $backup
try { Move-Item -LiteralPath ($asar + '.new') -Destination $asar }
catch { Move-Item -LiteralPath $backup -Destination $asar; throw }
# Repackage the custom archive's header hash using Electron's documented
# INTEGRITY/ELECTRONASAR resource. Integrity enforcement stays enabled.
# The resulting executable is a custom build, no longer OpenAI-signed.
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Collections.Generic;
public static class TokenBotsResource {
  public delegate bool LanguageCallback(IntPtr module, string type, string name, ushort language, IntPtr param);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern IntPtr LoadLibraryEx(string name, IntPtr file, uint flags);
  [DllImport("kernel32.dll")] public static extern bool FreeLibrary(IntPtr module);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern bool EnumResourceLanguages(IntPtr module, string type, string name, LanguageCallback callback, IntPtr param);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern IntPtr BeginUpdateResource(string name, bool deleteExisting);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern bool UpdateResource(IntPtr update, string type, string name, ushort language, byte[] data, uint size);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern bool EndUpdateResource(IntPtr update, bool discard);
  public static ushort[] Languages(string path) {
    var result = new List<ushort>(); var module = LoadLibraryEx(path, IntPtr.Zero, 2);
    if(module == IntPtr.Zero) throw new Exception("Cannot inspect custom executable resources");
    try {
      LanguageCallback callback = (m,t,n,l,p) => { result.Add(l); return true; };
      if(!EnumResourceLanguages(module,"INTEGRITY","ELECTRONASAR",callback,IntPtr.Zero)) throw new Exception("Expected integrity resource missing");
    } finally { FreeLibrary(module); }
    return result.ToArray();
  }
}
'@
$exe = Join-Path $appDir 'ChatGPT.exe'
Copy-Item -LiteralPath $exe -Destination ($exe + '.tokenbots-original')
$languages = [TokenBotsResource]::Languages($exe)
$headerHash = Hash-Bytes $json
$metadata = [Text.Encoding]::UTF8.GetBytes(('[{"file":"resources\\app.asar","alg":"SHA256","value":"' + $headerHash + '"}]'))
$update = [TokenBotsResource]::BeginUpdateResource($exe,$false)
if ($update -eq [IntPtr]::Zero) { throw 'Could not update custom archive metadata.' }
$complete = $false
try {
    foreach ($language in $languages) {
        if (-not [TokenBotsResource]::UpdateResource($update,'INTEGRITY','ELECTRONASAR',$language,$metadata,$metadata.Length)) { throw 'Custom archive metadata write failed.' }
    }
    $complete = $true
} finally {
    if (-not [TokenBotsResource]::EndUpdateResource($update,(-not $complete))) { throw 'Custom archive metadata commit failed.' }
}
$owlConfig = Join-Path $appDir 'resources\owl-app.ini'
if (Test-Path -LiteralPath $owlConfig) {
    $owlText = [IO.File]::ReadAllText($owlConfig)
    if ($owlText -notmatch '(?m)^UserDataDirectoryName=Codex\r?$') { throw 'Unexpected runtime profile name.' }
    Copy-Item -LiteralPath $owlConfig -Destination ($owlConfig + '.tokenbots-original')
    [IO.File]::WriteAllText($owlConfig, [regex]::Replace($owlText,'(?m)^UserDataDirectoryName=Codex\r?$', 'UserDataDirectoryName=TokenBotsCodex'), [Text.Encoding]::ASCII)
}
Write-Host 'Patched isolated TokenBots copy. Official installation unchanged.'
