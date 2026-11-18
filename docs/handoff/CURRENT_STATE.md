# Estado atual

Atualizado: 2026-11-18 · Por: Codex (V2-SEC-006)

## Repositório
- Branch `dev`; operador autoriza commits testados/revisados nessa branch, sem merge/deploy/main/master.
- Baseline `f8e6949`; CORE-001..004 em `87a034f`, `56e44d2`, `6737c2f`, `db12642`. Push autorizado anteriormente somente até db12642 em origin/dev.
- SEC-001 `8d94e7d`, SEC-002 `065d9ed`, novos commits locais sem push. SEC-006 registrada nesta sessão no commit `V2-SEC-006: harden Git preparation and inspection`; consulte git log -1 para hash final.
- WIP original de tema/exclusão/migração v3 preservado no baseline. Nenhum WIP externo identificado.

## Implementado
- v1 preservada: worker separado, fila SQLite, worktrees/locks, idempotência e contratos legados. DOC-001 verificador de documentação concluído.
- CORE-001..004: adapters/registry/manifestos, resultados e telemetria honestos, bindings por papel imutáveis e snapshots/digests compatíveis. Defaults Claude/Claude/Codex e fallback exato preservados; billing/uso desconhecidos, sem parsers reais.
- SEC-001: política HTTP global Host/peer/origem e token CSRF/bearer; bootstrap local /session e liveness /health sem token sob mesmos controles locais. Frontend autentica reads/writes sem persistência/replay de mutações.
- SEC-002: ambiente por nomes/escopo, declarações de config dirs CLI e extensões opcionais ORCH_ENV_ALLOWLIST congeladas por nome no snapshot/digest. Valores não persistidos; controles internos filtrados e marcador de despacho preservado para identificar descendentes.
- **SEC-006 done:** policy/git.py compartilhada por core.run_command, projects.git e repository_lock.identity. Config por chamada desliga hooks/fsmonitor/assinatura/pager/manutenção e recursão de submódulos; diff sem conversores; aceita apenas formas completas não interativas necessárias ao produto.
- Git lê configuração efetiva/includes em consulta sem expor valores e recusa clean/smudge/process executáveis. prepare registra worktree --no-checkout e revalida na nova branch antes de reset --hard HEAD. Timeout cobre consulta+comando; fds preservados; config original não é alterado.
- **Compatibilidade:** repositórios com filtros executáveis configurados não são suportados na automação. Configuração condicional detectada após registro pode deixar branch/worktree vazia para inspeção; não há limpeza automática. Submódulos não são inspecionados recursivamente. Git invocado por ferramentas de agentes/testes fora desse wrapper não é interceptado, e isso não é sandbox do SO.
- CLI flags/permissões de agentes não mudaram; Claude ainda acceptEdits, Codex read-only. SEC-003/004 e decisões humanas continuam pendentes.

## Evidências desta tarefa
| Verificação | Resultado |
|---|---|
| Baseline pytest isolado | 301 passed, 1 warning |
| Pytest final `ORCH_DB=<tmp> python -m pytest -q -p no:cacheprovider` | 323 passed, 1 warning LangGraph, 14,30 s |
| Git real + ambiente | 47 passed, controles positivos e regressões de hooks/fsmonitor/conversores/filtros/branch/aliases/opções |
| Revisão independente review_sec006 | 69 focados passaram; correções finais aprovadas em 2026-11-18 |
| Frontend | 38 vitest no baseline; build e lint verdes; frontend inalterado |
| Docs / diff --check | sucesso |
| E2E | não reexecutado em SEC-006; última execução SEC-002 9 passed / 2 skipped em QA com mocks |
| Agentes CLI reais | não executados; sem quota de CLIs |

Todos os Git sentinelas e workflows de integração usam repositórios/DB temporários. Nenhum serviço QA iniciado nesta tarefa. Revisor atingiu limite antes da primeira aprovação final, mas retomou após continuação e aprovou; pendência resolvida.

## Próximos passos
- WF-001: schema WorkflowDefinition e validação conforme especificação, com fakes e revisão distinta. CORE-003 já concluída.
- F0-002/Q2–Q12 e aceitação/rejeição dos ADRs aguardam operador; não presumir mudanças de padrão/permissões/quota. SEC-003 exige execução real autorizada e SEC-003/004 têm revisão humana obrigatória.

## Ambiente
Python 3.9.7 (.venv), LangGraph 0.6.11, Node 22.18.0, Git 2.43.0 verificado nesta tarefa. Sem dependências novas ou alterações em credenciais.
