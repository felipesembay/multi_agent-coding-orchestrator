# Session log (append-only)

---

## 2026-11-17 — Claude — V2-F0-000 (auditoria e planejamento)

1. **Planejado:** auditar v1 e produzir arquitetura, especificações, design system, roadmap, backlog, ADRs e protocolo de handoff para a v2, sem implementar.
2. **Implementado:** somente documentação (ver CURRENT_STATE). Nenhum código, dependência ou configuração alterados.
3. **Arquivos:** `AGENTS.md`, `CLAUDE.md`, `docs/README.md`, `docs/architecture/**`, `docs/specifications/**`, `docs/design/**`, `docs/planning/**`, `docs/handoff/**`, README (seção "Evolução planejada").
4. **Testes:** pytest 72 passed; vitest 32 passed (com WIP pré-existente). Build/lint/e2e não executados.
5. **Decisões:** ADR-0001..0010 propostos (status `proposto`).
6. **Problemas encontrados:** rotas `/runs*`, `/overview`, `/settings` sem Host check; ambiente completo herdado por agentes; Planner Claude com `acceptEdits`; hooks Git possivelmente executados em `git worktree add` (hipótese); Python 3.9 EOL; padrão atual de agentes difere do desejado; telemetria dos CLIs não verificada.
7. **Pendências:** Q1–Q12 em OPEN_QUESTIONS.
8. **Próxima tarefa:** V2-F0-001 → V2-F0-002 → V2-CORE-001.
9. **Critérios de aceite da próxima:** ver NEXT_STEPS.
10. **Comandos:** ver NEXT_STEPS.

## 2026-11-17 — Codex — início da implementação v2

- [FATO] HEAD `83cebe8` e WIP conferem com CURRENT_STATE; nenhuma divergência inicial identificada.
- [FATO] Q1–Q12 continuam sem decisão registrada. Solicitadas decisões ao operador; nenhum commit, descarte de WIP ou consumo de quota autorizado nesta sessão.
- [RECOMENDAÇÃO] Enquanto as decisões estão pendentes, executar V2-DOC-001 (sem dependências), uma tarefa por vez, com testes locais e handoff.

### V2-DOC-001 — marco de testes

- Implementados `scripts/check_docs.py` e `tests/test_check_docs.py`: links locais/âncoras, IDs declarados no backlog e data do handoff comparada ao último commit de código, sem rede.
- Testes específicos: `python -m pytest -q -p no:cacheprovider tests/test_check_docs.py` → 8 passed; `python scripts/check_docs.py` → documentação válida.
- Baseline frontend: `npm --prefix frontend test` → 32 passed (6 arquivos).
- Operador decidiu preservar WIP **sem commit** e informar decisões depois. Q1–Q12 não foram presumidas; V2-F0-001 não satisfaz critério de baseline limpo e V2-F0-002 aguarda decisões.
- Revisão independente de V2-DOC-001 solicitada conforme AGENT_HANDOFF §4; nenhuma execução de CLI de agente do produto.

### 2026-11-17 — Codex — fechamento V2-DOC-001

