# Próximos passos

## Próxima tarefa recomendada: V2-SEC-006

**Objetivo:** verificar e desabilitar hooks/config insegura do Git em core.prepare/run_command, conforme SECURITY_GOVERNANCE CA4. Task P0 independente.

**Aceite:** repositório temporário com hook post-checkout sentinela não o executa ao preparar worktree; manter worktrees/locks/diffs/status e recuperação compatíveis. Ler SECURITY_GOVERNANCE/ADR-0009, comparar projects.git/repository_lock.identity. Testar Git real em diretórios temporários, sem agentes reais/quota; revisão distinta e handoff antes do commit dev.

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
- V2-F0-002 `blocked`: Q2–Q12 e ADRs aguardam revisão humana. Não impedem SEC-006; SEC-003 requer autorização de validação real. Quota real segue não autorizada.

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
