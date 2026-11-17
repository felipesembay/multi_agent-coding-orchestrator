# Auditoria do estado atual (v1)

Data: 2026-11-17 · Commit base: `83cebe8` + alterações não commitadas (ver §11) · Auditor: Claude

Legenda de cada afirmação:

- **[FATO]** comprovado por leitura de código, execução de teste ou saída de comando.
- **[HIPÓTESE]** plausível, não verificado; exige spike ou teste.
- **[RECOMENDAÇÃO]** proposta de mudança.

## 1. Verificações executadas

| Verificação | Resultado |
|---|---|
| `python -m pytest -q -p no:cacheprovider` com `ORCH_DB` temporário | [FATO] 72 passed, 1 warning (deprecation LangChain serializer) |
| `npx vitest run` em `frontend/` | [FATO] 6 arquivos, 32 testes passando |
| Versões | [FATO] Python 3.9.7, LangGraph 0.6.11, Node 22.18.0 |
| CLIs no PATH | [FATO] `claude` 2.1.92, `codex` 0.166.0, `agy` 1.5.1, `ollama`, `cargo`/`rustc`. Tauri CLI ausente |
| Testes e2e Playwright | Não executados (exigem API e frontend em execução) |
| Chamadas reais a agentes | Não executadas (consumiriam quota) |

## 2. Estrutura

[FATO] Backend Python em `orchestrator/` (≈1.900 linhas), frontend React em `frontend/`, testes Python em `tests/` com agentes mockados, documentação operacional em `docs/execution-manager.md`, CI GitHub Actions somente com pytest em Python 3.9 (`.github/workflows/tests.yml`). Não há `LICENSE`, `AGENTS.md` ou `CLAUDE.md` versionados antes desta sessão.

## 3. LangGraph

- [FATO] `orchestrator/core.py` `graph()` define um `StateGraph(State)` fixo com nós `plan`, `implement`, `review`, `advance`, `finish`, `blocked`. Arestas: plan→implement→review; `decide` → next/retry/blocked; `more` → continue/finish.
- [FATO] `State` é `TypedDict` com `run_id, repo, worktree, scope, plan, task_index, attempts, review, status, error, managed`.
- [FATO] Sem checkpointer. `recursion_limit=250`. Entrada alternativa (`implement`/`review`) usada apenas pelo `resume` legado.
- [FATO] Limite de tentativas por tarefa: `MAX_ATTEMPTS` (padrão 3). Plano limitado a 1–30 tarefas.
- [FATO] O nó `review` executa testes configurados **antes** de chamar o reviewer; teste falho força `approved=false`.

## 4. Adapters de agentes

| Agente | Função | argv real | Saída | Telemetria capturada |
|---|---|---|---|---|
| Claude Code | `core.claude` | `claude -p --permission-mode acceptEdits <prompt>` | texto | [FATO] nenhuma |
| Codex CLI | `core.codex` | `codex exec --sandbox read-only <prompt>` | texto | [FATO] nenhuma |
| Antigravity | `core.antigravity` | `agy --print <prompt> --model <m> --mode plan|accept-edits --output-format json` | JSON; usa `status`, `denied_actions`, `response` | [FATO] nenhuma (demais campos ignorados) |