1. **Planejado:** iniciar implementação do planejamento; respeitar decisões humanas e escolher tarefa sem dependências enquanto aguardava resposta.
2. **Implementado:** V2-DOC-001, verificação determinística de links locais/âncoras e referências Markdown, IDs completos do backlog e atualização de handoff comparada ao último commit de código.
3. **Arquivos da sessão:** novos `scripts/check_docs.py` e `tests/test_check_docs.py`; atualizados IMPLEMENTATION_PLAN, BACKLOG, OPEN_QUESTIONS, CURRENT_STATE, NEXT_STEPS e SESSION_LOG. `git diff --stat` total: 18 arquivos rastreados, 531 inserções e 277 remoções, todos do WIP preexistente (os arquivos desta sessão permanecem não rastreados, junto com o planejamento). Nenhum arquivo de produto modificado nesta sessão.
4. **Testes:** `ORCH_DB="$(mktemp -d)/events.db" python -m pytest -q -p no:cacheprovider` fora do sandbox → 81 passed, 1 warning, 8,18 s; `npm --prefix frontend test` → 32 passed; `npm --prefix frontend run build` e `npm --prefix frontend run lint` → sucesso; `python scripts/check_docs.py` → sucesso. E2E não executado.
5. **Decisões:** nenhum ADR aceito ou alterado. Operador pediu preservar WIP sem commit e informar decisões depois; Q1 registrada, Q2–Q12 pendentes.
6. **Problemas:** pytest bloqueou no TestClient dentro do sandbox; diagnóstico com faulthandler, interrupção das duas tentativas e execução fora do sandbox autorizada automaticamente. Revisão encontrou links por referência e parênteses sem cobertura; corrigidos, adicionada regressão.
7. **Pendências:** baseline limpo e decisões humanas impedem núcleo v2; nenhum commit criado. Revisão independente `review_doc001` aprovou V2-DOC-001 após correções, 9 testes específicos e validação da documentação.
8. **Próxima tarefa recomendada:** resolver V2-F0-001 e V2-F0-002; depois V2-CORE-001. Tarefas independentes restantes estão listadas em NEXT_STEPS.
9. **Critérios de aceite:** baseline conforme BACKLOG; ADRs aceitos/rejeitados e questões respondidas/adiadas pelo operador; caracterização de argv antes de extrair AgentRuntime.
10. **Comandos:** `python scripts/check_docs.py`; `source .venv/bin/activate`; `ORCH_DB="$(mktemp -d)/events.db" python -m pytest -q -p no:cacheprovider`; `npm --prefix frontend test`; build/lint conforme NEXT_STEPS e IMPLEMENTATION_PLAN.

## 2026-11-17 — Codex — início na branch dev

- [FATO] Branch agora `dev`, criada pelo operador; HEAD permanece `83cebe8`, WIP preservado conforme sessão anterior.
- [FATO] Operador autorizou iniciar implementação e novos commits em `dev`, com testes antes de integrar a main/master. Isso substitui a orientação anterior de não commitar o WIP.
- V2-F0-001 retomada: validar baseline e revisar antes do commit em dev. Q2–Q12 não são implicitamente respondidas pela criação da branch.

### V2-F0-001 — baseline validado para commit em dev

1. Planejado: preservar WIP e estabelecer baseline em dev, conforme nova autorização do operador.
2. Implementado: nenhuma alteração adicional no código do WIP; Q1 e critério de branch do backlog atualizados à instrução do operador.
3. Arquivos: baseline contém WIP de tema/exclusão/migração v3, planejamento e V2-DOC-001 da sessão anterior; `git diff --stat`: 18 arquivos rastreados, 531 inserções e 277 remoções, mais arquivos novos listados em git status.
4. Testes: pytest isolado → 81 passed, 1 warning; vitest → 32 passed; build e lint → sucesso; check_docs → sucesso. E2E não executado nesta etapa.
5. ADRs: sem decisões novas; Q2–Q12 pendentes.
6. Problemas: nenhum bloqueante na revisão independente `review_baseline_dev`; contraste visual/e2e não avaliados.
7. Pendências: decisões humanas de F0-002; não consumir quota real.
8. Próxima tarefa: V2-CORE-001, sem mudança de comportamento.
9. Aceite: caracterizar argv antes da refatoração e preservar testes/patch points existentes.
10. Comandos: baseline em IMPLEMENTATION_PLAN; `python scripts/check_docs.py`.

### V2-CORE-001 — caracterização antes da extração

- Baseline de desenvolvimento commitado em `f8e6949`; árvore limpa antes da tarefa.
- Novo `tests/providers/test_argv_characterization.py` executado contra o core original, antes de mover adapters: 22 casos novos + 7 testes existentes de fallback = 29 passed, 1 warning.
- Cobre argv/cwd/timeout/env/pass_fds de Claude planner/implementer, agy planner/implementer com/sem modelo, Codex reviewer, modelos diretos, fallback, erros agy e defaults.
- Nenhuma chamada real a CLI; `shutil.which` e `subprocess.run` substituídos por mocks. Refatoração só começa após este marco verde.

### V2-CORE-001 — extração e compatibilidade

