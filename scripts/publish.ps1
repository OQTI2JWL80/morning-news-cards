param([switch]$Login)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:GH_CONFIG_DIR = Join-Path (Get-Location) '.local\gh-config'
$gh = Join-Path (Get-Location) '.local\tools\github-cli\bin\gh.exe'
if (-not (Test-Path -LiteralPath $gh)) { & "$PSScriptRoot\install-gh.ps1" }
$gitCommand = Get-Command git -ErrorAction SilentlyContinue
$git = if ($gitCommand) { $gitCommand.Source } else { Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' }
if (-not (Test-Path -LiteralPath $git)) { throw 'Install Git for Windows first.' }
$env:PATH = (Split-Path -Parent $git) + [IO.Path]::PathSeparator + $env:PATH
if ($Login) {
    & $gh auth login --hostname github.com --git-protocol https --web --skip-ssh-key
    if ($LASTEXITCODE) { throw 'GitHub login not completed.' }
}
$accountText = & $gh api user
if ($LASTEXITCODE) { throw 'Run scripts/publish.ps1 -Login to authenticate first.' }
$account = $accountText | ConvertFrom-Json
if ($account.login -ne 'OQTI2JWL80') { throw 'Expected GitHub account OQTI2JWL80.' }
& $gh auth setup-git
if ($LASTEXITCODE) { throw 'Git authentication setup failed.' }
if (-not (Test-Path -LiteralPath '.git')) {
    & $git init -b main
    if ($LASTEXITCODE) { throw 'Git initialization failed.' }
}
& $git config user.name $account.login
& $git config user.email "$($account.id)+$($account.login)@users.noreply.github.com"
& $git add .gitignore .env.example .github newsbrief scripts site tests docs README.md requirements.txt package.json
if ($LASTEXITCODE) { throw 'Source staging failed.' }
& $git diff --cached --quiet
if ($LASTEXITCODE -eq 1) {
    & $git commit -m 'Build daily Korean morning news cards'
    if ($LASTEXITCODE) { throw 'Source commit failed.' }
}
$repo = 'OQTI2JWL80/morning-news-cards'
& $gh repo view $repo --json name | Out-Null
if ($LASTEXITCODE) {
    & $gh repo create $repo --public --description '매일 한국시간 07시 기준 뉴스 카드'
    if ($LASTEXITCODE) { throw 'Repository creation failed.' }
}
$remoteNames = & $git remote
$origin = if ($remoteNames -contains 'origin') { & $git remote get-url origin } else { $null }
$expectedOrigin = "https://github.com/$repo.git"
if (-not $origin) { & $git remote add origin $expectedOrigin }
elseif ($origin -ne $expectedOrigin) { throw 'Unexpected origin; refusing to replace it.' }
& $git push -u origin main
if ($LASTEXITCODE) { throw 'Push failed; no force push was attempted.' }
# An initial push may run before Pages is enabled; explicitly queue a fresh run.
& $gh api --method POST "repos/$repo/pages" -f build_type=workflow 2>$null | Out-Null
if ($LASTEXITCODE) {
    & $gh api --method PUT "repos/$repo/pages" -f build_type=workflow | Out-Null
    if ($LASTEXITCODE) { throw 'Pages setup failed.' }
}
& $gh workflow run daily.yml --repo $repo
if ($LASTEXITCODE) { throw 'Workflow dispatch failed; use the Actions Run workflow button.' }
Write-Output 'Site deployment started: https://oqti2jwl80.github.io/morning-news-cards/'
Write-Output 'Add GEMINI_API_KEY in GitHub Actions secrets; confirm free tier before setting GEMINI_FREE_TIER_CONFIRMED=true.'
& $gh run list --repo $repo --limit 3
