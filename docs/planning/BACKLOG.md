# Backlog v2

Fonte única de status das tarefas. Atualize a linha da tarefa ao iniciar (`doing`) e ao concluir (`done` + evidência: commit/teste). Nunca marque `done` sem evidência.

**Status:** `todo` · `doing` · `blocked` · `review` · `done` · `dropped`
**Prioridade:** P0 (MVP, bloqueante) · P1 (MVP) · P2 (pós-MVP) · P3 (futuro)
**Complexidade** (sem estimativa de horas): S = 1 módulo, poucos testes · M = 2–4 módulos ou migração · L = transversal, novo subsistema · XL = exige ADR/spike adicional
**Perfil:** BE (backend Python) · FE (React) · RS (Rust/Tauri) · SEC · OPS (CI/empacotamento) · HUM (decisão humana)

## F0 — Auditoria e arquitetura

| ID | Título | Status | P | C | Deps | Perfil | Critério de aceite | Testes / evidência |
|---|---|---|---|---|---|---|---|---|
| V2-F0-000 | Auditoria e documentação de planejamento | done | P0 | M | — | BE | `docs/` criado conforme IMPLEMENTATION_PLAN | 72 pytest / 32 vitest inalterados; sessão 2026-11-17 |
| V2-F0-001 | Estabelecer baseline: decidir commit do WIP (tema, exclusão, migração v3) | done | P0 | S | — | HUM | `git status` limpo na branch de desenvolvimento autorizada ou WIP descartado conscientemente | 2026-11-17: baseline dev autorizado; 81 pytest / 32 vitest, build/lint verdes; revisão review_baseline_dev aprovada |
| V2-F0-002 | Revisar ADRs 0001–0010 e responder OPEN_QUESTIONS | blocked | P0 | S | F0-000 | HUM | Cada ADR com status `aceito` ou `rejeitado`; Q1–Q12 respondidas ou adiadas com data | 2026-11-18: Q2–Q12 registradas (Q7 adiada); aceitação/rejeição integral dos ADRs ainda pendente. Revisão documental review_decisions_f0002 aprovada; perguntas respondidas não bloqueiam suas tarefas específicas. |
| V2-F0-003 | Spike de telemetria dos CLIs (Claude, Codex, agy) | todo | P0 | M | F0-002 | BE | Documento `docs/specifications/telemetry/*.md` com formato real por versão; fixtures redigidas | Exige autorização para consumir quota |
| V2-F0-004 | Spike Tauri 2 + WebKitGTK + sidecar Python | todo | P1 | M | F0-002 | RS | Protótipo descartável fora de `master` cumprindo validação do ADR-0002 | Relatório no ADR-0002 |
| V2-F0-005 | Decidir versão de Python e verificar compat `langgraph-checkpoint-sqlite` | done | P0 | S | F0-002 | HUM/BE | Versão-alvo registrada; CI atualizado se mudar | Python 3.12.3 + SqliteSaver round-trip (2 novos; 563 pytest / 54 vitest); CI 3.12 em ubuntu-24.04; revisão review_f0005 aprovada (2026-11-18) |

## F1 — Núcleo extensível + baseline de segurança