- Extraídos adapters para `orchestrator/providers/runtimes/` e contrato mínimo Pydantic/Protocol em `base.py`.
- Fachadas `core.claude/codex/antigravity` continuam retornando texto, com mesma assinatura, flags e timeouts. Runner injetado a cada chamada preserva patches `core.run_command`; `coding_agent`, fallback, prompts e eventos permanecem iguais.
- `InvocationResult` contém somente texto nesta tarefa; uso/eventos em CORE-002, manifests/probe/registry em CORE-003. Não antecipados modos read-only de Claude ou workspace-write de Codex.
- Falha inicial de coleta: Pydantic em Python 3.9 não avalia união `str | None`; corrigido usando Optional, sem atualizar Python/dependências. Caracterização + fallback voltaram a 29 passed após a extração.

### V2-CORE-001 — fechamento para commit em dev

1. **Planejado:** extrair AgentRuntime e adapters mantendo comportamento legado, caracterizando argv antes da refatoração.
2. **Implementado:** contratos mínimos Pydantic e Protocol; adapters ClaudeCodeRuntime, CodexCliRuntime, AntigravityRuntime; fachadas compatíveis; runner injetado sem dependência circular do core. CORE-001 concluída após revisão independente `review_core001` (35 testes repetidos, sem achados bloqueantes).
3. **Arquivos:** core.py, providers/{__init__,base}.py, providers/runtimes/{__init__,claude_code,codex_cli,antigravity}.py; tests/providers/test_{argv_characterization,runtime_contract}.py; CURRENT_STATE, NEXT_STEPS, SESSION_LOG, BACKLOG e IMPLEMENTATION_PLAN. Código somente nos caminhos autorizados por NEXT_STEPS; exceção documental necessária ao protocolo. Estatística final será registrada no commit (arquivos novos antes não apareciam em git diff --stat).
4. **Testes:** caracterização antes/depois da extração + fallback: 29 passed; contratos adicionais: suíte focada 35 passed. `ORCH_DB="$(mktemp -d)/events.db" python -m pytest -q -p no:cacheprovider` → 109 passed, 1 warning em 8,13 s. Frontend no baseline: 32 vitest, build/lint verdes, sem alteração posterior. check_docs e diff --check verdes; E2E não executado.
5. **Decisões:** nenhuma decisão humana presumida; mudanças de padrões, permissões, versões e quota ficam nas tarefas próprias. Sem manifest/probe nesta extração, previstos em CORE-003; metadata/usage previstos em CORE-002.
6. **Problemas:** coleta inicial incompatível com uniões Pydantic no Python 3.9; corrigida com Optional, sem instalar dependências. Patch points core.run_command/core.claude/core.antigravity mantidos; não precisou alterar asserts existentes.
7. **Pendências:** Q2–Q12/ADRs; F0-002 continua bloqueada apenas para tarefas dependentes; quota real não autorizada. Segurança legada preservada nesta extração, correções em SEC-*.
8. **Próxima tarefa:** V2-CORE-002, com dependência CORE-001 satisfeita.
9. **Aceite:** completar InvocationResult/UsageReport e um agent_call por chamada, provider/modelo/duração; uso unavailable até parsers, dashboard compatível, testes mockados e revisão distinta.
10. **Comandos:** ativar .venv, pytest com ORCH_DB temporário, npm --prefix frontend test, python scripts/check_docs.py; build/lint conforme IMPLEMENTATION_PLAN. Commits apenas dev; não fazer merge/push/deploy.

- Registro final: commit de CORE-001 criado em dev; estatística preparada antes do commit: 14 arquivos, 369 inserções, 96 remoções. Árvore limpa após commit; CURRENT_STATE ajustado no mesmo commit para refletir conclusão. Consulte `git log -1` para o hash final.

## 2026-11-17 — Codex — V2-CORE-002 início

- [FATO] `dev`, HEAD `87a034f`, árvore limpa; sem divergências do handoff. Operador autorizou CORE-002 e mantém autorização de commits testados em dev.
- Escopo: completar InvocationResult/UsageReport; medir invocações e normalizar códigos de erro sem alterar exceções legadas; eventos agent_call por tentativa de runtime vinculada ao run. Não capturar texto/prompt/ambiente ou raw de CLIs.
- Sem parsers de telemetria: tokens/custos/modelo reportado/session_id permanecem indisponíveis. Sem alterações de flags ou de seleção de agente.

### CORE-002 — marco de testes antes da implementação

