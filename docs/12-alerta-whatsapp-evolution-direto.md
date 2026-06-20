# Todo - Alerta de WhatsApp direto pela Evolution API

## Avaliação

- O uso do n8n não é necessário para o envio do alerta via WhatsApp.
- A Evolution API já expõe os endpoints necessários para:
  - consultar instâncias;
  - conectar/pairar a instância;
  - enviar texto e mídia.
- Para o fluxo do projeto, a solução mais simples é o backend do `monitoramento` chamar a Evolution API diretamente.
- O n8n deve ficar fora deste escopo.

## Objetivo

Implementar alertas de placa por WhatsApp no sistema `monitoramento` usando apenas o backend FastAPI e a Evolution API da VPS.

## Escopo funcional

- Enviar alerta quando uma placa monitorada for detectada.
- Incluir no alerta:
  - placa detectada;
  - data e hora;
  - confiança;
  - câmera;
  - local;
  - imagem/frame capturado quando existir.
- Registrar tentativa de envio e status por canal.
- Manter o fluxo atual de e-mail funcionando.
- Garantir isolamento por `client_id`.
- Permitir configuração completa pelo administrador via UI do sistema.

## Integração Evolution

- Base URL: `http://192.168.0.115:8081`
- Instância ativa observada na VPS: `whatsapp`
- API key já existente na VPS, usada pelo backend.
- As credenciais e parâmetros operacionais devem ser gerenciáveis pela interface administrativa, sem depender de edição manual do `.env` em produção.
- Configurações mínimas esperadas na UI:
  - Evolution base URL;
  - nome da instância;
  - API key/token;
  - status/ativo do canal WhatsApp;
  - número de destino por placa monitorada;
  - opção de teste de envio.

## Fase 1. Backend e modelo de dados

- [ ] Confirmar/ajustar `WHATSAPP_EVOLUTION_INSTANCE_NAME=whatsapp` em todos os ambientes relevantes.
- [ ] Validar `WHATSAPP_EVOLUTION_API_KEY`, `WHATSAPP_EVOLUTION_BASE_URL` e timeout.
- [ ] Persistir configurações de WhatsApp em tabela própria para leitura/escrita pela UI de admin.
- [ ] Garantir que `alert_whatsapp` existe no modelo `MonitoredPlate` e nos schemas.
- [ ] Garantir que `AlertChannel` possui o valor `whatsapp`.
- [ ] Implementar serviço de WhatsApp direto na Evolution API.
- [ ] Enviar texto simples quando não houver frame.
- [ ] Enviar mídia quando houver imagem disponível.
- [ ] Fazer deduplicação por ocorrência/canal para não reenviar.
- [ ] Registrar status `sent` / `failed` em `AlertSent`.

## Fase 2. Payload e formatação

- [ ] Criar payload rico com:
  - placa;
  - confiança;
  - câmera;
  - local;
  - data/hora;
  - `image_url` quando houver;
  - `image_base64` quando necessário para mídia.
- [ ] Normalizar número para formato E.164/numérico aceito pela Evolution.
- [ ] Criar legenda curta e legível para a mídia.
- [ ] Definir fallback para texto caso a imagem falhe.

## Fase 3. APIs e rotas

- [ ] Criar endpoints administrativos para ler e atualizar as configurações do canal WhatsApp.
- [ ] Proteger os endpoints com autenticação e autorização de admin.
- [ ] Expor endpoint de teste de conexão com a Evolution para o admin validar credenciais.
- [ ] Atualizar rota de placas monitoradas para aceitar `alert_whatsapp`.
- [ ] Manter isolamento por cliente em todas as consultas e envios.
- [ ] Verificar que o gatilho de alerta continua sendo a ocorrência criada pelo worker.
- [ ] Se necessário, expor endpoint de teste interno para validar envio WhatsApp em ambiente controlado.

## Fase 4. Frontend

- [ ] Criar seção de configuração WhatsApp no painel administrativo.
- [ ] Permitir editar base URL, instância, token e estado do canal pela UI.
- [ ] Adicionar validação em tempo real dos campos administrativos.
- [ ] Adicionar botão de testar conexão / enviar mensagem de teste.
- [ ] Exibir campo opcional de WhatsApp no cadastro/edição de placa.
- [ ] Validar número em tempo real no formulário.
- [ ] Exibir WhatsApp nas placas monitoradas quando configurado.
- [ ] Manter estados de loading, error e empty state.
- [ ] Atualizar `frontend/src/types/index.ts`.

## Fase 5. Infra e ambiente

- [ ] Atualizar `.env.example` e `.env.prod.example`.
- [ ] Ajustar `.env.prod` na VPS para apontar para a instância correta.
- [ ] Verificar se a instância `whatsapp` está conectada na Evolution.
- [ ] Se a instância estiver desconectada, finalizar a conexão via QR/pairing code.

## Fase 6. Testes

- [ ] Criar/ajustar testes do fluxo de alerta WhatsApp.
- [ ] Testar deduplicação.
- [ ] Testar envio sem imagem.
- [ ] Testar envio com imagem.
- [ ] Rodar `pytest backend/tests/ -v`.

## Fase 7. Deploy e validação

- [ ] Commitar as mudanças.
- [ ] Fazer push.
- [ ] Atualizar a VPS com backend/frontend.
- [ ] Validar o envio real do alerta.
- [ ] Verificar logs da Evolution e do backend.

## Critérios de aceite

- O sistema envia alerta via WhatsApp sem n8n.
- O alerta contém dados úteis e frame quando disponível.
- O status do envio é registrado.
- O fluxo de e-mail permanece funcionando.
- O deploy na VPS fica alinhado com a instância `whatsapp`.
