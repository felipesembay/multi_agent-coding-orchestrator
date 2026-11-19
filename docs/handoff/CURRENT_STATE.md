# Estado atual

Atualizado: 2026-11-19 · Por: Codex (V2-SEC-007)

## Repositório
- Branch `dev`; commits testados/revisados autorizados pelo operador. Sem merge/deploy/main/master. Push solicitado pelo operador em 2026-11-18 concluído até 7431745 em origin/dev; sem force/main/master. Commits WF-007 (6f1c167), CI-DIST-004 (feb4caf), WF-008 (58051a2), WF-009 (1d05736), WF-010 (2986229), F0-005 (a85d13f), DIST-002 (57bacaf), SEC-003 (db340b4), SEC-004 (0ec638d), WF-005 (dd172fb), WF-006 (6c387d4), OBS-001 (09ce461), SEC-005 (76d37bd) e RES-001 ficam locais; nenhum novo push solicitado.
- Baseline `f8e6949`; CORE-001..004 em `87a034f`, `56e44d2`, `6737c2f`, `db12642`. Histórico remoto dev atualizado até 7431745 nesta sessão.
- SEC-001 `8d94e7d`, SEC-002 `065d9ed`, SEC-006 `7ac3634`, WF-001 `caee20e`, WF-002 `fc93cd1` locais. WF-003 `1474f4b`. Registro parcial F0-002 em `588c6db`. WF-004 em `7431745` (já em origin/dev). WF-007 em `6f1c167`, CI-DIST-004 em `feb4caf`, WF-008 em `58051a2`, WF-009 em `1d05736`, WF-010 em `2986229`, F0-005 em `a85d13f`, DIST-002 em `57bacaf`, SEC-003 em `db340b4`, SEC-004 em `0ec638d`, WF-005 em `dd172fb`, WF-006 em `6c387d4`, OBS-001 em `09ce461`, SEC-005 em `76d37bd`.
- WIP original de tema/exclusão/migração v3 preservado no baseline. Nenhum WIP externo identificado.

## Estado atual autoritativo — 2026-11-19

- PROV-001 concluída: OpenRouter de texto para plan/review integrado a registry/snapshot/host/keyring/usage_records; API mockada, sem acesso do modelo ao sistema de arquivos.666 pytest/54 Vitest,11 E2E/2 opt-ins skipped, build/lint/docs verdes. review_prov001 aprovada após corrigir uso em saída inválida, ledger, contexto e sessão D-Bus exclusiva do runner.
- SEC-003 em review por validação real exigida pendente, sem dispensa explícita. SEC-004 continua done com aprovação humana. Passagens antigas abaixo são marcos históricos e não substituem este estado/BACKLOG.
- Próxima sequência autorizada: RES-002, SEC-007, OBS-003, uma tarefa por vez. Sem push/merge/deploy; commit local dev autorizado. Nenhuma API de geração/CLI real ou alteração de credencial real nesta sessão.

