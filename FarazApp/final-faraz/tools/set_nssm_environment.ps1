param(
    [Parameter(Mandatory = $true)]
    [string]$NssmExe,
    [Parameter(Mandatory = $true)]
    [string]$ServiceName
)

$pairs = @(
    'PYTHONIOENCODING=utf-8',
    'PYTHONUTF8=1'
)

$vars = @(
    'FLASK_SECRET_KEY',
    'APP_LOGIN_USERNAME',
    'APP_LOGIN_PASSWORD',
    'SESSION_COOKIE_SECURE',
    'APP_PORT',
    'APP_HOST',
    'WAITRESS_THREADS'
)

foreach ($name in $vars) {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    if ($null -ne $value -and $value -ne '') {
        $pairs += ($name + '=' + $value)
    }
}

if (-not ($pairs | Where-Object { $_ -like 'APP_PORT=*' })) {
    $pairs += 'APP_PORT=5001'
}
if (-not ($pairs | Where-Object { $_ -like 'APP_HOST=*' })) {
    $pairs += 'APP_HOST=0.0.0.0'
}
if (-not ($pairs | Where-Object { $_ -like 'WAITRESS_THREADS=*' })) {
    $pairs += 'WAITRESS_THREADS=8'
}
if (-not ($pairs | Where-Object { $_ -like 'SESSION_COOKIE_SECURE=*' })) {
    $pairs += 'SESSION_COOKIE_SECURE=0'
}

$args = @('set', $ServiceName, 'AppEnvironmentExtra') + $pairs
& $NssmExe @args
if ($LASTEXITCODE -ne 0) {
    exit 1
}

exit 0
