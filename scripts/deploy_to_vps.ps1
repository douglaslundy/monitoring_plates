<#
  Deploy local -> VPS de producao (192.168.0.115, nao e git).
  Sincroniza os fontes alterados via pscp e reconstroi a stack via plink.

  Uso:
    powershell -ExecutionPolicy Bypass -File scripts\deploy_to_vps.ps1 -Password 'SENHA_DA_VPS'

  - Migration (011) aplica sozinha: o servico backend roda `alembic upgrade head`
    no start. Rebuildar o backend ja migra.
  - NAO toca em infra/go2rtc.local.yaml na VPS (mantem o stream recortado da
    camera dual-lens que ja funciona). go2rtc e reiniciado para carregar os
    novos templates lens_lower/lens_upper do go2rtc.yaml.
#>
param(
  [Parameter(Mandatory = $true)][string]$Password,
  [string]$VpsHost = "192.168.0.115",
  [string]$User = "lundy",
  [string]$HostKey = "SHA256:AcKGZMXhBZ0+sV8wW371/wJHmES3JC58Ka8A1aPGC38",
  [string]$RemoteDir = "/home/lundy/monitoramento"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$pscp = "pscp"
$plink = "plink"
$target = "$User@$VpsHost"

function Copy-Path($localRelative, $remoteParent) {
  Write-Host "[deploy] pscp -> $remoteParent  ($localRelative)"
  & $pscp -batch -hostkey $HostKey -pw $Password -r $localRelative "${target}:$remoteParent"
  if ($LASTEXITCODE -ne 0) { throw "pscp falhou em $localRelative (exit $LASTEXITCODE)" }
}

# 1) Sincroniza os fontes (cobre todos os arquivos do lote) + o script remoto.
Copy-Path "backend/app"             "$RemoteDir/backend/"
Copy-Path "backend/alembic"         "$RemoteDir/backend/"
Copy-Path "backend/Dockerfile"      "$RemoteDir/backend/"
Copy-Path "backend/export_models.py" "$RemoteDir/backend/"
Copy-Path "backend/yolov8n.pt"      "$RemoteDir/backend/"
Copy-Path "backend/yolov8s.pt"      "$RemoteDir/backend/"
Copy-Path "frontend/src"            "$RemoteDir/frontend/"
Copy-Path "infra/go2rtc.yaml"       "$RemoteDir/infra/"
Copy-Path "scripts/remote_deploy.sh" "$RemoteDir/"

# 2) Rebuild + restart na VPS rodando o script remoto (backend roda
#    `alembic upgrade head` no start -> migra). Executar um ARQUIVO via bash evita
#    o mangling de aspas/linhas que ocorre ao passar comando multi-linha por
#    PowerShell -> plink.
Write-Host "[deploy] executando rebuild remoto via plink..."
& $plink -batch -hostkey $HostKey -pw $Password $target "bash $RemoteDir/remote_deploy.sh"
if ($LASTEXITCODE -ne 0) { throw "plink/rebuild remoto falhou (exit $LASTEXITCODE)" }

Write-Host "[deploy] concluido."