## Implementado
- **RES-001 concluída:** criados `orchestrator/resilience/digest.py` (`compute_tree_digest` sobre `git status --porcelain=v2`, `git diff --no-ext-diff HEAD` e hashes de arquivos não rastreados limitados, além de `current_git_head`) e `orchestrator/resilience/ledger.py` (`StepLedger`, `start_step_execution`, `complete_step_execution`, `fail_step_execution`, `list_step_executions`, `next_step_attempt`), integrados ao executor de workflows (`workflows/execution.py`) e vinculados a `usage_records.step_execution_id`. Retomada gerenciada não foi adiantada (permanece em `V2-RES-002`/`003`). Novos testes em `tests/workflows/test_step_ledger.py` (4 casos). Evidência: **624 pytest / 54 Vitest**, build/lint/docs verdes; revisão independente `review_res001` aprovada.
- **SEC-005 concluída:** `keyring>=24,<26` adicionado a `requirements.txt` e módulo `orchestrator/secrets/store.py` implementado com `CredentialStore`, `InMemoryKeyringBackend` e helpers `bind_provider_credential`/`remove_provider_credential`. Recusa backends `fail`/`null` (falha fechada com `KeyringUnavailableError` sem cair para arquivo em texto puro), grava apenas `credential_ref` (`multi-agent-orchestrator:<adapter>:<config_id>`) em `provider_configs.credential_ref` com auditoria `credential.set`/`credential.removed` sem valor sensível. Novos testes em `tests/security/test_credential_store.py` (6 casos, incluindo varredura binária do arquivo SQLite confirmando ausência do segredo-sentinela). Evidência: **620 pytest / 54 Vitest**, build/lint/docs verdes; revisão independente `review_sec005` aprovada.
- **OBS-001 concluída:** Migração 5 (`ACCOUNTING_MIGRATION` em `project_store.py`) adiciona as tabelas `step_executions`, `price_catalog_versions`, `price_entries`, `usage_records`, `budgets` e `budget_events` com constraints SQLite (incluindo invariante `token_source='unavailable'` com contagens/custos `NULL` e `raw_usage <= 8192` bytes JSON). Criado `orchestrator/accounting/usage.py` com redação recursiva de chaves sensíveis (`redact_raw_usage`) e gravação idempotente por `call_id` (`record_usage`), integrado tanto ao caminho legado (`core._record_agent_call`) quanto ao host de workflows estritos (`workflows/execution.py`) sem duplicar chamadas ou perder `retry_of`. Novos testes em `tests/workflows/test_usage_records.py` (4 casos). Evidência: **614 pytest / 54 Vitest**, build/lint/docs verdes; revisão independente `review_obs001` aprovada.
- **WF-006 concluída:** `AntigravityRuntime` passa a declarar `Capability.REVIEW` e `Capability.STRUCTURED_OUTPUT` e, quando invocado como `reviewer` (`--mode plan`), extrai e valida estritamente o payload JSON `{approved: bool, findings: list[str], test_suggestions?: list[str]}`, preenchendo `InvocationResult.structured` e recusando texto livre ou tipos inválidos. Novos testes em `tests/workflows/test_antigravity_reviewer.py` (12 casos). Evidência: **610 pytest / 54 Vitest**, build/lint/docs verdes; revisão independente `review_wf006` aprovada.
- **WF-005 concluída:** `CodexCliRuntime` passa a declarar `Capability.CODE_EDIT` e `Capability.CODE_EXEC` e `permission_modes=['read_only', 'workspace_write']` (mantendo `verified=False` até spike/validação real para não promover execução real sem verificação), executando `['codex', 'exec', '--sandbox', 'workspace-write', req.prompt]` quando invocado como `implementer` com `workspace_write`. Verificado em `codex exec --help` (v0.166.0) que `--sandbox` aceita apenas `read-only`, `workspace-write` e `danger-full-access` (não há modo de edição sem shell no CLI). Novos testes em `tests/workflows/test_codex_executor.py` comprovam `argv` e execução end-to-end do Preset A (`default-v2`) com adapters mockados. Evidência: **598 pytest / 54 Vitest**, build/lint/docs verdes; revisão independente `review_wf005` aprovada.
- **SEC-004 concluída:** criado `orchestrator/policy/roles.py` aplicando a matriz autoritativa de permissões por papel (`planner` e `reviewer` → somente `read_only`; `implementer` → somente `workspace_write`; `documenter` → `read_only` ou `workspace_write`) e construtores determinísticos de `argv` para os três adapters (`ClaudeCodeRuntime` adiciona `--disallowedTools Bash` em `workspace_write`, `AntigravityRuntime` usa `--mode plan|accept-edits`, `CodexCliRuntime` usa `--sandbox read-only|workspace-write`). Novos testes em `tests/security/test_role_argv.py` (23 casos). Evidência: **590 pytest / 54 Vitest**, build/lint/docs verdes. Revisão humana (§15) aprovada pelo operador em 2026-11-19.
- **SEC-003 implementada, em review:** `ClaudeCodeRuntime` passa a suportar `permission_modes=['read_only', 'workspace_write']`, mapeando `read_only` → `--permission-mode plan` e `workspace_write` → `--permission-mode acceptEdits`. `bindings.py` remove a exceção legada que permitia `planner` com `workspace_write` no Claude, exigindo `read_only` em todos os planners e reviewers. Patch point legado `core.claude` preservado. Novos testes em `tests/security/test_planner_readonly.py` confirmam `argv`, recusa de `workspace_write` no planner e extração de JSON (raw e cercado por markdown). Evidência: **567 pytest / 54 Vitest**, build/lint/docs verdes. Revisão humana aprovada pelo operador em 2026-11-19; a validação real com o Claude CLI (Q10) não foi executada (pendência opcional).
- **DIST-002 concluída:** job `frontend` (Ubuntu 24.04, Node 22, cache `npm`, `npm --prefix frontend ci`, `lint`, `build`, `test`) adicionado a `.github/workflows/tests.yml`; teste de contrato do workflow CI adicionado em `tests/test_python_checkpoint_compat.py`. Evidência: **564 pytest / 54 Vitest**, build/lint/docs verdes; revisão independente `review_dist002` aprovada.
- **F0-005 concluída:** ambiente `.venv` migrado para Python 3.12.3 (auto-contido no workspace, removendo symlink externo de Python 3.9.7), `langgraph-checkpoint-sqlite>=2,<4` adicionado a `requirements.txt`, CI `.github/workflows/tests.yml` atualizado para Python 3.12 em `ubuntu-24.04` e novo teste `tests/test_python_checkpoint_compat.py` validando runtime `>=3.12` e round-trip persistente de `SqliteSaver` com `StateGraph`. Evidência: **563 pytest / 54 Vitest**, build/lint/docs verdes, zero warnings do LangGraph em Python 3.12; revisão independente `review_f0005` aprovada. Retomada gerenciada não foi adiantada (permanece em `V2-RES-002`/`003`).
- **WF-010 concluída:** fallbacks ordenados com erro tipado/no-effects, candidatos congelados/validados, limites cumulativos, IDs de chamadas e uso persistido no event store; sem migração OBS-001 antecipada. Guia geral Antigravity criado.561 pytest/54 Vitest,11E2E/2skip,build/lint/docs verdes; revisão review_wf010 aprovada; commit local dev, sem push.
- **WF-009 concluída:** editor `/workflows`, etapas opcionais/reordenação/limites, cópias e histórico de versões imutáveis, validação estrutural ao vivo sem bindings. URL fixa versão-base e refresh com falha preserva rascunhos; primeiro teste sincroniza política. Evidência:534 pytest/54 Vitest,11 E2E/2 opt-ins skipped, build/lint/docs verdes; revisão independente review_wf009 aprovada. Commit local autorizado em dev; sem push.
- v1 preservada: worker separado, fila SQLite, worktrees/locks, idempotência e contratos legados. DOC-001 verificador de documentação concluído.
- CORE-001..004: adapters/registry/manifestos, resultados com uso desconhecido honesto, bindings por papel e snapshots/digests compatíveis. Defaults Claude/Claude/Codex e fallback exato preservados.
- SEC-001: política HTTP global Host/peer/origem e tokens em leituras/escritas; bootstrap local /session e liveness /health. Frontend autenticado.
- SEC-002: ambiente por nomes/escopo e extensões opcionais congeladas por nome no snapshot/digest. Valores não persistidos; marcador de despacho preservado para detectar órfãos.
- SEC-006: política Git compartilhada, hooks/fsmonitor/conversores desligados e filtros executáveis recusados, inclusive condicionais por branch. Repositórios com esses filtros não suportados. Git de ferramentas externas não é interceptado; não é sandbox de SO. Registro recusado após worktree add pode deixar worktree/branch vazia para inspeção.
- **WF-001:** `orchestrator/workflows/schema.py` contém WorkflowDefinition v1, união discriminada de seis tipos de etapa, limites/aprovação e bindings separados com parâmetros/fallbacks. `validation.py` valida estrutura e providers já habilitados, sem probes/invocações/imports de plugins.
- Plano primeiro/único, bloco per_task contíguo, retorno somente review→implement anterior no mesmo bloco com tentativas limitadas. Capacidades mínimas por tipo, permissões por papel, escrita só com runtime code_edit verificado; fallback inclui todas as capacidades primárias. Erros Pydantic por campo; API 422 futura em WF-008.
- Faixas complementares do contrato documentadas em WORKFLOW_ENGINE §6.2.1: 100 etapas declaradas, 10000 passos totais, 86400 s, 20 tentativas. `documenter` é o papel de document; escrita também verificada. Nome legacy-v1 não contorna validação.
- **WF-002:** migração aditiva v4 entregue em project_store.py, com três tabelas novas, três colunas managed_runs anuláveis, FK/índice de workflow, JSON/digests básicos e triggers de imutabilidade contra update/delete/replace. BEGIN IMMEDIATE com rechecagem, rollback total e concorrência testados.
- Provider_configs continua desabilitado por default e não há seed. WF-007 introduziu escritor interno append_version com Pydantic/JSON canônico e snapshot explícito de providers habilitados; WF-008 acrescenta CRUD mínimo HTTP de definição/versões e referências locais de provider, sem campos de credencial/settings. Settings/credential_ref não integrados são recusados, não copiados. JSON1 requerido, verificado SQLite3.36.0.
- **WF-003:** compiler.py/nodes.py compilam definições estritas com executores confiáveis obrigatórios por tipo, snapshots em memória de configuração, envelopes/eventos e contadores por etapa/tarefa, prazo, revisão lógica das evidências e aprovação/gates explícitos. Sem executores CLI implícitos, API ou ledger. Budget não nulo e fallback configurável recusados até integrações OBS/WF-010.
- core.graph usa compile_legacy com layout privado e callbacks/entradas/topologia/recursion250 preservados. Snapshot topológico capturado de fc93cd1 antes da mudança; não existe bypass por nome legacy-v1 em workflows de usuário. Execução genérica deriva recursion de max_total_steps e verifica contagem por etapa.
- Deadline checado antes/depois e nos controles; executor deve aplicar context.timeout_s aos subprocessos. Gates têm payload booleano obrigatório mas persistência/proveniência em RES-004; nenhum autoapprove de produção. Testes/review precisam cobrir a última escrita para finalizar.
- **WF-004:** presets.py fornece catálogo interno legacy-v1/A/B/C e clonagem/configuração por etapa. Padrão UI recomendado A e CLIlegacy identificados; cada consulta cria cópias independentes, modelos null mantêm defaults do provider e escolhas substituem bindings inteiros.
- validate_preset respeita manifestos reais, sem promover capacidades. A/C não executáveis com manifestos atuais incompletos; B bloqueado por PROV-001 mesmo com fakes. Legacy continua com resolução/validação original; clone vira workflow estrito com planner read_only/testes separados/só primários, sem bypass por nome. Modelo vazio normalizado só no clone, original intacto.
- **WF-007:** config.workflow opcional com versão/definição/bindings e adapter/kind resolvidos, workflow_digest canônico e confirmação sobre config inteira. Store interno grava versões imutáveis; fila revalida drift na transação e grava três colunas dedicadas. Sem seleção, config/digest/default e colunas nulas antigos preservados.
- Runner confere integridade e capacidades instaladas antes de criar worktree; executa snapshot sem reler versões/providers mutáveis. Host AgentRuntime estrito envia modelos/permissões diretamente, sem exceções do legado. Perfil de testes congelado e Git/agente/testes compartilham deadline absoluto, incluindo atraso de eventos.
- WF-007 entregou seleção interna; WF-008 expõe seleção opcional no preflight/start HTTP. ModelProvider/settings/credential_ref/parâmetros/gates/budgets/fallbacks sem integração recusados antes da fila; nenhuma capacidade real promovida.
- **WF-008:** workflow_api + store expõem listagem/criação/clonagem, histórico/append imutável e validate com erros por campo. Referências de provider locais só para adapter já registrado, sem segredos/settings/entrypoints; mutações auditam IDs. Novo POST preflight e StartInput.workflow opcional usam snapshot, GET/cliente legado preservados.
- StartExecution lista presets/workflows/versões, filtra providers e permite modelos suportados por etapa. Consentimento invalidado ao editar seleção; key idempotente estável. A vira default apenas quando apto; cópia requer ação explícita; legado com aviso até lá. Trio fica congelado apesar de refreshGET, mapas aceitam IDsconstructor.
- Default conhecido agy é resolvido no preflight para impedir drift do worker, sem mudar legado. CLI Claude/Codex sem flag de modelo não aceitam override. Validação HTTP omite input/ctx para não ecoar segredos/campos proibidos.
- Sem seed de banco ou editor de etapas nesta entrega; CLI default preservado. CLI flags intactas: Claude ainda acceptEdits, Codex read-only. SEC-003/004 permanecem sem implementação; Q2–Q12 recebidas nesta sessão, conforme seção de decisões abaixo.

