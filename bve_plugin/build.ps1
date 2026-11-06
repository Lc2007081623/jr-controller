param([string]$Bve5 = 'D:\bve', [string]$Bve6 = 'D:\BVE6', [switch]$Test)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$out = Join-Path $root 'build\bve'
foreach ($target in @(@('BVE5', $Bve5, 'v3.5', 'x86'), @('BVE6', $Bve6, 'v4.0.30319', 'x64'))) {
    $folder = Join-Path $out $target[0]
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
    $api = Join-Path $target[1] 'Mackoy.IInputDevice.dll'
    $compiler = Join-Path $env:WINDIR ('Microsoft.NET\Framework\' + $target[2] + '\csc.exe')
    & $compiler /nologo /target:library /optimize+ "/platform:$($target[3])" "/out:$folder\JRController.Bve.dll" "/reference:$api" /reference:System.Windows.Forms.dll (Join-Path $PSScriptRoot 'JRController.cs')
    if ($LASTEXITCODE -ne 0) { throw "Build failed: $($target[0])" }
    if ($Test) {
        Copy-Item -LiteralPath $api -Destination $folder -Force
        & $compiler /nologo /define:TEST /target:exe "/platform:$($target[3])" "/out:$folder\PluginTests.exe" "/reference:$api" /reference:System.Windows.Forms.dll (Join-Path $PSScriptRoot 'JRController.cs') (Join-Path $PSScriptRoot 'PluginTests.cs')
        if ($LASTEXITCODE -ne 0) { throw 'Test build failed' }
        & (Join-Path $folder 'PluginTests.exe')
        if ($LASTEXITCODE -ne 0) { throw "Tests failed: $($target[0])" }
    }
}
