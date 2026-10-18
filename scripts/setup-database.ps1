[CmdletBinding()]
param(
    [string]$DatabaseHost = 'localhost',
    [ValidateRange(1, 65535)][int]$Port = 5432,
    [string]$AdminUser = 'postgres',
    [string]$PsqlPath = 'psql',
    [switch]$SchemaOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$configuration = @{}

# Load development defaults, then local overrides. Never execute .env contents.
foreach ($fileName in @('.env.example', '.env')) {
    $filePath = Join-Path $projectRoot $fileName
    if (Test-Path -LiteralPath $filePath) {
        foreach ($line in Get-Content -LiteralPath $filePath -Encoding UTF8) {
            if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
                $key = $Matches[1]
                $value = $Matches[2].Trim()
                if ($value.Length -ge 2 -and (
                    ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                    ($value.StartsWith("'") -and $value.EndsWith("'"))
                )) {
                    $value = $value.Substring(1, $value.Length - 2)
                }
                $configuration[$key] = $value
            }
        }
    }
}

function Get-ConfigurationValue([string]$Name) {
    $processValue = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ($null -ne $processValue) { return $processValue }
    return $configuration[$Name]
}

$databaseUser = Get-ConfigurationValue 'POSTGRES_USER'
$databasePassword = Get-ConfigurationValue 'POSTGRES_PASSWORD'
$databaseName = Get-ConfigurationValue 'POSTGRES_DB'
foreach ($value in @($databaseUser, $databasePassword, $databaseName)) {
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw 'Set POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_DB in .env first.'
    }
}

if (-not (Get-Command $PsqlPath -ErrorAction SilentlyContinue)) {
    throw 'psql was not found. Add PostgreSQL 16/bin to PATH or pass -PsqlPath.'
}

$connectionArguments = @('-X', '-w', '-h', $DatabaseHost, '-p', "$Port", '-v', 'ON_ERROR_STOP=1')
$savedEnvironment = @{}
foreach ($name in @('PGPASSWORD', 'PGCLIENTENCODING', 'PGCONNECT_TIMEOUT',
                    'TASKFLOW_DB_USER', 'TASKFLOW_DB_PASSWORD', 'TASKFLOW_DB_NAME')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

try {
    $env:PGCLIENTENCODING = 'UTF8'
    $env:PGCONNECT_TIMEOUT = '5'
    $env:TASKFLOW_DB_USER = $databaseUser
    $env:TASKFLOW_DB_PASSWORD = $databasePassword
    $env:TASKFLOW_DB_NAME = $databaseName

    if (-not $SchemaOnly) {
        $adminPassword = Get-ConfigurationValue 'POSTGRES_ADMIN_PASSWORD'
        if ([string]::IsNullOrEmpty($adminPassword)) {
            $securePassword = Read-Host "PostgreSQL password for $AdminUser" -AsSecureString
            $credential = New-Object System.Management.Automation.PSCredential($AdminUser, $securePassword)
            $adminPassword = $credential.GetNetworkCredential().Password
        }
        $env:PGPASSWORD = $adminPassword
        Write-Host "Creating role/database if missing on ${DatabaseHost}:$Port..."
        & $PsqlPath @connectionArguments -U $AdminUser -d postgres -f (Join-Path $projectRoot 'database/bootstrap.sql')
        if ($LASTEXITCODE -ne 0) { throw 'Database bootstrap failed.' }
    }

    $env:PGPASSWORD = $databasePassword
    Write-Host "Applying schema to $databaseName as $databaseUser..."
    & $PsqlPath @connectionArguments -U $databaseUser -d $databaseName -f (Join-Path $projectRoot 'database/migrate.sql')
    if ($LASTEXITCODE -ne 0) { throw 'Schema migration failed; its transaction was rolled back.' }

    & $PsqlPath @connectionArguments -U $databaseUser -d $databaseName -c @'
SELECT current_database() AS database, current_user AS owner,
       current_setting('TimeZone') AS timezone,
       (SELECT count(*) FROM pg_tables
        WHERE schemaname = 'public' AND tablename <> 'schema_migrations') AS application_tables,
       (SELECT count(*) FROM public.permissions) AS permissions;
'@
    if ($LASTEXITCODE -ne 0) { throw 'Database verification failed.' }
    Write-Host "Database ready: ${DatabaseHost}:$Port/$databaseName"
}
finally {
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
    $adminPassword = $null
    $databasePassword = $null
    $credential = $null
    $securePassword = $null
}