| ID | Título | Status | P | C | Deps | Perfil | Critério de aceite | Testes |
|---|---|---|---|---|---|---|---|---|
| V2-CORE-001 | Interface `AgentRuntime` + adapters Claude/Codex/agy sem mudança de comportamento | done | P0 | M | F0-001 | BE | `core.claude/codex/antigravity/coding_agent` delegam aos adapters; argv idêntico | 22 casos de caracterização antes/depois; 6 contratos; 109 pytest verdes; revisão review_core001 (2026-11-17) |
| V2-CORE-002 | `InvocationResult`/`UsageReport` estruturados + evento `agent_call` (provider, modelo, duração) | done | P0 | M | CORE-001 | BE | Todas as chamadas geram `agent_call`; uso `unavailable` até parsers | 130 pytest / 33 vitest; 55 focados; build/lint/docs verdes; revisão review_core002 (2026-11-17) |
| V2-CORE-003 | Registry + `CapabilityManifest` + entry points | done | P0 | S | CORE-001 | BE | `GET /providers` lista built-ins e fake de entry point | 154 pytest / 33 vitest; build/lint/docs verdes; revisão review_core003 (52 testes, 2026-11-17) |
| V2-CORE-004 | Bindings papel→runtime/modelo substituindo leitura direta de env no core | done | P0 | M | CORE-003 | BE | Env vira fonte do preset `legacy-v1`; reviewer configurável internamente | 179 pytest / 33 vitest; 69 focados; build/lint/docs verdes; revisão review_core004 (2026-11-17) |
| V2-SEC-001 | Proteger todas as rotas (Host/loopback + token) | done | P0 | S | — | SEC | CA1 de SECURITY_GOVERNANCE; frontend continua funcionando | 273 pytest / 38 vitest; 9 e2e (2 opt-ins skipped); build/lint/docs verdes; revisão review_sec001 (2026-11-17) |
| V2-SEC-002 | Ambiente de subprocessos por allowlist | done | P0 | S | — | SEC | CA2 de SECURITY_GOVERNANCE | 301 pytest / 38 vitest; /proc de agentes fake, worker e órfãos; 9 e2e (2 skipped); revisão review_sec002 (2026-11-17) |
| V2-SEC-003 | Planner Claude em modo somente leitura (`--permission-mode plan`) | todo | P0 | S | CORE-001 | SEC/HUM | Planner não edita arquivos; plano JSON continua extraível | Teste argv + 1 validação real autorizada |
| V2-SEC-006 | Desabilitar hooks/config insegura do Git em `prepare`/`run_command` | done | P0 | S | — | SEC | CA4 de SECURITY_GOVERNANCE | 323 pytest / 38 vitest; 22 casos Git com controles positivos; build/lint/docs verdes; revisão review_sec006 (69 focados, 2026-11-18) |
| V2-SEC-004 | Matriz de permissões por papel aplicada em argv | todo | P1 | M | CORE-004 | SEC | CA3 de SECURITY_GOVERNANCE | Testes argv por papel/adapter |
| V2-SEC-007 | Auditoria estendida (workflows, providers, credenciais, aprovações) | todo | P1 | S | CORE-003 | BE | Ações listadas em SECURITY §6.6 auditadas sem valores sensíveis | Teste de registros |

## F2 — Workflows configuráveis

| ID | Título | Status | P | C | Deps | Perfil | Critério de aceite | Testes |
|---|---|---|---|---|---|---|---|---|
| V2-WF-001 | Schema `WorkflowDefinition` + validação | done | P0 | S | CORE-003 | BE | Regras §6.2 de WORKFLOW_ENGINE; schema/validation, revisão review_wf001 aprovada | 75 focados; 398 pytest / 38 vitest; build/lint/docs |
| V2-WF-002 | Migração 4: `workflow_definitions`, `workflow_versions`, `provider_configs`, colunas em `managed_runs` | done | P0 | S | WF-001 | BE | Upgrade v3 preserva dados/índices; revisão review_wf002 aprovada | 26 migração; 424 pytest / 38 vitest; build/lint/docs |
| V2-WF-003 | Compilador definição→StateGraph com equivalência ao grafo atual | done | P0 | L | WF-001, CORE-004 | BE | CA1 de WORKFLOW_ENGINE; layout legado e compiler estrito, revisão review_wf003 aprovada | 30 novos; 454 pytest / 38 vitest; build/lint/docs |
| V2-WF-004 | Presets `legacy-v1`, A, B, C (B desabilitado até PROV-001) | done | P0 | S | WF-003 | BE | Catálogo/clones/escolhas por etapa; CLI legacy; B bloqueado; revisão review_wf004 aprovada | 31 novos;485 pytest /38 vitest; build/lint/docs |
| V2-WF-007 | Snapshot de workflow+bindings no run e digest de confirmação | done | P0 | M | WF-002, WF-003 | BE | CA4, snapshot opcional/store/runner íntegro; revisão review_wf007 aprovada | 36 novos;521 pytest /38 vitest; build/lint/docs |
| V2-WF-005 | Codex CLI como executor (`workspace-write`) | todo | P1 | M | SEC-004, F0-002 (Q5) | BE/SEC | Preset A implementa com Codex mockado; flags corretas | argv + integração mockada |
| V2-WF-006 | Antigravity como reviewer com saída JSON validada | todo | P1 | M | CORE-004 | BE | Reviewer agy retorna `{approved,findings,…}` validado | Fixture + integração mockada |
| V2-WF-008 | API de workflows e seleção no início da execução | done | P1 | M | WF-007 | BE/FE | API/seleção versionada com snapshots e readonly; revisão review_wf008 aprovada | 532 pytest /44vitest;11API+6UI novos;9e2e/2skip;build/lint/docs |
| V2-WF-009 | Editor de workflow em lista (MVP) | done | P1 | M | WF-008 | FE | Criar, validar, salvar versão, clonar preset | 534 pytest/54 Vitest;11 E2E,2 skipped; build/lint/docs; revisão review_wf009 aprovada; commit V2-WF-009 em dev |
| V2-WF-010 | Fallbacks configuráveis por etapa | done | P1 | M | WF-003, CORE-002 | BE | CA5: fallback/uso por tentativa persistidos em events; tabela OBS-001 futura | 561 pytest/54 Vitest;27 novos fallback+1 dashboard;11e2e/2skip;build/lint/docs;review_wf010 aprovada;commit V2-WF-010 dev |
| V2-PROV-001 | OpenRouter `ModelProvider` básico (plan/review) + chave no keyring | todo | P1 | M | CORE-003, SEC-005 | BE | CA4 de PROVIDER_SYSTEM | HTTP mock (200/401/402/429/5xx) |
| V2-SEC-005 | Credential store com `keyring` | todo | P1 | M | F0-002 | SEC | Chave salva/lida/removida; nunca no SQLite | Teste com backend de keyring em memória |

