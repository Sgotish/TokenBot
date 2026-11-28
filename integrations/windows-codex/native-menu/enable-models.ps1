param([Parameter(Mandatory=$true)][string]$AppDirectory, [string]$ProfileDirectory, [string]$CatalogPath)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath (Join-Path $AppDirectory '.tokenbots-custom-copy'))) { throw 'Unknown TokenBots app copy.' }
if (-not $ProfileDirectory) {
    $access = Get-Content -Raw -LiteralPath (Join-Path $AppDirectory 'resources\tokenbots-native.json') | ConvertFrom-Json
    $id = ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($access.key)))).Replace('-','').Substring(0,16).ToLowerInvariant()
    $ProfileDirectory = Join-Path $env:USERPROFILE ('.tokenbots-native-homes\' + $id)
}
$config = Join-Path $ProfileDirectory 'config.toml'
$text = [IO.File]::ReadAllText($config)
$source = if ($CatalogPath) { $CatalogPath } else { Join-Path $PSScriptRoot 'codex-models.json' }
$catalog = Get-Content -Raw -LiteralPath $source | ConvertFrom-Json
foreach ($model in @('gpt-6.2-sol','gpt-6.2-astra','gpt-6.1-terra')) {
    if ($catalog.models.slug -notcontains $model) { throw 'Incomplete model catalog. Nothing changed.' }
}
$destination = Join-Path $ProfileDirectory 'tokenbots-models.json'
$section = [regex]::Match($text, '(?m)^[ \t]*\[')
$root = if ($section.Success) { $text.Substring(0,$section.Index) } else { $text }
$rest = if ($section.Success) { $text.Substring($section.Index) } else { '' }
$root = [regex]::Replace($root,'(?m)^[ \t]*model_catalog_json[ \t]*=[^\r\n]*(\r?\n|$)','')
$line = 'model_catalog_json = ' + (ConvertTo-Json -Compress $destination)
$next = $line + "`r`n" + $root + $rest
if ($next -ne $text) { Copy-Item -LiteralPath $config -Destination ($config + '.before-models-' + [guid]::NewGuid().ToString('N')) }
[IO.File]::WriteAllText($destination,[IO.File]::ReadAllText($source),(New-Object Text.UTF8Encoding($false)))
[IO.File]::WriteAllText($config,$next,(New-Object Text.UTF8Encoding($false)))
Write-Host 'Model catalog updated. Existing model selection and conversations preserved.'
