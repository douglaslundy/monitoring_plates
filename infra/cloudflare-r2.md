# Configurar Cloudflare R2 (armazenamento de imagens)

Cloudflare R2 oferece **10 GB gratuitos/mês** sem custo de egress, ideal para armazenar frames das câmeras.

## Passo a passo

### 1. Criar bucket R2

1. Acesse [dash.cloudflare.com](https://dash.cloudflare.com) → selecione sua conta
2. Menu lateral → **R2 Object Storage** → **Create bucket**
3. Nome do bucket: `monitoramento-frames`
4. Localização: **Automatic** (ou escolha a mais próxima do servidor)
5. Clique em **Create bucket**

### 2. Criar API Token com permissão R2

1. Clique em **Manage R2 API Tokens** (canto superior direito da página R2)
2. **Create API Token**
3. Permissões: **Object Read & Write**
4. Scope: **Specific bucket** → `monitoramento-frames`
5. Clique em **Create API Token**
6. **Copie imediatamente** o Access Key ID e Secret Access Key (não são exibidos novamente)

### 3. Obter o Account ID

1. Na página principal do R2 → anote o **Account ID** exibido no canto direito
2. O endpoint S3 compatível será:
   ```
   https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   ```

### 4. Configurar no sistema

Atualize as variáveis de ambiente (`.env.prod` ou Railway):

```env
STORAGE_TYPE=s3
S3_BUCKET=monitoramento-frames
S3_ENDPOINT=https://SEU_ACCOUNT_ID.r2.cloudflarestorage.com
S3_ACCESS_KEY=SEU_ACCESS_KEY_ID_AQUI
S3_SECRET_KEY=SEU_SECRET_ACCESS_KEY_AQUI
```

### 5. (Opcional) URL pública para acesso direto

Se quiser que as imagens sejam servidas diretamente pelo R2 (sem passar pela API):

1. No bucket → **Settings** → **Public access** → habilite **R2.dev subdomain**
2. Ou vincule um domínio personalizado em **Custom Domains**
3. Atualize `storage_service.py` para retornar a URL pública do R2 em vez de `/api/images/...`

> **Nota de segurança:** Por padrão, o sistema serve imagens via `/api/images/{path}` com verificação de autenticação. Habilitar acesso público ao bucket remove essa proteção — use somente se as imagens não forem sensíveis.

## Limites gratuitos R2

| Recurso | Limite gratuito |
|---|---|
| Armazenamento | 10 GB/mês |
| Operações de escrita (Class A) | 1 milhão/mês |
| Operações de leitura (Class B) | 10 milhões/mês |
| Egress (saída de dados) | Gratuito (sem limite) |

Para 50 câmeras capturando 1 frame/segundo com JPEG ~30 KB:
- Volume diário: 50 × 86.400 × 30 KB ≈ **123 GB/dia** → muito acima do gratuito
- **Recomendação:** aumentar `AGENT_FRAME_INTERVAL` para 5–30 segundos ou ativar a deduplicação agressiva (`AGENT_DEDUP_SECONDS=60`)
- Com intervalo de 10s: ~12 GB/dia → ainda excede o gratuito após alguns dias
- Para produção real, o plano pago R2 custa $0,015/GB de armazenamento + operações