## F3 — Observabilidade

| ID | Título | Status | P | C | Deps | Perfil | Critério de aceite | Testes |
|---|---|---|---|---|---|---|---|---|
| V2-OBS-001 | Migração 5 + gravação de `usage_records` | todo | P1 | M | CORE-002 | BE | Toda chamada gera registro (inclusive `unavailable`) | Integração mockada |
| V2-OBS-002 | Parsers de telemetria por CLI | todo | P1 | M | F0-003, OBS-001 | BE | CA1 de TOKEN_ACCOUNTING | Fixtures por versão |
| V2-OBS-003 | Catálogo de preços versionado (manual + import) | todo | P1 | M | OBS-001 | BE | CA4 de TOKEN_ACCOUNTING | Testes de vigência |
| V2-OBS-004 | Estimador local opcional (rotulado) | todo | P2 | S | OBS-001 | BE | Registros `estimated` só com opção ativa | Unitário |
| V2-OBS-005 | Orçamentos run/projeto com warn/block | todo | P2 | M | OBS-003, RES-004 | BE | CA3 de TOKEN_ACCOUNTING | Integração |
| V2-OBS-006 | API de agregações + projeções incrementais | todo | P2 | M | OBS-001 | BE | RNF3 de TOKEN_ACCOUNTING | Teste de desempenho com 10⁵ linhas |
| V2-OBS-007 | Dashboard de custos | todo | P2 | L | OBS-006, DESK-005 | FE | CA2 de TOKEN_ACCOUNTING; UI_UX §3.6 | Vitest de componentes |
| V2-OBS-008 | Uso por run na tela de detalhes | todo | P1 | S | OBS-001 | FE | Aba "Uso" com rótulos de fonte | Vitest |

## F4 — Resiliência e continuidade

| ID | Título | Status | P | C | Deps | Perfil | Critério de aceite | Testes |
|---|---|---|---|---|---|---|---|---|
| V2-RES-001 | Ledger `step_executions` + digest de árvore | todo | P1 | M | WF-003 | BE | Ledger started/completed por nó | Unitário + integração |
| V2-RES-002 | Checkpointer SQLite LangGraph | todo | P1 | M | F0-005, WF-003 | BE | Round-trip do estado | Teste de checkpoint |
| V2-RES-003 | Retomada gerenciada com inspeção | todo | P1 | L | RES-001, RES-002, RES-004 | BE | CA1/CA2 de PERSISTENCE | Crash injection |
| V2-RES-004 | Aprovações humanas persistidas (`approvals`) | todo | P1 | M | WF-002 | BE/FE | Plano/resultado/retomada aprováveis na UI | API + vitest |
| V2-RES-005 | Artefatos do run (`run_artifacts`) | todo | P2 | S | RES-001 | BE | Plano, relatório de teste, revisão e handoff salvos | Unitário |
| V2-RES-006 | SSE para eventos e logs | todo | P2 | M | SEC-001 | BE/FE | CA4 de PERSISTENCE | Teste de stream |
| V2-DOC-002 | Gerador determinístico de handoff por run | todo | P2 | S | RES-005 | BE | Markdown gerado só de eventos/ledger, sem LLM | Snapshot test |

## F5 — Desktop

