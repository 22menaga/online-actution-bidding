$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot '.env.docker'
$exampleFile = Join-Path $projectRoot '.env.docker.example'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker CLI was not found. Install and start Docker Desktop, then try again.'
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Desktop is not running or its engine is unavailable.'
}

if (-not (Test-Path $envFile)) {
    $template = Get-Content -Raw -Encoding UTF8 $exampleFile
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    $secretBytes = New-Object byte[] 48
    $passwordBytes = New-Object byte[] 32
    $random.GetBytes($secretBytes)
    $random.GetBytes($passwordBytes)
    $random.Dispose()
    $secretKey = [Convert]::ToBase64String($secretBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    $databasePassword = [BitConverter]::ToString($passwordBytes).Replace('-', '').ToLowerInvariant()
    $template = $template.Replace('GENERATE_WITH_scripts-docker-up.ps1', $secretKey)
    $template = $template.Replace("auction_user:$secretKey@db", "auction_user:$databasePassword@db")
    $template = $template.Replace("POSTGRES_PASSWORD=$secretKey", "POSTGRES_PASSWORD=$databasePassword")
    Set-Content -Path $envFile -Value $template -Encoding ASCII -NoNewline
    Write-Host 'Created .env.docker with unique local secrets. Keep this file private.'
}

Push-Location $projectRoot
try {
    docker compose --env-file .env.docker up --build --detach --wait --wait-timeout 300
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose could not start the application. Check the build/start output above.'
    }
    docker compose --env-file .env.docker ps
    Write-Host 'Application URL: http://localhost:8000'
    Write-Host 'Create an admin account with: docker compose --env-file .env.docker exec web python manage.py createsuperuser'
}
finally {
    Pop-Location
}