- [FATO] Seleção por env em `coding_agent()`: `ORCH_PLANNER`, `ORCH_IMPLEMENTER` ∈ {`claude`, `antigravity`}. Reviewer é **sempre Codex**.
- [FATO] Fallback Claude→Antigravity apenas para o Planner, detectado por substrings de erro (`rate limit`, `usage limit`, …). Gera evento `agent_fallback`.
- [FATO] Modelo padrão Antigravity fixo no código: `gemini-4-argon-medium`. Claude e Codex usam o modelo padrão do CLI (sem `--model`).
- [FATO] Planner Claude roda com `acceptEdits`, ou seja, **pode editar arquivos** durante o planejamento. Planner Antigravity usa `--mode plan`.
- [FATO] A proibição de shell para o Implementer existe **apenas no prompt**.
- [FATO, via `--help`] Flags disponíveis e não usadas: Claude `--output-format json|stream-json`, `--model`, `--fallback-model`, `--max-budget-usd`, `--json-schema`, `--allowedTools/--disallowedTools`, `--permission-mode plan`; Codex `--json` (JSONL), `-m`, `-s`, `--output-schema`, `-o`; Agy `--output-format stream-json`, `--json-schema`, `--sandbox`, `--effort`, subcomandos `models` e `acp`.
- [HIPÓTESE] O JSON do Claude inclui `usage` e `total_cost_usd`; o JSONL do Codex inclui eventos de contagem de tokens; o JSON do agy inclui métricas de uso. **Nenhuma dessas estruturas foi verificada nesta sessão** → spike `V2-F0-003`.

### Divergência com o padrão desejado

[FATO] Padrão atual: Planner Claude, Implementer Claude, Reviewer Codex. Padrão desejado pelo produto: Planner Claude, Executor Codex, Reviewer Antigravity. Para isso Codex precisa de modo de escrita (`--sandbox workspace-write`, hoje nunca usado) e Antigravity precisa de modo de revisão com saída estruturada (hoje nunca revisa).

## 5. API FastAPI

- [FATO] `orchestrator/api.py`: `/health`, `/runs`, `/overview`, `/settings`, `/runs/{id}`, `/runs/{id}/events`.
- [FATO] `orchestrator/project_api.py`: `/session`, `/project-policy`, `/projects*`, preflight e início de execução (202).
- [FATO] Middleware `local_security.protect_project_routes` aplica loopback, Host, Origin, CSRF, JSON e limite de 150 kB **somente** a `/session`, `/project-policy` e `/projects*`.
- [FATO] `/runs`, `/runs/{id}`, `/runs/{id}/events`, `/overview`, `/settings`, `/health` não validam Host nem Origin. Payloads de eventos contêm saídas de agentes e trechos de diff; `/settings` expõe o caminho do banco.
- [HIPÓTESE] Uma página web maliciosa poderia ler esses dados via DNS rebinding enquanto a API estiver ativa. → `V2-SEC-001`.
- [FATO] Token CSRF único por processo, entregue por `GET /session` (protegido por Host/Origin).

## 6. Persistência SQLite

[FATO] Um único arquivo (`ORCH_DB`, padrão `~/.local/state/multi-agent-orchestrator/events.db`):

| Tabela | Origem | Papel |
|---|---|---|
| `events` | `core.SCHEMA` | Timeline append-only (`run_id, at, stage, payload` JSON string) |
| `platform_migrations` | migração 1 | Versões aplicadas (1, 2, 3) |
| `repositories`, `projects`, `project_requests`, `project_previews`, `platform_audit` | migração 1 | Catálogo e auditoria |
| `managed_runs` | migração 2 | Fila + lifecycle + config congelada + idempotência + identidade do processo |
| `execution_worker` | migração 2 | Singleton com heartbeat |
| `projects.deleted_at` | migração 3 (WIP) | Exclusão lógica |

- [FATO] Índice único parcial `one_active_run_per_repository` impede dois runs ativos/órfãos no mesmo `git_common_dir`.
- [FATO] Migrações são listas de SQL em `project_store.py` aplicadas em `connection()`; não há ferramenta de migração.
- [FATO] Leituras de dashboard reconstroem resumos em memória lendo **todos** os eventos (`dashboard.read_runs`) a cada requisição.

## 7. Projetos e worktrees

- [FATO] Caminhos validados contra `ORCH_ALLOWED_ROOTS` (sem `..`, symlinks ou diretórios ocultos; `git_common_dir` também autorizado).
- [FATO] Criação de repositório usa descritores `O_NOFOLLOW`, prévia com token e TTL de 600 s.
- [FATO] `core.prepare()` exige repositório limpo e `HEAD`, cria `git worktree add -b agent/<run_id> <base>/<run_id> HEAD`. Nada é removido automaticamente.
- [FATO] Lock advisory `flock` em `<git-common-dir>/orchestrator-execution.lock`, compartilhado com o CLI.

