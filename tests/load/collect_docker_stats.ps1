# Samples `docker stats` for one container into a CSV while a load run is on.
# Owner: DevOps 1 (Day 3). Usage:
#   Start-Job -FilePath tests/load/collect_docker_stats.ps1 -ArgumentList `
#       "setu-day3-load", "tests/load/results/a_docker_stats.csv"
#   ... run locust ...
#   Get-Job | Stop-Job   # stop sampling, one header line + one row per sample
param(
    [Parameter(Mandatory = $true)][string]$Container,
    [Parameter(Mandatory = $true)][string]$OutFile,
    [int]$IntervalSeconds = 5
)

$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
if (-not (Test-Path $docker)) { $docker = "docker" }

$dir = Split-Path -Parent $OutFile
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }

"timestamp,cpu_percent,mem_usage,mem_percent,net_io" |
    Out-File -FilePath $OutFile -Encoding utf8

while ($true) {
    $line = & $docker stats $Container --no-stream `
        --format "{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}}" 2>$null
    if ($line) {
        "$(Get-Date -Format o),$line" |
            Out-File -FilePath $OutFile -Append -Encoding utf8
    }
    Start-Sleep -Seconds $IntervalSeconds
}