- Baseline confirmado: 109 pytest passed (1 warning), 32 vitest passed.
- Escrito `tests/providers/test_invocation_metadata.py` cobrindo duração determinística, uso unavailable, erros preservados/códigos normalizados, fallback por tentativa, privacidade, contexto e planner/implementer/reviewer.
- Vermelho esperado na coleta: UsageReport ainda não existe. Nenhum CLI real executado.

### CORE-002 — marco verde e revisão

- Contratos completos UsageReport/InvocationResult, AgentCall e medição monotônica em CommandRuntime; códigos normalizados em providers/errors.py, exceções originais preservadas para fallback legado.
- Runtime recebe observer opcional. Core usa contexto local por run/papel, resetado em finally, preservando assinaturas das fachadas e seus mocks. Implementer passa state; reviewer associa contexto sem alterar argv.
- Eventos contêm apenas metadados, excluem usage.raw, prompt/output/cwd/env/erros brutos. Sem telemetria verificada: source unavailable, valores nulos, billing unknown, modelo reportado/session nulos. Modelo agy solicitado é registrado após resolver default/env; Claude/Codex defaults desconhecidos permanecem nulos.
- 55 testes focados passed, 1 warning; check_docs válido. Adicionadas regressões API e frontend para agent_call como evento adicional, preservando etapa/status/resultados.
- Chamadas independentes de runtime sem contexto de run retornam metadados; não criam runs/eventos órfãos. Quando uma fachada é substituída por mock integral, não há invocação real de adapter nem evento artificial.

### 2026-11-17 — Codex — fechamento V2-CORE-002

1. **Planejado:** resultados/uso estruturados e evento por invocação de runtime vinculada ao run, mantendo contratos e fallback legados.
2. **Implementado:** UsageReport/InvocationResult/AgentCall; medição monotônica e observer no CommandRuntime; normalização conservadora de erros preservando exceções; contexto por run/papel nas fachadas; implementer com state e reviewer com contexto; dashboard ignora telemetria como etapa. Nenhuma mudança de argv/prompts/seleção.
3. **Arquivos:** core.py, dashboard.py, providers/base.py, providers/errors.py (novo), três runtimes; tests/providers/test_invocation_metadata.py (novo), test_dashboard_api.py; frontend/src/lib/events.test.ts; BACKLOG, IMPLEMENTATION_PLAN, PROVIDER_SYSTEM e documentos de handoff. `git diff --stat` antes da finalização documental: 11 arquivos rastreados, 216 inserções, 24 remoções; novos arquivos e estatística final no commit.
4. **Testes:** baseline 109 pytest / 32 vitest; teste novo vermelho por UsageReport inexistente antes de implementar. Final: ORCH_DB temporário pytest → 130 passed, 1 warning em 8,30 s; testes focados → 55 passed; vitest → 33 passed; build/lint → sucesso; check_docs/diff --check → sucesso. E2E não executado. Nenhuma rede/CLI real/quota consumida pelos testes.
5. **Decisões:** detalhes de implementação documentados em PROVIDER_SYSTEM, coerentes com ADR-0004/0006 propostos; não aceitaram decisões humanas pendentes. Usage unavailable/campos nulos e billing unknown até evidência; sem parsers/usage_records nesta tarefa.
6. **Problemas:** sem bloqueantes. Observer que falha durante erro não oculta causa original; warning sem mensagens/segredos. Persistência que falha após sucesso é propagada. Sem contexto de run não cria evento órfão; mocks integrais de fachadas não simulam chamadas reais.
7. **Pendências:** F0-002/Q2–Q12; parsers reais dependem de autorização de quota e spike F0-003. Revisão independente `review_core002` aprovada, 55 testes focados repetidos e documentação validada, sem achados bloqueantes.
8. **Próxima tarefa:** V2-CORE-003, registry e CapabilityManifest.
9. **Aceite:** GET /providers com built-ins e fake de entry point; plugins de terceiros só por opt-in; probes sem segredos, nenhuma inferência de quota; testes mockados, revisão e handoff.
10. **Comandos:** .venv; ORCH_DB temporário python -m pytest -q -p no:cacheprovider; npm --prefix frontend test; npm --prefix frontend run build; npm --prefix frontend run lint; python scripts/check_docs.py. Commit em dev autorizado, sem merge/push/deploy.
