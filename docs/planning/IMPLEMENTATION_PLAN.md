# Implementation Plan — Multi-Agent Orchestrator v2

> **Ponto de entrada para qualquer agente (Claude, Codex, Antigravity ou humano) que assumir o projeto.**
> Leia este arquivo primeiro. Ele indica o que ler, qual é o estado atual e qual tarefa executar em seguida.

Última atualização: 2026-11-19 · Fase atual: **F2 — Workflows (início)** (Q2–Q12 registradas; revisão integral de ADRs e segurança restantes pendentes) · Autor da sessão: Codex

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
- WIP de tema claro/escuro, exclusão lógica e migração v3 preservado e commitado em `dev`, conforme autorização do operador. Sem merge/deploy/main/master; push dev autorizado em 2026-11-18 concluído até7431745.
- `V2-DOC-001` e `V2-CORE-001..004` concluídas: verificador de documentação, adapters, metadados, registry e bindings por papel com snapshots; comandos/fallback/digests legados preservados.
- `V2-SEC-001` concluída: política local global e token em leituras/escritas, bootstrap /session e liveness /health locais; frontend autenticado.
- `V2-SEC-002` concluída: ambiente por allowlist de escopo, nomes congelados no snapshot/digest e marcador de supervisão preservado.
- `V2-SEC-006` concluída: política Git compartilhada com hooks/fsmonitor/conversores desligados e recusa de filtros executáveis, inclusive condicionais por branch.
- `V2-WF-001` concluída: schema versionado e validação pura de estrutura/bindings; sem execução/migração/API/presets.
- `V2-WF-002` concluída: migração aditiva v4 para workflows/provider_configs, novas colunas anuláveis e versões imutáveis; sem integração ao executor/API ou seeds.
- `V2-WF-003` concluída: compilador LangGraph com executores host obrigatórios, limites/envelopes; core.graph delega ao layout privado legado, com topologia/callbacks/pontos de entrada preservados.
- `V2-WF-004` concluída: catálogo/clonagem/escolhas por etapa, default UI A/CLIlegacy e bloqueio B até PROV-001; execução real continua dependente das capacidades/permissões e UI futuras.
- `V2-WF-007` concluída: snapshots internos opcionais e digests no run, store versionado e runner íntegro usando configuração congelada. base para a seleção HTTP/UI da WF-008.
- `V2-WF-008` concluída: endpoints/versionamento/validate/presets e StartExecution com versões/providers/modelos; compatibilidade legada e disponibilidade real preservadas.
- `V2-DIST-004` corrige CI localmente: Python3.9 indisponível no ubuntu-latest26.04 antes dos testes; imagem22.04 fixada. Actions remoto aguarda push/run; Python3.12 fica em F0-005.
- `V2-WF-009` concluída: editor em lista, validação ao vivo, cópias e versões imutáveis; bindings continuam por run.
- `V2-WF-010` concluída: alternativas ordenadas por erro tipado seguro, snapshots de todos os candidatos e registros de uso no event store por chamada; tabela/contabilidade completa OBS-001 futura.
- `V2-F0-005` concluída: migração para Python 3.12.3 validada localmente, `langgraph-checkpoint-sqlite` (`SqliteSaver`) testado com round-trip em `StateGraph`, CI atualizado para Python 3.12 em `ubuntu-24.04`.
- Incrementos Antigravity: SEC-004/WF-005/006, DIST-002, OBS-001, SEC-005 e RES-001 concluídos; SEC-003 em review pela evidência real pendente. Python3.12 e CI atualizados; OBS-001 inclui usage_records/migração5.
- RES-002 concluída: SqliteSaver separado/thread_id por run/durability sync e guard de não retomada;675pytest/54Vitest/build/lint/docs, revisão aprovada.
- Baseline desta sessão: **624 pytest /54 Vitest**. PROV-001 concluída:666 pytest/54 Vitest,11E2E/2skip e build/lint/docs; resultados detalhados em CURRENT_STATE. Nenhum agente real/API de geração acionado.

## 5. Próximas tarefas

1. Sequência PROV-001/RES-002/SEC-007/OBS-003 concluída e revisada nesta sessão. Validação final721pytest/54Vitest,11E2E/2opt-ins skipped, build/lint/docs verdes. Nenhuma API de geração real/credencial alterada; commits locais dev, sem push.
2. Próxima recomendada **V2-RES-004**, depois **V2-RES-003**, ou alternativas liberadas OBS-008/PROV-002 conforme prioridade. Uma tarefa por vez; nenhuma iniciada automaticamente após a sequência.
3. **V2-SEC-003** em review: validação real exigida pendente, não opcional. **V2-F0-002** blocked pela revisão formal dos ADRs. Não reabrir questões já respondidas nem inventar evidência.

Detalhes e critérios: [CURRENT_STATE](../handoff/CURRENT_STATE.md), [NEXT_STEPS](../handoff/NEXT_STEPS.md) e [guia Antigravity](../handoff/ANTIGRAVITY_HANDOFF.md).

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