## Evidências WF-008 / CI
| Verificação | Resultado |
|---|---|
| CI remoto reportado | Falhou setup-python3.9 no ubuntu-latest26.04, antes dos testes; Actions44354266781/44214673001 |
| Correção CI local DIST-004 | feb4caf fixa ubuntu-22.04, manifesto oficial3.9.25 confirmado, pytest isolado; revisão review_ci_fix aprovada. Sem push/run remoto novo; não declarar Actions verde |
| Baseline pytest isolado / vitest | 521 passed,1 warning /38 passed |
| Pytest final isolado | 532 passed,1 warning LangGraph,18,89 s |
| Novos testes API | 11 passed; inclui ausência de agentes no HTTP e default agy congelado via runner fake |
| Frontend final | 44 vitest;6 novos, build/lint verdes |
| Revisão review_wf008 | aprovada após trio/IDsprototype;243 Python focados+44vitest/build/lint. Último default agy revalidado:48 focados passaram |
| E2E final QA isolado | 9 passed /2 skipped (opt-ins de projetos/exclusão),11,6s; serviços encerrados |
| Docs / diff --check | sucesso |
| Agentes CLI reais | nenhum; sem quota real |

## Decisões do operador — 2026-11-18
- Q2 esclarecida: novo padrão desejado Claude → Codex → Antigravity, usuário pode escolher providers/modelos por etapa. Q5 aceita workspace-write como necessário para preset A, com alternativa sem execução a verificar. Não ativados nesta sessão; default executado ainda Claude/Claude/Codex.
- Q3 alvo Python3.12 autorizado, ainda não migrado. Q4 perguntar ao fechar com run ativo, opção background. Q6 Ubuntu/.deb primeiro, AppImage depois; assinatura não escolhida.
- Q7 explicitamente adiada: intenção pública/open source sem licença específica; nenhum LICENSE criado. Q8 alertar por padrão, bloqueio opt-in, valor indefinido. Q9 contador separado/equivalente estimado não cobrado.
- Q10 autoriza poucos prompts triviais em diretório temporário para spikes de telemetria/Planner read-only. Nenhum consumo real nesta sessão; testes automáticos com mocks continuam obrigatórios.
- Q11 commits automáticos em worktree/branch agent/<run> por tarefa aprovada, não por tentativa/chamada nem na origem; sem merge/push/deploy. Q12 Conductor provisório/reversível.
- Registro não é implementação nem aceitação integral dos ADRs; revisão específica dos dez ADRs continua pendente. F0-002 fica parcial/blocked residual por esse critério, não por perguntas já respondidas.

