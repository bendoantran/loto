$ErrorActionPreference = 'Stop'
$taskPython = (Get-Command python -ErrorAction Stop).Source
$taskCollector = Join-Path $PSScriptRoot 'history.py'
$taskStatus = (& $taskPython $taskCollector status | ConvertFrom-Json)
if ($taskStatus.worker_running) {
    Write-Output 'The collector is already running. See PROGRESS.md or run status-history.ps1.'
    exit 0
}
if ($taskStatus.state -eq 'finished') {
    Write-Output 'The requested archive has finished. See PROGRESS.md and years/.'
    exit 0
}
$taskStop = Join-Path $PSScriptRoot 'STOP'
if (Test-Path -LiteralPath $taskStop) { Remove-Item -LiteralPath $taskStop }
$taskLogDirectory = Join-Path $PSScriptRoot 'launch-logs'
New-Item -ItemType Directory -Path $taskLogDirectory -Force | Out-Null
$taskStamp = Get-Date -Format 'yyyyMMdd-HHmmss-ffff'
$taskProcess = Start-Process -FilePath $taskPython -ArgumentList @('-u', ('"' + $taskCollector + '"'), 'run') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskLogDirectory ($taskStamp + '.out.log')) -RedirectStandardError (Join-Path $taskLogDirectory ($taskStamp + '.err.log')) -PassThru
Write-Output "Started loto history collector (PID $($taskProcess.Id))."
Write-Output 'It resumes saved checkpoints and automatically retries connection failures.'
Write-Output ('Progress: ' + (Join-Path $PSScriptRoot 'PROGRESS.md'))
