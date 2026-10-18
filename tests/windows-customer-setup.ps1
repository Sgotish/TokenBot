# Exercise real setup and repair paths with isolated homes and synthetic credentials.
$ErrorActionPreference = 'Stop'
$originalHome = $env:CODEX_HOME
$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('tokenbot-customers-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixtureRoot | Out-Null
function Invoke-RestMethod { return @{data=@(@{id='gpt-6.1-sol'})} }
try {
    $template = [IO.File]::ReadAllText((Join-Path $PSScriptRoot '..\integrations\windows-codex\setup.ps1.template'))
    foreach ($name in @('alice','bob')) {
        $env:CODEX_HOME = Join-Path $fixtureRoot $name
        New-Item -ItemType Directory -Path $env:CODEX_HOME | Out-Null
        $path = Join-Path $env:CODEX_HOME 'config.toml'
        [IO.File]::WriteAllText($path, "model = `"original-model`"`n[projects.`"C:/example`"]`ntrust_level = `"trusted`"`n")
        $source = $template.Replace('__BASE_URL__','https://example.test/v1').Replace('__TEST_KEY__',($name+'-synthetic-key')).Replace('TokenBots Partner Test',('TokenBots '+$name))
        & ([scriptblock]::Create($source))
        $current = [IO.File]::ReadAllText($path)
        if (-not $current.Contains($name+'-synthetic-key') -or -not $current.Contains('trust_level = "trusted"')) { throw 'Own key or existing project settings missing' }
        if ($current.Contains($(if ($name -eq 'alice') {'bob-synthetic-key'} else {'alice-synthetic-key'}))) { throw 'Customer credential crossed homes' }
        if (@(Get-ChildItem -Path ($path+'.before-tokenbots-*')).Count -lt 1) { throw 'Backup missing' }
        # Rotate a customer's package. The real repair branch must replace the old key and name.
        & ([scriptblock]::Create($source.Replace(($name+'-synthetic-key'),($name+'-rotated-key')).Replace(('TokenBots '+$name),('TokenBots '+$name+' updated'))))
        $current=[IO.File]::ReadAllText($path)
        if ($current.Contains($name+'-synthetic-key') -or -not $current.Contains($name+'-rotated-key') -or -not $current.Contains('TokenBots '+$name+' updated')) { throw 'Customer package repair failed' }
    }
    Write-Host 'Two independent Windows customer setups and credential updates passed.'
} finally {
    $env:CODEX_HOME = $originalHome
    Remove-Item -LiteralPath $fixtureRoot -Recurse -Force
    Remove-Item Function:\Invoke-RestMethod
}