## Próximos passos
- Continuidade sugerida: F0-005 e sequência SEC-003/004, WF-005/006, OBS-001; ver ANTIGRAVITY_HANDOFF/NEXT_STEPS. WF-009 concluída; WF-010 concluída e revisada.
- Execução real do padrão A depende de SEC-003/004, WF-005/006 (API/seleção/editor já entregues). B continua bloqueado por PROV-001. Decisões Q2/Q5 já recebidas; não promover manifestos não verificados.
- Python3.12/compatibilidade em F0-005 e spikes autorizados em F0-003/SEC-003 podem avançar no escopo decidido; uma tarefa por vez, com revisão pertinente. Não confundir o bloqueio residual de F0-002 com as questões já resolvidas.
- Licença específica, assinatura, valor de orçamento, identidade final e revisão integral dos ADRs continuam pendentes nos seus respectivos escopos.

## Ambiente
Python 3.12.3 (.venv), LangGraph 1.2.22, langgraph-checkpoint-sqlite 3.1.3, Node 22.18.0, Git 2.43.0. Sem alterações em credenciais.

## CI e versão de Python
O email remoto anterior descrevia falha de setup do Python 3.9 em `ubuntu-latest` (26.04), corrigida em `V2-DIST-004` (`feb4caf`). Com `V2-F0-005`, o workflow `.github/workflows/tests.yml` passa a usar `ubuntu-24.04` e `python-version: "3.12"`, alinhado ao ambiente local validado. CI remoto só poderá ser declarado verde após push/execução autorizados dos commits novos.

