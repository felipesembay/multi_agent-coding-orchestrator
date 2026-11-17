# Componentes — atual e proposto

Legenda de estado: **existe** (código atual), **muda** (existe e será alterado), **novo** (não existe).

## Backend Python (`orchestrator/`)

| Componente | Arquivo atual | Estado | Responsabilidade v2 | Tarefas |
|---|---|---|---|---|
| Motor / grafo | `core.py` | muda | Grafo fixo vira saída do compilador de workflow; `prepare`, `event`, `run_command` permanecem | V2-WF-003 |
| Adapters CLI | `core.py` (`claude`, `codex`, `antigravity`, `coding_agent`) | muda → move | Viram `providers/runtimes/{claude_code,codex_cli,antigravity}.py` atrás de `AgentRuntime` | V2-CORE-001/002 |
| Contratos de provider | — | novo | `providers/base.py`: `AgentRuntime`, `ModelProvider`, `CapabilityManifest`, `InvocationRequest`, `InvocationResult`, `UsageReport` | V2-CORE-001/003 |
| Registry | — | novo | `providers/registry.py`: built-ins + entry points `orchestrator.providers` | V2-CORE-003 |
| Política de papéis | — | novo | `policy/roles.py`: matriz read/write/exec por papel → flags de CLI | V2-SEC-004 |
| Workflow schema | — | novo | `workflows/schema.py` (Pydantic), `validation.py`, `presets.py` | V2-WF-001/004 |
| Compilador | — | novo | `workflows/compiler.py`: definição → `StateGraph` | V2-WF-003 |
| Store de workflows | — | novo | `workflows/store.py` + migração 4 | V2-WF-002 |
| Execution Manager | `execution_manager.py` | muda | Configuração deixa de ser só env: snapshot de workflow + bindings | V2-WF-007 |
| Runner | `execution_runner.py` | muda | Recebe snapshot; não mais mapeia env por papel | V2-WF-007 |
| Worker | `worker.py` | muda | Ambiente por allowlist; retomada gerenciada | V2-SEC-002, V2-RES-003 |
| Persistência | `project_store.py` | muda | Novas migrações (4+); possível extração para `migrations/` | V2-WF-002, V2-OBS-001, V2-RES-001 |
| Contabilidade | — | novo | `accounting/{usage,pricing,budget,estimator}.py` | V2-OBS-* |
| Checkpoints / ledger | — | novo | `resilience/{checkpointer,ledger,recovery}.py` | V2-RES-* |
| Credenciais | — | novo | `secrets/store.py` (keyring) | V2-SEC-005 |
| Segurança HTTP | `local_security.py` | muda | Todas as rotas; token bearer para desktop | V2-SEC-001, V2-DESK-004 |
| API | `api.py`, `project_api.py` | muda | Rotas de workflows, providers, uso, aprovações, SSE | V2-WF-008, V2-OBS-006, V2-RES-004/006 |
| Supervisor desktop | — | novo | `supervisor.py`: sobe API + worker, porta efêmera, logs | V2-DESK-002 |
| Dashboard read model | `dashboard.py` | muda | Projeções incrementais em vez de reler todos os eventos | V2-OBS-006 |
| Handoff de run | — | novo | `handoff/generator.py`: Markdown determinístico a partir de eventos | V2-DOC-002 |
| CLI | `cli.py` | mantém | `--workflow`/`--preset` opcional | V2-WF-004 |

## Frontend (`frontend/`)

| Componente | Estado | Responsabilidade v2 |
|---|---|---|
| `styles/theme.css` | muda | Tokens tonais existentes + camada semântica ([DESIGN_SYSTEM.md](../design/DESIGN_SYSTEM.md)) |
| `components/ui/*` | muda | Biblioteca completa (Badge, Card, Tabs, Dialog, Table, Tooltip, Select, Toast, Kbd, StatusDot) |
| `components/layout/Layout.tsx` | muda | Shell desktop: sidebar de projetos, topbar, painel inferior de terminal |
| `features/Workflows*` | novo | Lista/editor de workflows e presets |
| `features/Providers*` | novo | Gerenciamento de modelos e credenciais |
| `features/Usage*` | novo | Dashboard de tokens e custos |
| `features/RunGraph*` | novo | Visualização gráfica dos agentes (React Flow, leitura) |
| `features/Terminal*` | novo | Logs em tempo real via SSE |
| `lib/api.ts` | muda | Base URL dinâmica e token (desktop) |

## Desktop (`desktop/`, novo)

| Componente | Responsabilidade |
|---|---|
| `desktop/src-tauri/` | Projeto Tauri 2 (Rust): janela, tray, spawn do sidecar, comando `backend_info` (porta + token) |
| `desktop/sidecar/` | Spec PyInstaller (ou alternativa decidida no spike) |
| `desktop/tauri.conf.json` | Bundles AppImage e .deb, CSP, allowlist de capabilities Tauri |
