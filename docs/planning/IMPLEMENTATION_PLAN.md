# Implementation Plan — Multi-Agent Orchestrator v2

> **Ponto de entrada para qualquer agente (Claude, Codex, Antigravity ou humano) que assumir o projeto.**
> Leia este arquivo primeiro. Ele indica o que ler, qual é o estado atual e qual tarefa executar em seguida.

Última atualização: 2026-11-17 · Fase atual: **F1 — Núcleo extensível + segurança** (decisões F0 pendentes) · Autor da sessão: Codex

## 1. Regra de ouro

Nada descrito em `docs/specifications/`, `docs/design/` ou `docs/planning/` está implementado, a menos que [CURRENT_STATE.md](../handoff/CURRENT_STATE.md) e o [BACKLOG](BACKLOG.md) digam `done` com evidência (commit, teste). O README descreve o comportamento atual; estes documentos descrevem o destino.

## 2. Ordem de leitura

| Ordem | Arquivo | Quando ler |
|---|---|---|
| 1 | [handoff/CURRENT_STATE.md](../handoff/CURRENT_STATE.md) | Sempre. Estado do repositório e da última sessão |
| 2 | [handoff/NEXT_STEPS.md](../handoff/NEXT_STEPS.md) | Sempre. Próxima tarefa e comandos |
| 3 | [handoff/AGENT_HANDOFF.md](../handoff/AGENT_HANDOFF.md) | Sempre. Protocolo obrigatório de início e fim de sessão |
| 4 | [planning/BACKLOG.md](BACKLOG.md) | Para localizar a tarefa, dependências e critérios de aceite |
| 5 | Especificação da área da tarefa | Ver tabela §3 |
| 6 | ADRs citados pela especificação | Antes de mudar uma decisão |
| 7 | [architecture/CURRENT_STATE_AUDIT.md](../architecture/CURRENT_STATE_AUDIT.md) | Para entender o código existente sem relê-lo inteiro |

Não é necessário ler toda a pasta `docs/`. Leia apenas a especificação da área em que vai trabalhar.

## 3. Mapa de áreas

| Prefixo da tarefa | Área | Especificação | ADRs principais |
|---|---|---|---|
| `V2-F0` | Auditoria, spikes, decisões | [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) | — |
| `V2-CORE` / `V2-PROV` | Provedores, adapters, papéis | [PROVIDER_SYSTEM.md](../specifications/PROVIDER_SYSTEM.md) | [0001](../architecture/DECISIONS/ADR-0001-evoluir-nao-reescrever.md), [0004](../architecture/DECISIONS/ADR-0004-model-provider-vs-agent-runtime.md) |
| `V2-WF` | Workflows configuráveis | [WORKFLOW_ENGINE.md](../specifications/WORKFLOW_ENGINE.md) | [0005](../architecture/DECISIONS/ADR-0005-workflow-como-dado.md) |
| `V2-OBS` | Tokens, custos, orçamento | [TOKEN_ACCOUNTING.md](../specifications/TOKEN_ACCOUNTING.md) | [0006](../architecture/DECISIONS/ADR-0006-contabilidade-de-uso.md) |
| `V2-RES` | Checkpoints, recuperação, aprovação | [PERSISTENCE.md](../specifications/PERSISTENCE.md) | [0007](../architecture/DECISIONS/ADR-0007-checkpoints-e-idempotencia.md) |
| `V2-DESK` / `V2-DIST` | Desktop, design, empacotamento | [DESKTOP_APP.md](../specifications/DESKTOP_APP.md), [DESIGN_SYSTEM.md](../design/DESIGN_SYSTEM.md), [UI_UX.md](../design/UI_UX.md) | [0002](../architecture/DECISIONS/ADR-0002-tauri-2-desktop.md), [0003](../architecture/DECISIONS/ADR-0003-ciclo-de-vida-do-backend.md) |
| `V2-SEC` | Segurança e governança | [SECURITY_GOVERNANCE.md](../specifications/SECURITY_GOVERNANCE.md) | [0008](../architecture/DECISIONS/ADR-0008-credenciais-no-keyring.md), [0009](../architecture/DECISIONS/ADR-0009-seguranca-local.md) |
| `V2-DOC` | Documentação e handoff | [AGENT_HANDOFF.md](../handoff/AGENT_HANDOFF.md) | [0010](../architecture/DECISIONS/ADR-0010-handoff-no-repositorio.md) |

## 4. Estado atual resumido

- v1 funcional preservada: projetos, solicitações, fila SQLite, worker separado, LangGraph linear e worktrees Git. Baseline testado e revisado em `dev`: `f8e6949`.
- WIP de tema claro/escuro, exclusão lógica e migração v3 preservado e commitado em `dev`, conforme autorização do operador. Sem merge/push/main/master.
- `V2-DOC-001` e `V2-CORE-001` concluídas: verificador de documentação e extração dos adapters CLI com contratos mínimos `AgentRuntime`, sem mudança de comportamento.
- Validação: **109 pytest / 32 vitest**, build/lint e documentação verdes (2026-11-17). Nenhum agente CLI real executado; E2E não executado.

## 5. Próxima tarefa

1. **`V2-CORE-002`** — completar `InvocationResult`/`UsageReport` e evento `agent_call`; uso sempre `unavailable` até parsers verificados. Depende só de CORE-001, já concluída.
2. **`V2-F0-002`** — pendente de revisão humana dos ADRs e de [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md). Não assumir respostas; bloquear apenas tarefas dependentes.
3. Depois: CORE-003 registry/capabilities ou tarefas de segurança independentes, uma por vez.

Detalhes e comandos: [NEXT_STEPS.md](../handoff/NEXT_STEPS.md).

## 6. Invariantes que nenhuma tarefa pode quebrar sem ADR

1. HTTP nunca executa workflow dentro da requisição; o worker separado executa.
2. Toda execução roda em Git worktree própria; nenhum merge, push ou deploy automático.
3. Configuração de execução é congelada por run (hoje `managed_runs.config` + digest).
4. Aprovação automática do reviewer não é aprovação humana.
5. Eventos existentes e endpoints legados (`/runs`, `/runs/{id}/events`) continuam compatíveis.
6. Agentes reais não são chamados em testes automatizados; usar mocks.
7. Credenciais nunca em texto puro no SQLite, em logs ou em eventos.
8. Documentação de handoff atualizada ao fim de cada sessão ([AGENT_HANDOFF.md](../handoff/AGENT_HANDOFF.md)).

## 7. Comandos de verificação do baseline

```bash
source .venv/bin/activate
ORCH_DB="$(mktemp -d)/events.db" python -m pytest -q -p no:cacheprovider
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run lint
```