## Marco WF-009 — início
HEAD58051a2 jácommitado e árvore limpa, dev ahead3. Editor de definições versionadas, binding/modelos permanecem por run na confirmação conformeADR0005; sem persistir campos que seriam descartados. Validação estrutural sem providers para salvar rascunhos, snapshots e readonly preservados. Baseline532pytest/44vitest verdes.

## Evidências WF-009

| Verificação | Resultado |
|---|---|
| Baseline isolado | 532 pytest /44 Vitest, árvore limpa HEAD58051a2 |
| Pytest final isolado | 534 passed,1 warning LangGraph,19,66s |
| Frontend final | 54 Vitest em8 arquivos;10 novos editor; build/lint verdes |
| API focada | 13 passed,2 novos; validar estrutura sem provider lookup e preservar versões anteriores |
| E2E final QA temporário | 11 passed/2 skipped (opt-ins projetos/exclusão),14,7s; agentes simulados, serviços encerrados |
| Revisão independente | review_wf009 aprovada após2P2 corrigidos;10 focados e diff limpo revalidados pelo revisor |
| Docs/diff | check_docs e diff --check verdes; sem novas dependências/credenciais/quota |

- WF-009 altera apenas edição/validação/versionamento; providers/modelos continuam por run no StartExecution. Salvar gate/budget não libera sua execução; B aguarda PROV-001. Nenhum run é iniciado pelo editor.
- CI remoto não foi reexecutado: correção DIST-004 e commits seguintes permanecem locais em dev. Não afirmar Actions verde sem push/run futuro autorizado.

## Marco WF-010 — início
HEAD1d05736 limpo em dev. Implementação de fallback em andamento; contratos de erro seguro e registros usage_record no event store, tabela OBS-001 permanece futura. Handoff geral para Antigravity solicitado. Sem CLIs reais/quota/push.

