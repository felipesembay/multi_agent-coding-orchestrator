# Estado atual

Atualizado: 2026-11-18 · Por: Codex (V2-WF-002)

## Repositório
- Branch `dev`; commits testados/revisados autorizados pelo operador. Sem merge/deploy/main/master. Novo push não autorizado.
- Baseline `f8e6949`; CORE-001..004 em `87a034f`, `56e44d2`, `6737c2f`, `db12642`. Push anterior somente até db12642 em origin/dev.
- SEC-001 `8d94e7d`, SEC-002 `065d9ed`, SEC-006 `7ac3634`, WF-001 `caee20e` locais. WF-002 registrada no commit `V2-WF-002: add additive workflow and provider migration`; consultar git log para hash final.
- WIP original de tema/exclusão/migração v3 preservado no baseline. Nenhum WIP externo identificado.

## Implementado
- v1 preservada: worker separado, fila SQLite, worktrees/locks, idempotência e contratos legados. DOC-001 verificador de documentação concluído.
- CORE-001..004: adapters/registry/manifestos, resultados com uso desconhecido honesto, bindings por papel e snapshots/digests compatíveis. Defaults Claude/Claude/Codex e fallback exato preservados.
- SEC-001: política HTTP global Host/peer/origem e tokens em leituras/escritas; bootstrap local /session e liveness /health. Frontend autenticado.
- SEC-002: ambiente por nomes/escopo e extensões opcionais congeladas por nome no snapshot/digest. Valores não persistidos; marcador de despacho preservado para detectar órfãos.
- SEC-006: política Git compartilhada, hooks/fsmonitor/conversores desligados e filtros executáveis recusados, inclusive condicionais por branch. Repositórios com esses filtros não suportados. Git de ferramentas externas não é interceptado; não é sandbox de SO. Registro recusado após worktree add pode deixar worktree/branch vazia para inspeção.
- **WF-001:** `orchestrator/workflows/schema.py` contém WorkflowDefinition v1, união discriminada de seis tipos de etapa, limites/aprovação e bindings separados com parâmetros/fallbacks. `validation.py` valida estrutura e providers já habilitados, sem probes/invocações/imports de plugins.
- Plano primeiro/único, bloco per_task contíguo, retorno somente review→implement anterior no mesmo bloco com tentativas limitadas. Capacidades mínimas por tipo, permissões por papel, escrita só com runtime code_edit verificado; fallback inclui todas as capacidades primárias. Erros Pydantic por campo; API 422 futura em WF-008.
- Faixas complementares do contrato documentadas em WORKFLOW_ENGINE §6.2.1: 100 etapas declaradas, 10000 passos totais, 86400 s, 20 tentativas. `documenter` é o papel de document; escrita também verificada. Nome legacy-v1 não contorna validação.
- **WF-002:** migração aditiva v4 entregue em project_store.py, com três tabelas novas, três colunas managed_runs anuláveis, FK/índice de workflow, JSON/digests básicos e triggers de imutabilidade contra update/delete/replace. BEGIN IMMEDIATE com rechecagem, rollback total e concorrência testados.
- Tabelas novas vazias; provider_configs desabilitado por default. Nenhum escritor/CRUD de workflow/provider ou consumidor no executor. Validação Pydantic antes de persistir body e proteção de settings serão obrigatórias no futuro caminho de escrita; SQL cuida apenas de integridade básica. JSON1 requerido, verificado SQLite3.36.0.
- Sem compilador, presets, endpoints ou mudança do fluxo atual. CLI flags intactas: Claude ainda acceptEdits, Codex read-only. SEC-003/004 e decisões humanas permanecem pendentes.

## Evidências WF-002
| Verificação | Resultado |
|---|---|
| Baseline pytest isolado / vitest | 398 passed, 1 warning / 38 passed |
| Pytest final isolado | 424 passed, 1 warning LangGraph, 15,09 s |
| Novos testes de migração | 26 passed contra fixture SQL v3 congelada de caee20e |
| Revisão independente review_wf002 | aprovada sem bloqueios; 101 testes de workflows passaram |
| Frontend | 38 vitest no baseline; build/lint verdes; frontend inalterado |
| Docs / diff --check | sucesso |
| E2E | não reexecutado em WF-002; última SEC-002: 9 passed / 2 skipped com mocks |
| Agentes CLI reais | nenhum; sem quota real |

## Próximos passos
- WF-003: compilador com equivalência ao grafo legado, snapshot de topologia e suíte atual; revisão independente obrigatória. Ver NEXT_STEPS.
- WF-003/004 cuidarão do compilador e da compatibilidade legacy-v1; não ativar novo padrão antes das decisões humanas.
- F0-002/Q2–Q12 e ADRs aguardam operador; não presumir padrão/permissões/quota. SEC-003 exige validação real autorizada; SEC-003/004 têm revisão humana obrigatória.

## Ambiente
Python 3.9.7 (.venv), LangGraph 0.6.11, Node 22.18.0, Git 2.43.0. Sem dependências novas ou alterações em credenciais.
