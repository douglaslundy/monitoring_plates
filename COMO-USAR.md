# Como usar esta pasta com o Claude Code

## Passo 1 — Instale o Claude Code (só uma vez)
Abra o terminal e rode:
```
npm install -g @anthropic-ai/claude-code
```

## Passo 2 — Prepare a pasta do projeto
1. Coloque esta pasta inteira (`monitoramento-transito/`) onde quiser no seu computador
2. Abra o terminal dentro desta pasta

## Passo 3 — Inicie o Claude Code
```
claude
```
Na primeira vez, ele vai pedir para fazer login com sua conta Anthropic.

O Claude Code vai ler o arquivo `CLAUDE.md` automaticamente e já vai entender todo o projeto.

## Passo 4 — Comece o desenvolvimento
Abra o arquivo `docs/01-estrutura-base.md`, copie todo o conteúdo e cole no Claude Code.

Aguarde terminar. Confira o checklist no final do arquivo. Só então abra o próximo.

## Ordem das etapas
| Arquivo | O que faz |
|---------|-----------|
| docs/01-estrutura-base.md | Cria toda a estrutura de pastas e Docker |
| docs/02-banco-autenticacao.md | Banco de dados e login |
| docs/03-clientes-usuarios-planos.md | Gestão de clientes e planos |
| docs/04-cameras.md | Cadastro de câmeras e agente local |
| docs/05-ocr-processamento.md | Reconhecimento de placas |
| docs/06-busca-ocorrencias.md | Busca e alertas |
| docs/07-interface-polimento.md | Interface final |
| docs/08-testes.md | Testes automatizados |
| docs/09-deploy.md | Deploy na nuvem |

## Dica importante
Se uma sessão no Claude Code ficar muito longa (mais de 30 minutos), rode `/clear` para
limpar o contexto. O Claude vai reler o CLAUDE.md automaticamente e continuar de onde parou.