## Marco WF-010 — implementação em revisão
Cadeia de alternativas tipadas no envelope, snapshots incluem todos os candidatos, uso por chamada em eventos persistidos e recusa de retries ambíguos. Primeira rodada62 focados verdes; casos ampliados identificaram fixture falsa sem capacidade structured_output (corrigida). Validação ampliada/suite e revisão independente em andamento; WIP local sem commit.

## Marco WF-010 — revisão aprovada

- review_wf010 aprovou código e documento Antigravity:192 focados +27 casos fallback independentes, check_docs/diff verdes. Ajuste final de projeção usage_record também aprovado, sem repetir suite do revisor.
- Host e compilador implementam alternativas ordenadas por erro tipado com atestado sem efeitos, limites cumulativos, IDs/retry_of e uso por chamada em eventos. Snapshots incluem todos os providers alternativos, modelo agy conhecido e guards de integração; sem escalada de permissão. Alterações não mudam fallback legado ou flags dos CLIs.
- Tabela usage_records/migração5 e contabilidade universal continuam OBS-001. Built-ins atuais ainda não atestam retry seguro para quota; stderr genérico não autoriza repetição. Configurável via API; controles dedicados de fallback na UI não foram adicionados nesta tarefa BE.
- Documento geral: [ANTIGRAVITY_HANDOFF](ANTIGRAVITY_HANDOFF.md), com decisões, regras, tarefas sugeridas e prompt. Nenhuma tarefa adicional iniciada. Sem agentes reais/quota/push/credenciais/dependências novas.

## Evidências finais WF-010

| Verificação | Resultado |
|---|---|
| Baseline | 534 pytest/54 Vitest, HEAD1d05736 limpo |
| Python final isolado | 561 passed,1 warning LangGraph,21,61s |
| Novos testes | 27 fallback +1 parametrização dashboard; um antigo bloqueio fallback removido pois integrado |
| Frontend | 54 Vitest, build/lint verdes; sem mudança de UI |
| E2E QA | 11 passed/2 opt-ins skipped,14,7s; serviços temporários encerrados e agentes mockados |
| Independente | review_wf010:192 focados,27 fallback, docs/diff; aprovação final da projeção usage_record |
| Documentação | check_docs e diff limpos; guia Antigravity revisado |

Próxima recomendada F0-005 (Python3.12/SqliteSaver), alternativa de continuidade sem quota DIST-002/SEC-005; sequência completa no guia. Backlog:19 done/43 todo/1 blocked. WIP da tarefa incluído no commit local V2-WF-010; nenhum push/merge/deploy.

## Marco V2-F0-005 — implementação e validação em Python 3.12
- `.venv` migrado para Python 3.12.3 local ao workspace (eliminando o symlink antigo que apontava para Python 3.9.7 fora da raiz do repositório).
- `langgraph-checkpoint-sqlite>=2,<4` adicionado a `requirements.txt` (instalado `3.1.3` com `langgraph 1.2.22`).
- `.github/workflows/tests.yml` atualizado para `ubuntu-24.04` com `python-version: "3.12"`.
- Novo teste `tests/test_python_checkpoint_compat.py` verifica versão `sys.version_info >= (3, 12)` e round-trip persistente em SQLite com `SqliteSaver` e `StateGraph`.
- Resultado: **563 pytest passed** (22,53s, zero warnings), **54 Vitest passed**, `build`, `lint`, `check_docs.py` e `git diff --check` verdes. Revisão independente `review_f0005` aprovada sem findings. Backlog: **20 done / 42 todo / 1 blocked**. Nenhum agente CLI real acionado.

## Marco V2-DIST-002 — CI do frontend
- `.github/workflows/tests.yml` expandido com o job `frontend` (`ubuntu-24.04`, Node 22, cache `npm` via `frontend/package-lock.json`, `npm --prefix frontend ci`, `lint`, `build`, `test`).
- `tests/test_python_checkpoint_compat.py` acrescenta `test_ci_workflow_defines_python_312_and_frontend_checks`.
- Resultado: **564 pytest / 54 Vitest**, build, lint e `check_docs.py` verdes.

## Marco V2-SEC-003 — Planner Claude em modo somente leitura
- `ClaudeCodeRuntime` suporta `read_only` (`--permission-mode plan`) e `workspace_write` (`--permission-mode acceptEdits`).
- `bindings.py` exige `read_only` para `planner`, `planner_fallback` e `reviewer` sem exceção de escrita para o planner Claude.
- `tests/security/test_planner_readonly.py` adicionado (3 testes); `test_argv_characterization.py`, `test_bindings.py`, `test_registry.py` e `test_runtime_contract.py` atualizados.
- Resultado: **567 pytest / 54 Vitest**, build/lint/docs verdes. Aprovada pelo operador (done).

