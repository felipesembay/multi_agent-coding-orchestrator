# Estado atual

Atualizado: 2026-11-17 · Por: Codex (V2-CORE-001)

## Repositório
- Branch: `dev`, criada pelo operador. Baseline: `f8e6949` (`V2-F0-001: establish reviewed development baseline`).
- Operador autorizou implementação e novos commits em `dev`, após testes. Não fazer merge/push/deploy nem integrar main/master.
- WIP anterior de tema claro/escuro, exclusão lógica e migração v3 foi preservado, revisado por `review_baseline_dev`, testado e incluído no baseline, junto com planejamento e V2-DOC-001. A orientação anterior de preservar sem commit foi substituída pela autorização de commits em dev.
- V2-CORE-001 registrada em dev no commit `V2-CORE-001: extract CLI runtimes behind compatible facades`, após revisão independente `review_core001`; consulte `git log -1`. Nenhum WIP restante identificado.

## Implementado
- v1 funcional conforme [CURRENT_STATE_AUDIT.md](../architecture/CURRENT_STATE_AUDIT.md), com tema/exclusão/migração v3 do baseline.
- **V2-DOC-001 done:** `scripts/check_docs.py` valida links locais/âncoras/referências, IDs completos do backlog e data deste documento contra último commit de código. Sem rede/dependências novas.
- **V2-F0-001 done:** baseline em dev testado, revisado e commitado em `f8e6949`.
- **V2-CORE-001 done:** `orchestrator/providers/base.py` contém contratos mínimos Pydantic `InvocationRequest`, `InvocationResult(text)` e Protocol `AgentRuntime`; adapters Claude/Codex/Antigravity extraídos para `providers/runtimes/`.
- Fachadas `core.claude/codex/antigravity` preservam assinatura e retorno texto; `coding_agent` mantém seleção/fallback. `core.run_command` é injetado por chamada para manter mocks/lock/execução existentes.
- Nenhuma mudança de flags, prompts, timeout, fallback ou eventos. `InvocationResult` completo/uso/eventos pertencem a CORE-002; manifestos/probe/registry a CORE-003. Claude continua com `acceptEdits`; Codex continua read-only; correções de segurança seguem no backlog.

## Testes desta sessão
| Comando | Resultado |
|---|---|
| `ORCH_DB=<tmp> python -m pytest -q -p no:cacheprovider` | Baseline 81 passed; final 109 passed, 1 warning LangGraph |
| `python -m pytest -q -p no:cacheprovider tests/providers tests/test_planner_fallback.py` | 35 passed; revisão independente repetiu com sucesso |
| Caracterização antes de alterar core | 22 testes novos + 7 fallback: 29 passed |
| `npm --prefix frontend test` | 32 passed (6 arquivos), no baseline; frontend não alterado depois |
| `npm --prefix frontend run build` / `run lint` | sucesso, no baseline |
| `python scripts/check_docs.py` / `git diff --check` | sucesso |
| E2E / execução real de agentes | não executados |

A suíte completa Python requer sair do sandbox neste ambiente para TestClient/sockets/subprocessos locais; execução autorizada automaticamente. Nenhum CLI de agente real chamado nos testes.

## Próximas etapas e pendências
- V2-CORE-002 ou V2-CORE-003 liberadas após CORE-001; executar uma por vez. Recomendação: CORE-002, resultado/uso/eventos estruturados.
- V2-F0-002 permanece `blocked`: Q2–Q12 aguardam decisão humana; nenhum ADR aceito/rejeitado por presunção. Isso não bloqueia as tarefas CORE cuja dependência é só CORE-001.
- Quota real não autorizada. Não iniciar F0-003/validação real SEC-003. Demais decisões só bloqueiam suas tarefas indicadas em OPEN_QUESTIONS.

## Ambiente observado
Python 3.9.7 (.venv), LangGraph 0.6.11, Node 22.18.0; CLIs `claude` 2.1.92, `codex` 0.166.0, `agy` 1.5.1, `ollama` observados na auditoria anterior; Rust/cargo presentes; Tauri CLI ausente na auditoria. Compatibilidade Pydantic em Python 3.9 mantida com Optional, sem dependências novas.
