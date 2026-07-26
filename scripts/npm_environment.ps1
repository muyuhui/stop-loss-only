function Initialize-ProjectNpmEnvironment {
    param([Parameter(Mandatory = $true)][string]$StateRoot)

    New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
    $userConfig = Join-Path $StateRoot 'npm-userconfig'
    Set-Content -LiteralPath $userConfig -Value '' -NoNewline -Encoding ASCII
    $env:NPM_CONFIG_USERCONFIG = $userConfig
}