## Marco V2-SEC-004 — Matriz de permissões por papel em argv
- `orchestrator/policy/roles.py` centraliza a matriz `ROLE_ALLOWED_PERMISSIONS` e os builders `build_claude_argv`, `build_codex_argv` e `build_antigravity_argv`.
- `ClaudeCodeRuntime` em `workspace_write` inclui `--disallowedTools Bash` além de `--permission-mode acceptEdits`; qualquer combinação `(role, permission)` proibida levanta `RolePermissionError` antes de iniciar subprocesso.
- `tests/security/test_role_argv.py` adicionado com 23 testes cobrindo CA3 de `SECURITY_GOVERNANCE.md`.
- Resultado: **590 pytest / 54 Vitest**, build/lint/docs verdes. Aprovada pelo operador (done).

## Marco V2-WF-005 — Codex CLI como executor (`workspace-write`)
- `CodexCliRuntime` inclui `Capability.CODE_EDIT` e `Capability.CODE_EXEC` e `permission_modes=['read_only', 'workspace_write']` (`verified=False` preservado).
- Inspeção de `codex exec --help` (0.166.0) confirma que `--sandbox` só oferece `[read-only, workspace-write, danger-full-access]`; não há flag para escrita de arquivos sem shell no CLI.
- `tests/workflows/test_codex_executor.py` valida `argv` (`codex exec --sandbox workspace-write <prompt>`), rejeição de permissões inválidas e execução completa do Preset A (`default-v2`) com adapters reais e runners mockados.
- Resultado: **598 pytest / 54 Vitest**, build/lint/docs verdes.

## Marco V2-WF-006 — Antigravity como reviewer com saída JSON validada
- `AntigravityRuntime` inclui `Capability.REVIEW` e `Capability.STRUCTURED_OUTPUT` e valida estritamente o JSON de revisão (`approved: bool`, `findings: list[str]`, `test_suggestions?: list[str]`), populando `InvocationResult.structured`.
- Texto livre ("Looks good to me! Approved.") ou tipos não booleanos/listas inválidas levantam `RuntimeError` classificado como `invalid_output`.
- `tests/workflows/test_antigravity_reviewer.py` adicionado com 12 testes (incluindo integração com `core.review`).
- Resultado: **610 pytest / 54 Vitest**, build/lint/docs verdes.

## Marco V2-OBS-001 — Migração 5 e gravação de `usage_records`
- `project_store.py` inclui `ACCOUNTING_MIGRATION` (versão 5) com `step_executions`, `price_catalog_versions`, `price_entries`, `usage_records`, `budgets` e `budget_events`.
- `orchestrator/accounting/usage.py` persiste cada chamada de agente em `usage_records` (usando `call_id` como chave primária para deduplicação com eventos `usage_record` de `V2-WF-010`, preservando `retry_of`, resolvendo `project_id` de `managed_runs` quando disponível e redigindo segredos de `raw_usage` com limite de 8 kB).
- Integrado em `core._record_agent_call` e `workflows/execution.py`.
- `tests/workflows/test_usage_records.py` adicionado (4 testes). Resultado: **614 pytest / 54 Vitest**, build/lint/docs verdes.

## Marco V2-SEC-005 — Credential store com `keyring`
- `orchestrator/secrets/store.py` fornece `CredentialStore`, `InMemoryKeyringBackend` e `bind_provider_credential`/`remove_provider_credential`.
- SQLite armazena somente `credential_ref` (`multi-agent-orchestrator:<adapter>:<config_id>`) e auditoria `credential.set`/`credential.removed` sem segredos; backends `fail`/`null` falham fechados com `KeyringUnavailableError`.
- `tests/security/test_credential_store.py` adicionado (6 testes). Resultado: **620 pytest / 54 Vitest**, build/lint/docs verdes.

## Marco V2-RES-001 — Ledger `step_executions` + digest de árvore
- `orchestrator/resilience/digest.py` calcula `tree_digest` determinístico (`git status --porcelain=v2` + `git diff --no-ext-diff HEAD` + conteúdo limitado de untracked) e `git_head_before`.
- `orchestrator/resilience/ledger.py` grava `started` antes e `completed`/`failed` depois de cada invocação de nó no host de workflows, populando `usage_records.step_execution_id`.
- `tests/workflows/test_step_ledger.py` adicionado (4 testes). Resultado: **624 pytest / 54 Vitest**, build/lint/docs verdes.

