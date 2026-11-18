# Próximos passos

## Próxima tarefa: V2-WF-004 — decisão Q2 pendente

**Objetivo:** presets legacy-v1, A/B/C e preservação do CLI legado. WF-003/CORE-004 concluídas. Q2 sobre mudança de padrão bloqueia a conclusão/ativação desta tarefa conforme OPEN_QUESTIONS; não presumir resposta. Q5/SEC-004/WF-005 também limitam Codex executor real, e preset B fica desabilitado até PROV-001. Os testes de presets devem usar manifestos fakes, sem promover built-ins não verificados.

**Aceite:** presets validados com fakes, CLI permanece legacy-v1 por padrão, decisões de ativação registradas pelo operador e revisão independente. Ler WORKFLOW_ENGINE/OPEN_QUESTIONS/ADR-0005; usar compilador genérico apenas com executores confiáveis, e compatibilidade legada explícita, sem bypass por nome de usuário.

**Alternativa liberada:** V2-WF-007 (WF-002/WF-003 prontos), snapshot/digest de workflow+bindings por run, sem mudar padrão, permitindo aguardar Q2. Não iniciar tarefa sem registrar escolha e baseline.

## WF-003 concluída

- compiler.py compila WorkflowDefinition estrita em StateGraph com executores host injetados por tipo. nodes.py define WorkflowState/StepContext e envelopes com eventos por etapa, contadores por tarefa, prazo e limite global.
- core.graph delega a compile_legacy com layout privado de compatibilidade e mesmos callbacks, entradas/recursion250; review legado continua incluindo testes. Topologia congelada antes de alterar core em fixture JSON de fc93cd1. Sem novas flags/CLI/defaults ou retomada gerenciada.
- Gate exige executor e approved booleano; política após plano reutiliza gate explícito ou gera um. Testes falhos e revisão antiga após nova escrita impedem sucesso. Evidência atual por revisão lógica não substitui ledger/digest/approvals futuros.
- Budget não nulo e fallbacks configuráveis são recusados até OBS/WF-010. Executores devem aplicar timeout restante a chamadas em andamento; checagens síncronas são antes/depois da chamada. Nenhum executor CLI concreto/API/ledger/uso/gate persistido foi adiantado. Contrato detalhado em WORKFLOW_ENGINE §6.3.1.
- Revisão review_wf003 aprovada: 134 focados passaram; inclui 30 novos testes de compilador/topologia. Contagens completas desta sessão em CURRENT_STATE/SESSION_LOG. Sem agentes reais ou quota.

## WF-002 concluída

- Migração v4 aditiva: workflow_definitions, workflow_versions, provider_configs e managed_runs.workflow_version_id/bindings/workflow_digest, nulos para runs antigos. Dados/configs/events/índices antigos preservados.
- BEGIN IMMEDIATE com rechecagem sob lock, rollback total de DDL e reabertura/concorrência testados. FK/JSON/digests e versões imutáveis, inclusive contra OR REPLACE. Tabelas vazias, provider_configs.enabled default 0; nenhum seed ou novo comportamento de execução.
- Evidência: 424 pytest / 38 vitest, build/lint/docs verdes; 26 novos casos de migração; revisor review_wf002 aprovou e rodou 101 testes de workflows. Fixture SQL v3 congelada em caee20e. SQLite JSON1 requerido e verificado local3.36.0.
- Não existe CRUD de workflow/provider nesta tarefa; o futuro escritor deve aplicar schema Pydantic ao body e impedir segredos em settings. A migração só impõe integridade SQL básica; credential_ref é referência opcional, sem integração ao keyring. Sem API/compilador/presets/snapshot de workflow no executor.
- Decisões Q2–Q12 continuam em aberto e não foram necessárias para WF-002; não presumir respostas ao avançar.

## WF-001 concluída

- Schema v1 de WorkflowDefinition e seis etapas tipadas; bindings separados com provider_config_id/model/parameters/permission/fallbacks. Validação estrutural e de providers já habilitados, sem executar/probar/carregar plugins por input do workflow.
- Limites, aprovação, bloco per_task, retorno limitado review→implement, permissões e capacidades/fallbacks validados com erros Pydantic por campo. Escrita exige runtime verificado; nenhum bypass por nome legacy-v1. Política human_gate_after_plan é declarativa para compilador futuro.
- Evidência: 398 pytest / 38 vitest, 75 novos testes; build/lint/docs verdes. Revisor review_wf001 aprovou após correções de container inválido e bool estrito no plan. Nenhum CLI real/E2E nesta tarefa, sem mudanças em fluxo atual/migração/API/presets/defaults.
- Contrato e limites explícitos em WORKFLOW_ENGINE §6.2.1; mapa temporário confiável provider_configs ID→adapter será integrado à persistência na próxima tarefa.

## SEC-006 concluída

