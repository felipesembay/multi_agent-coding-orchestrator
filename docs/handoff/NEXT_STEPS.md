# Próximos passos

## Próxima tarefa: V2-CORE-002

**Objetivo:** completar `InvocationResult`/`UsageReport` e registrar `agent_call` (provider, modelo, duração) em todas as chamadas. Dependência CORE-001 concluída.

**Aceite:** resultados estruturados com uso `unavailable` até parsers verificados; um evento por chamada, incluindo tentativas de fallback; eventos novos não quebram o dashboard nem contratos legados. Sem quota real, segredos em logs ou mudanças nas flags. Ler PROVIDER_SYSTEM e TOKEN_ACCOUNTING antes de implementar, escrever testes com mocks, revisar e registrar handoff.

## Decisões humanas pendentes

- V2-F0-001 concluída: baseline `f8e6949` em `dev`, preservando o WIP. Novos commits em dev autorizados após testes; sem merge/push.
- V2-F0-002 `blocked`: Q2–Q12 e ADRs aguardam revisão humana. Não impedem CORE-002/003. Quota real segue não autorizada.

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