## Marco PROV-001 — início (Codex, 2026-11-19)
HEAD1f9bf64 limpo em dev. SEC-003 voltou a review por falta de validação real exigida, sem dispensa explícita; SEC-004 preservada. PROV-001 em implementação com HTTP/keyring simulados; baseline pendente. Nenhuma credencial real alterada, quota/push/merge/deploy.

## Marco PROV-001 — implementação em revisão
100 testes focados verdes, incluindo fila/dispatch com planner e reviewer API simulados, usage_records reportados e varredura SQLite sem chave-sentinela. Contexto inclui novos arquivos, bloqueia symlinks/binaries/limites; snapshot congela referência sem chave e preserva hashes legados sem campo novo nulo. Suites/revisão pendentes; WIP local.

## Evidências finais PROV-001

- Baseline624 pytest/54 Vitest. Final666 passed,23,66s; frontend54 Vitest/build/lint verdes; E2E11 passed/2 skipped (opt-ins projetos/exclusão),15,0s em QA temporário com mocks, serviços encerrados.
-42 testes adicionados: adapters/contexto/fila/uso/ledger e reserva D-Bus; asserts de catálogo atualizados para4 built-ins. Dois testes /proc antigos sincronizados após exec para eliminar race, sem enfraquecer allowlists.
- Revisor review_prov001 confirmou100 focados +54 segurança antes de ajustes; depois63 focados +26 ambiente e diff limpo. Sem bloqueadores restantes. check_docs verde.
- Referência de keyring entra no snapshot/digest, valor nunca; defaults/hashes legados preservados quando sem referência. HTTP200 inválido preserva uso reportado e falha sem retry. DBUS não passa a CLI/testes/Git. Sem migração/seed/modelo implícito, preços avançados ou UI de chaves nesta entrega.

## Marco RES-002 — implementação em revisão
Arquivo de checkpoints separado derivado de ORCH_DB, modo0600/WAL e SqliteSaver ligado ao compilador/host estrito com thread_id=run_id/digest. Checkpoint existente bloqueia novo início antes da worktree; sem retomada automática.25 focados verdes (8 novos). Serialização restrita sem pickle/import dinâmico; mínimos de dependências refletem versões de APIs verificadas no ambiente (sqlite3.1.3/checkpoint4.3.2/LangGraph1.2.22). Suites/revisão em andamento.

## RES-002 concluída

- Checkpoints de workflows estritos em banco separado derivado de ORCH_DB, privado0600/WAL/FULL, thread_id=run_id, metadata workflow_digest. Serialização restrita, sem pickle/dynamicimports. durability=sync antes do próximo nó. Presença de estado anterior bloqueia início repetido antes de worktree/agentes, sem liberação de retomada gerenciada.
- Baseline imediato666pytest/54Vitest. Final675pytest,24,41s;54Vitest/build/lint/docs verdes.9novoscheckpointer, incluindo corrupção isolada e falha de gravação que impede implementer. review_res002 aprovada:52focados iniciais,36checkpointer/compiler apóssync. E2E não repetido nesta tarefa sem UI/fluxo legado alterado; último PROV00111passed/2skipped.
- requirements mínimos LangGraph1.2.22/checkpoint4.3.2/sqlite3.1.3, versões já instaladas. Sem pip/credenciais/quota/chamada real. Commit local RES-002 dev; próxima SEC-007, depois OBS-003. Legado e endpoints de retomada permanecem fora desta entrega.

## Marco SEC-007 — implementação em revisão
Auditoria de ações estendidas validada por allowlist de campos/tipos/IDs, sem segredo/freetext/nestedpayload; produtores existentes passam pelo mesmo projects.audit. Eventos futuros de aprovação/override/resume têm contrato validado mas nenhum fluxo foi ativado. Testes de registros/rollback/produtores reais HTTP/keyring mockados em andamento. Sem schema novo/credenciais reais/quota.

## SEC-007 concluída

- policy.audit valida metadados dos eventos estendidos antes de projects.audit inserir; IDs/referência canônica/decision enum e nenhuma chave/objeto/freetext extra. Produtores de workflow/versão/provider/credential integrados; contratos futuros approval/budget/resume não ativam fluxos de domínio. Legado project/request/execution preservado.
- Baseline675pytest/54Vitest; final700pytest,22,80s/54Vitest/build/lint/docs verdes.25novos incluindo integração HTTP sem nomes/corpos e rollback SQL. review_sec007 aprovada com30focados/diff limpo. E2E não repetido:sem UI/execução alterada, último PROV00111passed/2skip.
- Sem nova migração/endpoints/credenciais/quota/push. Commit local SEC-007 dev autorizado; próxima OBS-003. SEC-003 segue review por evidência real pendente.