- policy/git.py compartilhada por core/projects/locks: hooks/fsmonitor/assinatura/pager/manutenção desabilitados, status/diff sem submódulos/conversores e formas completas não interativas. Aliases, globais de caller, abreviações e negações não autorizadas recusadas.
- Filtros executáveis clean/smudge/process da configuração efetiva recusados sem expor valores; includes por branch rechecados em worktree registrada sem checkout, antes de reset --hard HEAD. Config do repositório não é alterado; worktree vazia/branch podem permanecer se configuração condicional for recusada, para inspeção manual.
- Proteção cobre Git direto do orquestrador, não comandos Git que agentes/testes executem por conta própria; sem sandbox de SO/garantia contra mutação maliciosa concorrente do mesmo usuário.
- Evidências: 323 pytest / 38 vitest e build/lint/docs verdes, 22 casos Git com controles positivos, revisão review_sec006 (69 focados) aprovada em 2026-11-18 após correções de --check/--no-ignore-submodules. Revisor inicialmente atingiu limite, depois retomou e aprovou. E2E não reexecutado nesta tarefa; integração real Git/LangGraph/worker com agentes mockados coberta no pytest.

## SEC-002 concluída

- policy/env.py: base exata e escopos runner/adapter/tests/git; env desconhecido não herdado. Caminhos de configuração CLI preservados por manifesto (Claude/Codex), sem assumir variáveis extras agy.
- ORCH_ENV_ALLOWLIST permite extensões por nomes/escopo, sem glob, credenciais ou controles reservados. Quando não vazias, nomes canônicos entram no snapshot/digest; valores não persistidos. Default antigo/digest preservado; snapshots inválidos recusados e antigos sem extensão usam default vazio.
- Worker.environment filtra o runner e fornece nomes/entradas necessárias; execução reaplica snapshot. Runtime filtra com runner injetado e core revalida no subprocesso, com PATH efetivo; helpers Git também filtrados.
- Marcador de despacho confiável preservado em descendentes para comprovar órfãos; controles de banco/worker não passam aos agentes/testes. GIT_CONFIG_* seguros gerados. Nomes internos runner/tests/git reservados e identidade provider/manifest conferida, sem colisão de escopo.
- Evidências: 301 pytest / 38 vitest, build/lint/docs verdes, 9 e2e / 2 skipped em QA temporário; /proc de Python fake, supervisor real mockado e limpeza de filho após morte do runner. Revisão `review_sec002`: 93 focados aprovados. QA encerrado; nenhum CLI real.

## SEC-001 concluída

- Host estrito, peer loopback e origem em todas as rotas, inclusive docs/rotas inexistentes; token CSRF ou bearer válido para leituras/escritas. GET/HEAD /session é bootstrap local e /health liveness sem token, mantendo controles locais.
- CSRF e bearer são distintos por processo; bearer não é devolvido pelo bootstrap. app.state.api_token permite configuração nativa em memória (supervisor futuro). Não aceitar token em query/cookie, Authorization inválida não degrada para CSRF.
- Escritas CSRF exigem Origin autorizado; escritas de ambos os modos exigem JSON. Todos os corpos limitados a 150 kB reais; no-store/nosniff/CORP em sucessos/rejeições.
- Frontend obtém token por operação, sem cache/storage/replay de escrita. Contratos JSON e configuração/digest preservados; clientes diretos devem autenticar também leituras.
- Evidências: 273 pytest / 38 vitest, build/lint/docs verdes, E2E 9 passed / 2 skipped no harness temporário com mocks; revisão `review_sec001` (109 Python focados e 38 vitest). QA encerrado. Dois opt-ins de escrita projetos/exclusão não executados por guardrails próprios.

## CORE-004 concluída

- Bindings imutáveis por papel, registry/capacidades/permissões validados; env só fonte do preset legado. Defaults Claude/Claude/Codex e fallback exato preservados. Reviewer configurável internamente; papéis/permissões futuros não antecipados.
- execute_scope aceita bindings/registry internos, congela snapshot em State e started; resume CLI restaura snapshot se presente. Runs gerenciados continuam sem retomada.
- Worker passa bindings de managed_runs.config sem reescrever env de providers/modelos. Config padrão/digest antigos preservados; config explícita inclui bindings, digest e projeção plana checados. Sem migração.
- Leitura de snapshots antigos reproduz truthiness do runner; leitura direta do ambiente preserva strings vazias. Modelos agy nulos em bindings explícitos resolvidos para default conhecido, sem herdar env na chamada.
- Reviewer fake + LangGraph, ambiente divergente após planejamento/despacho, idempotência e digests testados. Retornos inválidos de plugins geram invalid_output estático sem payload em evento/traceback.
- Evidências: 179 pytest / 33 vitest; 69 focados; build/lint/docs verdes; revisão `review_core004`. E2E não executado.

## CORE-003 concluída

