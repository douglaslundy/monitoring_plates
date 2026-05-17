# Instalação do Agente de Câmera

Este guia é para o instalador do agente nas câmeras do cliente. Não é necessário conhecimento técnico.

## O que é o agente?

O agente é um pequeno programa instalado no computador do cliente. Ele conecta na câmera de segurança e envia imagens automaticamente para o sistema de reconhecimento de placas.

---

## Requisitos

- Windows 10 ou superior (64 bits)
- Computador com acesso à câmera (mesma rede local)
- Acesso à internet para enviar os frames ao servidor
- O endereço RTSP da câmera (fornecido pelo fabricante ou instalador de câmeras)

---

## Passo 1 — Baixar o agente

1. Acesse o sistema em `https://seudominio.com`
2. Faça login com suas credenciais
3. Vá em **Câmeras** → selecione a câmera desejada → **Baixar Agente**
4. Salve o arquivo `monitoramento-agent.zip` em uma pasta de fácil acesso (ex: `C:\Agente`)

---

## Passo 2 — Obter o token da câmera

1. No sistema, acesse **Câmeras** → clique na câmera
2. Copie o **Token do Agente** (sequência longa de letras e números)

---

## Passo 3 — Configurar o agente

1. Extraia o arquivo `monitoramento-agent.zip` para uma pasta (ex: `C:\Agente`)
2. Dentro da pasta extraída, encontre o arquivo `config.json.example`
3. **Copie** o arquivo e renomeie a cópia para `config.json`
4. Abra `config.json` com o Bloco de Notas e preencha:

```json
{
  "server_url": "https://seudominio.com",
  "token": "COLE_O_TOKEN_DA_CAMERA_AQUI",
  "camera_rtsp": "rtsp://usuario:senha@192.168.1.100:554/stream",
  "frame_interval": 5
}
```

| Campo | O que colocar |
|---|---|
| `server_url` | Endereço do sistema (fornecido pelo administrador) |
| `token` | Token copiado no Passo 2 |
| `camera_rtsp` | Endereço da câmera (consulte o manual da câmera ou instalador) |
| `frame_interval` | A cada quantos segundos enviar uma imagem (recomendado: 5) |

5. Salve o arquivo `config.json`

---

## Passo 4 — Iniciar o agente

1. Dê duplo clique em `monitoramento-agent.exe`
2. Uma janela preta aparecerá com mensagens como:
   ```
   [agent] iniciando...
   [agent] heartbeat: ok
   [agent] frame enviado: ok
   ```
3. Isso significa que está funcionando. **Não feche esta janela.**

---

## Passo 5 — Iniciar automaticamente com o Windows (opcional)

Para que o agente inicie automaticamente quando o computador ligar:

1. Pressione `Win + R`, digite `shell:startup` e clique em OK
2. Na pasta que abrir, crie um atalho para `monitoramento-agent.exe`
3. Pronto — o agente iniciará automaticamente

---

## Problemas comuns

### "config.json não encontrado"
- Verifique se o arquivo `config.json` (não `config.json.example`) está na **mesma pasta** que o `monitoramento-agent.exe`

### "heartbeat: falhou"
- Verifique se o computador tem acesso à internet
- Verifique se o `server_url` no `config.json` está correto
- Verifique se o `token` foi copiado corretamente (sem espaços extras)

### "falha ao capturar frame — verifique a câmera"
- Verifique se o endereço RTSP da câmera está correto
- Teste o endereço em um player como VLC: **Mídia** → **Abrir Fluxo de Rede** → cole o endereço RTSP
- Verifique se o usuário e senha da câmera estão corretos no endereço RTSP

### O agente fecha sozinho
- Verifique se há mensagens de erro antes de fechar
- Verifique se o arquivo `config.json` está preenchido corretamente

---

## Suporte

Em caso de dúvidas, entre em contato com o administrador do sistema e informe as mensagens que aparecem na janela do agente.