## 8. Worker e processos

- [FATO] `worker.py`: um worker por banco (flock em `<db>.worker.lock`), FIFO serial, um subprocesso `execution_runner` por run em nova sessão, heartbeat a cada 0,25 s, reconciliação de órfãos via `/proc` e dispatch token no ambiente.
- [FATO] O subprocesso herda **todo o `os.environ`** do worker, exceto `GIT_*`; agentes herdam o mesmo ambiente (incluindo eventuais chaves de API).
- [FATO] Dependência de Linux: `/proc`, `boot_id`, `fcntl`, grupos de processos.

## 9. Recuperação

- [FATO] `core.resume()` (somente CLI, runs legados) reconstrói posição a partir de eventos `implementation`/`review`; recusa histórico ambíguo.
- [FATO] Runs gerenciados interrompidos ficam `interrupted`; não há retomada.
- [FATO] Não existe registro de "chamada iniciada": uma chamada de agente interrompida não deixa evento, apenas possíveis alterações na worktree.

## 10. Frontend

- [FATO] React 19, Vite 8, TypeScript 6, Tailwind 4, TanStack Query 5, React Router 7, Radix Slot + CVA (padrão shadcn), Lucide.
- [FATO] Rotas: `/projects`, `/projects/new`, `/projects/:id`, `/overview`, `/executions`, `/executions/:runId`, `/agents`, `/reviews`, `/settings`.
- [FATO] Tokens de cor tonais (`neutral`, `blue`, `green`, `red`, `amber`, escala 100–950) em `frontend/src/styles/theme.css` com variante clara via `data-theme`. Componentes UI locais: apenas `button.tsx`.
- [FATO] Atualização por polling (3 s em runs ativos). Settings somente leitura.
- [FATO] CI não executa testes do frontend.

## 11. Trabalho não commitado no início da sessão

[FATO] `git status`: alterações em backend (`execution_manager.py`, `project_api.py`, `project_store.py`, `projects.py`), testes e frontend; novos `ThemeToggle.tsx`, `DeleteProject.tsx`, `styles/`, testes de tema e exclusão, e2e `theme-and-delete.spec.ts`. Os testes acima passaram **com** esse WIP. Esta sessão não alterou nenhum desses arquivos.

## 12. Matriz implementado / parcial / ausente frente à v2

| Capacidade v2 | Estado | Evidência |
|---|---|---|
| Projetos, solicitações, fila, worker | Implementado | migrações 1–3, `worker.py` |
| Worktree por run, sem merge/push | Implementado | `core.prepare` |
| Config congelada por run | Implementado (env-based) | `managed_runs.config` + digest |
| Escolha de provider por papel | Parcial | só planner/implementer, só claude/antigravity |
| Escolha de modelo | Parcial | só Antigravity |
| Reviewer configurável | Ausente | Codex fixo |
| Abstração de provider/capacidades | Ausente | funções soltas |
| Workflow persistido/editável | Ausente | grafo em código |
| Fallback configurável | Parcial | apenas Planner Claude→Antigravity |
| Tokens/custos | Ausente | — |
| Checkpoints LangGraph | Ausente | — |
| Retomada de run gerenciado | Ausente | `resume` recusa |
| Aprovação humana persistida | Ausente | README "Limitações" |
| Credenciais gerenciadas | Ausente | CLIs autenticados externamente |
| Desktop | Ausente | 3 processos manuais |
| Streaming (SSE/WebSocket) | Ausente | polling |
| Proteção de todas as rotas locais | Parcial | §5 |
| Isolamento de ambiente dos agentes | Ausente | §8 |
| Handoff entre agentes | Ausente | criado nesta sessão (docs) |