- `Capability`, `CapabilityManifest`, `ProbeResult`; manifestos honestos nos três runtimes e probe passivo (só presença do executável), versão/credenciais desconhecidas.
- Registry com runner/observer injetáveis, `get(adapter)` e listagem; built-ins por padrão. Entry points só com opt-in explícito, factories sem argumentos, sem descoberta/carregamento quando desativados; colisões/duplicatas e falhas isoladas.
- `GET /providers` retorna manifest/probe/source por adapter, sob proteção local Host/peer/Origin. HTTP não habilita plugins. provider_configs virá em WF-002; dependência padrão segue sem terceiros.
- Todos os built-ins verified=false, billing unknown e usage_source none; não anuncia papéis/telemetria futuros. Defaults/flags/fallback permanecem inalterados.
- Evidências: 154 pytest / 33 vitest, build/lint/docs verdes; revisão `review_core003` (52 testes repetidos). E2E não executado.

## CORE-002 concluída

- `UsageReport` completo e `InvocationResult` medido, com valores desconhecidos nulos e source `unavailable` em todos os built-ins até parsers verificados.
- Evento `agent_call` por tentativa real de runtime vinculada ao run, inclusive falha/fallback; provider canônico, papel, modelo solicitado ou null, duração monotônica, call_id, erro normalizado e uso. Billing `unknown` até autenticação verificada.
- Eventos não incluem prompt, resposta, ambiente, cwd, mensagens de erro ou usage.raw. Exceções legadas preservadas; observer com falha durante erro não substitui a causa original (warning sem conteúdo).
- Fachadas preservadas; runtime independente sem run devolve metadata sem criar eventos órfãos. Mocks integrais de fachadas não geram invocações artificiais. Implementer agora recebe state; reviewer usa contexto por run/papel.
- API ignora agent_call para etapa/status/resultado, mantendo atividade em last_event. Frontend conserva o evento no fallback genérico.
- Evidências: 130 pytest / 33 vitest, 55 focados, build/lint/docs verdes; revisão `review_core002`. E2E não executado.

## Decisões humanas pendentes

- V2-F0-001 concluída: baseline `f8e6949` em `dev`, preservando o WIP. Novos commits em dev autorizados após testes; sem merge/push.
- V2-F0-002 `blocked`: Q2–Q12 e ADRs aguardam revisão humana. Não impedem o trabalho de equivalência WF-003; SEC-003 requer autorização de validação real. Quota real segue não autorizada.

## Referência concluída: V2-CORE-001

**Objetivo:** extrair `AgentRuntime` e adapters `claude_code`, `codex_cli`, `antigravity` para `orchestrator/providers/`, mantendo `core.claude`, `core.codex`, `core.antigravity` e `core.coding_agent` como fachadas compatíveis.

**Escopo**
- Criar `orchestrator/providers/base.py` (Protocol + Pydantic mínimos de [PROVIDER_SYSTEM §6.1](../specifications/PROVIDER_SYSTEM.md#61-contratos-orchestratorprovidersbasepy)), `runtimes/{claude_code,codex_cli,antigravity}.py`.
- Nenhuma mudança de flags, prompts, timeouts, fallback ou eventos.
- Fora do escopo: registry, usage, novos papéis (CORE-002..004).

**Critérios de aceite**
1. Novo teste `tests/providers/test_argv_characterization.py` cobre: planner claude, implementer claude, planner antigravity, implementer antigravity (com e sem modelo), reviewer codex, fallback planner claude→antigravity — e prova que o `argv` passado a `subprocess.run` é idêntico ao atual (escrever e rodar o teste **antes** da refatoração, contra o código atual).
2. Todos os testes existentes passam sem alteração de asserts.
3. `tests/test_planner_fallback.py` continua verde (patch points podem precisar de shim compatível — documentar).
4. Código restrito a `orchestrator/core.py`, `orchestrator/providers/**` e `tests/providers/**`; documentos de status/handoff atualizados conforme protocolo obrigatório.

**Comandos**
```bash
cd /caminho/para/multi-agent-orchestrator
source .venv/bin/activate
git status --short
ORCH_DB="$(mktemp -d)/events.db" python -m pytest -q -p no:cacheprovider
npm --prefix frontend test
```

**Perfil:** BE. Revisor: agente diferente do implementador.

## Em paralelo (sem dependência de CORE-001)
`V2-SEC-001`, `V2-SEC-002`, `V2-SEC-006`, `V2-DIST-002`, `V2-DESK-005`.

## Verificação de documentação implementada

`V2-DOC-001`: executar `python scripts/check_docs.py` (sem dependências ou rede). Testes: `python -m pytest -q -p no:cacheprovider tests/test_check_docs.py`. Valida links locais/âncoras e definições de referência nos Markdown de `docs/`, README, AGENTS, CLAUDE e frontend/README, IDs completos `V2-*` e data de CURRENT_STATE contra o último commit de código. Não consulta links externos.
