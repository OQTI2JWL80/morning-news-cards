$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:GH_CONFIG_DIR = Join-Path (Get-Location) '.local\gh-config'
$gh = Join-Path (Get-Location) '.local\tools\github-cli\bin\gh.exe'
$repo = 'OQTI2JWL80/morning-news-cards'
$account = & $gh api user --jq .login
if ($LASTEXITCODE -or $account -ne 'OQTI2JWL80') { throw 'Sign in as OQTI2JWL80 first.' }
& $gh repo view $repo --json name | Out-Null
if ($LASTEXITCODE) { throw 'Publish the repository first.' }
Write-Host 'Create a key at https://aistudio.google.com/apikey in a Free Tier project.'
Write-Host 'Do not connect a billing account. The key is sent only to this repository Actions secret.'
$freeConfirmed = Read-Host 'Is this project Free Tier with no billing account attached? Type FREE to confirm'
if ($freeConfirmed -cne 'FREE') { throw 'Free Tier not confirmed; no API key was requested or changed.' }
$secureKey = Read-Host 'Paste the Gemini API key (input hidden)' -AsSecureString
if ($secureKey.Length -eq 0) { throw 'No API key entered.' }
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    $plainKey | & $gh secret set GEMINI_API_KEY --repo $repo
    if ($LASTEXITCODE) { throw 'Secret registration failed.' }
} finally {
    $plainKey = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    $secureKey.Dispose()
}
& $gh variable set GEMINI_FREE_TIER_CONFIRMED --body true --repo $repo
if ($LASTEXITCODE) { throw 'Free Tier confirmation variable could not be saved.' }
& $gh workflow run daily.yml --repo $repo
if ($LASTEXITCODE) { throw 'AI setup saved; start the workflow from GitHub Actions.' }
Write-Host 'AI setup saved. The workflow will collect, summarize, validate, and publish.'
& $gh run list --repo $repo --limit 3
