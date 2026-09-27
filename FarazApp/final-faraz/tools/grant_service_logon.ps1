param(
    [Parameter(Mandatory = $true)]
    [string]$Account
)

$ErrorActionPreference = 'Stop'

$sid = (New-Object System.Security.Principal.NTAccount($Account)).Translate(
    [System.Security.Principal.SecurityIdentifier]
).Value

$infFile = Join-Path $env:TEMP 'faraz_secedit.inf'
$dbFile = Join-Path $env:TEMP 'faraz_secedit.sdb'
$logFile = Join-Path $env:TEMP 'faraz_secedit.log'

if (Test-Path $dbFile) { Remove-Item $dbFile -Force -ErrorAction SilentlyContinue }
if (Test-Path $logFile) { Remove-Item $logFile -Force -ErrorAction SilentlyContinue }

secedit /export /cfg $infFile /quiet | Out-Null
if (-not (Test-Path $infFile)) {
    Write-Error "Could not export local security policy."
}

$content = Get-Content $infFile -Encoding Unicode
$updated = $false
$newContent = foreach ($line in $content) {
    if ($line -like 'SeServiceLogonRight*') {
        $updated = $true
        if ($line -match [regex]::Escape($sid)) {
            $line
        }
        elseif ($line -match '=\s*$') {
            ('SeServiceLogonRight = {0}' -f $sid)
        }
        else {
            ($line.TrimEnd() + ',' + $sid)
        }
    }
    else {
        $line
    }
}

if (-not $updated) {
    $newContent += 'SeServiceLogonRight = ' + $sid
}

Set-Content $infFile $newContent -Encoding Unicode
secedit /configure /db $dbFile /cfg $infFile /areas USER_RIGHTS /log $logFile /quiet | Out-Null
exit 0
