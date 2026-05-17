# Agente Local — Monitoramento de Trânsito

Software instalado no cliente para captura e envio de frames ao servidor.

## Requisitos

- Windows 10 / 11 (64-bit)
- Câmera IP com URL RTSP ou webcam USB
- Acesso à rede onde o servidor está hospedado

## Instalação rápida

### 1. Baixe o executável

Salve o `agent.exe` em uma pasta dedicada, por exemplo `C:\Monitoramento\`.

### 2. Crie o config.json

Na **mesma pasta** do `agent.exe`, crie `config.json`:

```json
{
  "server_url": "https://seu-servidor.com",
  "token": "SEU_TOKEN_AQUI",
  "camera_rtsp": "rtsp://usuario:senha@192.168.0.100:554/stream",
  "frame_interval": 1
}
```

> O **token** é gerado automaticamente ao cadastrar a câmera no painel web.

### 3. Execute

Duplo clique em `agent.exe` ou pelo terminal:

```
agent.exe
```

Saída esperada:
```
[agent] iniciando...
[agent] heartbeat: ok
[agent] frame enviado: ok
```

### 4. Verifique no painel

A câmera deve aparecer como **Online** em até 30 segundos.

---

## Configurações do config.json

| Campo | Descrição | Padrão |
|-------|-----------|--------|
| `server_url` | URL base do servidor | obrigatório |
| `token` | Token único da câmera (gerado no painel) | obrigatório |
| `camera_rtsp` | URL RTSP ou índice USB (`0`, `1`…) | `"0"` |
| `frame_interval` | Segundos entre capturas | `1` |
| `min_confidence` | Confiança mínima OCR (0.0–1.0) | `0.70` |
| `dedup_seconds` | Ignora mesma placa por N segundos | `30` |

---

## Solução de problemas

| Mensagem | Causa | Solução |
|----------|-------|---------|
| `config.json não encontrado` | Arquivo fora da pasta | Coloque config.json ao lado do agent.exe |
| `Campo obrigatório ausente: token` | Token faltando | Copie o token do painel web |
| `heartbeat: falhou` | Sem acesso ao servidor | Verifique `server_url` e rede |
| `falha ao capturar frame` | Câmera inacessível | Verifique a URL RTSP e se a câmera está ligada |

---

## Build (desenvolvedores)

```bash
bash build.sh
# Gera dist/agent.exe
```

## Executar como serviço Windows (opcional)

```bat
nssm install MonitoramentoAgent "C:\Monitoramento\agent.exe"
nssm set MonitoramentoAgent AppDirectory "C:\Monitoramento"
nssm start MonitoramentoAgent
```
