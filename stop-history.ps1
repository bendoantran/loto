$ErrorActionPreference = 'Stop'
Set-Content -LiteralPath (Join-Path $PSScriptRoot 'STOP') -Value 'Stop requested by the user.'
Write-Output 'Stop requested. The collector will save progress and stop after its current request (normally within 20 seconds).'
Write-Output 'Run start-history.ps1 to resume.'
