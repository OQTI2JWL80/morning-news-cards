$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$toolRoot = Join-Path $projectRoot '.local\tools\github-cli'
New-Item -ItemType Directory -Path $toolRoot -Force | Out-Null
$release = Invoke-RestMethod -Uri 'https://api.github.com/repos/cli/cli/releases/latest' -Headers @{ 'User-Agent' = 'morning-news-cards-setup' }
$zipAsset = $release.assets | Where-Object { $_.name -match '^gh_.*_windows_amd64\.zip$' } | Select-Object -First 1
$checksumAsset = $release.assets | Where-Object { $_.name -match '^gh_.*_checksums\.txt$' } | Select-Object -First 1
if (-not $zipAsset -or -not $checksumAsset) { throw 'Official GitHub CLI release assets not found.' }
$zipPath = Join-Path $toolRoot $zipAsset.name
Invoke-WebRequest -Uri $zipAsset.browser_download_url -OutFile $zipPath
$checksums = (Invoke-WebRequest -Uri $checksumAsset.browser_download_url).Content
if ($checksums -is [byte[]]) { $checksums = [Text.Encoding]::UTF8.GetString($checksums) }
$expectedLine = ($checksums -split "`n" | Where-Object { $_.Trim().EndsWith($zipAsset.name) } | Select-Object -First 1)
if (-not $expectedLine) { throw 'Checksum entry missing.' }
$expected = ($expectedLine.Trim() -split '\s+')[0]
$actual = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
if ($actual -ne $expected) { throw 'GitHub CLI checksum verification failed.' }
Expand-Archive -LiteralPath $zipPath -DestinationPath $toolRoot -Force
$executable = Get-ChildItem -LiteralPath $toolRoot -Filter gh.exe -File -Recurse | Select-Object -First 1
if (-not $executable) { throw 'GitHub CLI executable missing.' }
Write-Output $executable.FullName
& $executable.FullName --version