| ID | Título | Status | P | C | Deps | Perfil | Critério de aceite | Testes |
|---|---|---|---|---|---|---|---|---|
| V2-DESK-001 | Scaffold Tauri 2 em `desktop/` carregando `frontend/dist` | todo | P1 | M | F0-004 | RS | App abre no Ubuntu com UI atual | Build local |
| V2-DESK-002 | `orchestrator/supervisor.py` (porta efêmera, token, API+worker, logs, reinício) | todo | P1 | M | SEC-001 | BE | ADR-0003 itens 2 e 4 | Unitários |
| V2-DESK-003 | Sidecar empacotado | todo | P1 | L | DESK-002, F0-005 | OPS | Binário roda sem venv do desenvolvedor | Smoke em container |
| V2-DESK-004 | Integração token/origem Tauri ↔ API; `api.ts` dual-mode | todo | P1 | S | DESK-001, DESK-002 | FE/RS | CA4 de DESKTOP_APP | Vitest |
| V2-DESK-005 | Tokens semânticos + biblioteca de componentes | todo | P1 | M | — | FE | DESIGN_SYSTEM §2–5 implementado; contraste AA | Vitest + verificação de contraste |
| V2-DESK-006 | Shell UI: sidebar de projetos, topbar com status, painel inferior | todo | P1 | M | DESK-005 | FE | UI_UX §2 | Vitest + e2e web |
| V2-DESK-007 | Grafo de agentes (React Flow, leitura) | todo | P2 | M | WF-007, DESK-005 | FE | UI_UX §3.2 | Vitest |
| V2-DESK-008 | Terminal/logs em tempo real | todo | P2 | M | RES-006 | FE | UI_UX §3.3 | Vitest |
| V2-DESK-009 | Tela Modelos & Providers | todo | P2 | M | CORE-003, PROV-001 | FE | UI_UX §3.4 | Vitest |
| V2-DESK-010 | Configurações editáveis persistidas (substituir `.env` no desktop) | todo | P2 | M | DESK-002 | BE/FE | UI_UX §3.7; auditoria | API + vitest |

## F6 — Integrações e distribuição

| ID | Título | Status | P | C | Deps | Perfil | Critério de aceite | Testes |
|---|---|---|---|---|---|---|---|---|
| V2-DIST-001 | Bundles AppImage + .deb em CI | todo | P2 | L | DESK-003 | OPS | CA1/CA2 de DESKTOP_APP | Smoke de instalação |
| V2-DIST-002 | CI do frontend (lint, build, vitest) | done | P1 | S | — | OPS | Workflow GitHub Actions verde | Job frontend (Node 22, lint, build, vitest) em `.github/workflows/tests.yml`; 564 pytest / 54 vitest; revisão review_dist002 aprovada (2026-11-19) |
| V2-DIST-003 | E2E desktop (tauri-driver) | todo | P3 | L | DIST-001 | OPS | Fluxo mockado no app empacotado | CI |
| V2-DIST-004 | Corrigir imagem do CI Python 3.9 incompatível com ubuntu-latest | done | P0 | S | — | OPS | CI fixa imagem com binário oficial e testes isolados; migração Python separada | Logs Actions44354266781; manifesto3.9.25/22.04; baseline521/38; revisão review_ci_fix aprovada; remoto não reexecutado |
| V2-PROV-002 | OpenRouter: sync de catálogo, preços e parâmetros | todo | P2 | M | PROV-001, OBS-003 | BE | Preços com `source=openrouter_api` e data | HTTP mock |
| V2-PROV-003 | Ollama `ModelProvider` | todo | P3 | S | CORE-003 | BE | Plan/review local com `billing_mode=local` | HTTP mock |
| V2-WF-011 | Editor visual React Flow | todo | P3 | L | WF-009, DESK-007 | FE | Gera o mesmo JSON do editor em lista | Vitest |
| V2-WF-012 | Ramificações e loops controlados | todo | P3 | XL | WF-003, ADR novo | BE | Terminação provada por validação | Property tests |
| V2-SEC-008 | Isolamento de SO (bubblewrap/namespace sem rede) para testes e runtimes | todo | P3 | XL | ADR novo | SEC | Testes rodam sem rede quando habilitado | Integração |
| V2-DOC-001 | Script de verificação de docs (links, IDs do backlog, handoff atualizado) | done | P2 | S | — | BE | `python scripts/check_docs.py` falha em link quebrado ou ID desconhecido | 9 testes específicos; 81 pytest / 32 vitest; revisão Codex review_doc001 em 2026-11-17 |

## Fora do escopo v2 (registrado)
Merge/push/PR automáticos · deploy · multiusuário/autenticação pública · execução hospedada · paralelismo de runs no mesmo worker.
