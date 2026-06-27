<#
  Deploy via Git na VPS de producao (192.168.0.115).
  Garante checkout/clonagem do repo na VPS e publica via git pull + deploy remoto.

  Uso:
    powershell -ExecutionPolicy Bypass -File scripts\deploy_to_vps.ps1 -Password 'SENHA_DA_VPS'

  - Migration (011) aplica sozinha: o servico backend roda `alembic upgrade head`
    no start. Rebuildar o backend ja migra.
  - Preserva .env.prod e infra/go2rtc.local.yaml ao converter um diretorio legado
    sem .git para um checkout do repositorio.
#>
param(
  [Parameter(Mandatory = $true)][string]$Password,
  [string]$VpsHost = "192.168.0.115",
  [string]$User = "lundy",
  [string]$HostKey = "SHA256:AcKGZMXhBZ0+sV8wW371/wJHmES3JC58Ka8A1aPGC38",
  [string]$RemoteDir = "/home/lundy/monitoramento",
  [string]$RepoUrl = ""
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$plink = "plink"
$target = "$User@$VpsHost"

if ([string]::IsNullOrWhiteSpace($RepoUrl)) {
  $RepoUrl = (git config --get remote.origin.url).Trim()
}
if ([string]::IsNullOrWhiteSpace($RepoUrl)) {
  throw "Nao foi possivel descobrir o remote.origin.url para deploy via git."
}

function Invoke-Remote([string]$command) {
  & $plink -batch -hostkey $HostKey -pw $Password $target $command
  if ($LASTEXITCODE -ne 0) { throw "plink falhou (exit $LASTEXITCODE): $command" }
}

$legacyDir = "$RemoteDir-legacy-$(Get-Date -Format 'yyyyMMddHHmmss')"

& $plink -batch -hostkey $HostKey -pw $Password $target "test -d '$RemoteDir/.git'"
$repoExists = ($LASTEXITCODE -eq 0)

if (-not $repoExists) {
  Write-Host "[deploy] preparando checkout git na VPS..."
  Invoke-Remote "if [ -f '$RemoteDir/.env.prod' ]; then cp '$RemoteDir/.env.prod' /tmp/monitoramento.env.prod; fi"
  Invoke-Remote "if [ -f '$RemoteDir/infra/go2rtc.local.yaml' ]; then cp '$RemoteDir/infra/go2rtc.local.yaml' /tmp/monitoramento.go2rtc.local.yaml; fi"
  Invoke-Remote "if [ -d '$RemoteDir' ]; then mv '$RemoteDir' '$legacyDir'; fi"
  Invoke-Remote "git clone '$RepoUrl' '$RemoteDir'"
  Invoke-Remote "if [ -f /tmp/monitoramento.env.prod ]; then cp /tmp/monitoramento.env.prod '$RemoteDir/.env.prod'; fi"
  Invoke-Remote "if [ -f /tmp/monitoramento.go2rtc.local.yaml ]; then mkdir -p '$RemoteDir/infra' && cp /tmp/monitoramento.go2rtc.local.yaml '$RemoteDir/infra/go2rtc.local.yaml'; fi"
  Invoke-Remote "rm -f /tmp/monitoramento.env.prod /tmp/monitoramento.go2rtc.local.yaml"
}

Write-Host "[deploy] executando deploy remoto via git pull..."
Invoke-Remote "bash '$RemoteDir/scripts/remote_deploy.sh'"

Write-Host "[deploy] concluido."
