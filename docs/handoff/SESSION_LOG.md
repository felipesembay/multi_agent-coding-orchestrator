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

## 2026-11-17 — Codex — início V2-CORE-003

- [FATO] `dev`, HEAD `56e44d2`, árvore limpa; handoff confere. Operador autorizou CORE-003; commits testados em dev permanecem autorizados.
- Escopo: manifestos honestos, probes passivos (somente descoberta do executável), registry e GET /providers. Sem inferir versão/autenticação/quota, sem subprocessos no probe.
- provider_configs ainda não existe (WF-002); opt-in será parâmetro explícito do registry, API padrão sem terceiros; futura integração só habilitará configs enabled. Não antecipar migração ou UI.

### CORE-003 — baseline e testes vermelhos

- Baseline: 130 pytest passed (1 warning), 33 vitest passed.
- Escritos testes de registry/API: built-ins honestos, probe passivo, opt-in, entry points legados/select, rejeição de duplicatas/colisão, falhas isoladas sem vazamento, API local sem ativação por query.
- Coleta vermelha esperada: registry ainda inexistente. Nenhum agente CLI chamado.

### CORE-003 — marco verde e revisão

- Manifestos nos três runtimes, Protocol completo manifest/probe/invoke, probe passivo com shutil.which (sem caminho/versão/credenciais inferidos). Todas as verificações permanecem false, billing unknown e usage_source none. Capacidades futuras não anunciadas.
- Registry aceita injeção de runner/observer nos built-ins e factories de terceiros sem argumentos somente com opt-in explícito de nomes. Sem opt-in nem descobre entry points. Compatibilidade select/dict para Python 3.9+, duplicatas/colisões rejeitadas antes de carregar e falhas isoladas em códigos estáticos sem conteúdo de exceção.
- GET /providers protegido pela política local existente (Host/peer/Origin), sem ativação por query. Dependência padrão retorna apenas built-ins; provider_configs ficará em WF-002. Nenhuma mudança em core/fallback/argv.
- Primeira suíte completa: 149 pytest passed, 1 warning. Baseline frontend 33 passed e build/lint verdes. Adicionados mais 5 testes significativos de runner injetado, falha discovery/probe, payload inválido e plugin model_provider; registry 17 passed.

### 2026-11-17 — Codex — fechamento V2-CORE-003

1. **Planejado:** registry, CapabilityManifest, probe e GET /providers, preservando execução legada e sem carregar terceiros por padrão.
2. **Implementado:** contratos Capability/CapabilityManifest/ProbeResult, manifestos atuais dos três adapters, probe shutil.which sem comando/version/auth; registry com lookup/listagem e factories opt-in, compatibilidade entry_points select/dict, validação de identidade/interface e isolamento de falhas. API local protegida sem opt-in HTTP. Nenhuma mudança de core/argv/prompts/fallback.
3. **Arquivos:** api.py, local_security.py (somente incluir rota nova), providers/base.py, três runtimes; registry.py e tests/providers/test_{registry,provider_api}.py novos; BACKLOG, IMPLEMENTATION_PLAN, PROVIDER_SYSTEM, CURRENT_STATE, NEXT_STEPS, SESSION_LOG. `git diff --stat` intermediário: 9 arquivos rastreados, 106 inserções/8 remoções; inclui novos e documentação final no commit.
4. **Testes:** baseline 130 pytest/33vitest; testes novos vermelhos por registry inexistente. Primeira suite 149 verdes; após mais cinco casos de integração/falha, final `ORCH_DB=<tmp> python -m pytest -q -p no:cacheprovider` → 154 passed, 1 warning, 8,32 s. Registry isolado 17 passed. Build/lint frontend e check_docs/diff --check verdes. Frontend inalterado após baseline 33 verdes. E2E não executado.
5. **Decisões:** detalhes documentados em PROVIDER_SYSTEM §6.3, sem aceitar ADRs humanos. Como provider_configs só vem em WF-002, opt-in é configuração explícita do registry e API padrão não habilita plugins; não antecipar migração. Plugins são código confiável instalado; não isolados pelo registry.
6. **Problemas:** nenhum bloqueante. Probes passivos mantêm versão/credenciais desconhecidas; manifesto mostra capacidades atuais, todos verified=false/billing unknown/usage_source none. Não anunciar capacidades de tarefas futuras. Descoberta/importação/probe não expõem mensagens/caminhos/ambiente em erros públicos.
7. **Pendências:** Q2–Q12/ADRs; provider_configs em WF-002, parsers e verificações reais dependem de spike autorizado. Revisão independente `review_core003` aprovada com 52 testes (registry/contrato/caracterização/API) e documentação válida; nenhum agente CLI real executado.
8. **Próxima tarefa:** V2-CORE-004, bindings por papel/runtime/modelo.
9. **Aceite:** env como fonte legada; reviewer configurável internamente; snapshots/digest/idempotência e defaults legacy preservados; caracterização/fallback verdes e sem permissões novas por presunção.
10. **Comandos:** .venv; ORCH_DB temporário python -m pytest -q -p no:cacheprovider; npm --prefix frontend test; build/lint; python scripts/check_docs.py. Commit em dev autorizado, sem merge/push/deploy.

## 2026-11-17 — Codex — início V2-CORE-004

- [FATO] dev, HEAD `6737c2f`, árvore limpa; handoff confere. Operador autorizou CORE-004, mantendo commits testados em dev.
- Escopo: bindings tipados por papel, fonte env somente no adaptador legado, resolução pelo registry e validação de capacidades/permissões atuais. Configuração persistida, digests/idempotência e defaults/fallback legados preservados. Sem novas flags/padrões por presunção de Q2/Q5.
- Baseline em validação; nenhuma quota real autorizada.

### CORE-004 — testes vermelhos

- Baseline 154 pytest / 33 vitest confirmado.
- Escrito tests/providers/test_bindings.py: resolução legada, modelos/defaults, snapshots antigos independentes do ambiente, imutabilidade, rejeição de capacidades/permissões/modelos incompatíveis, fallback congelado, reviewer fake registrado e snapshot do CLI.
- Vermelho esperado: módulo bindings ainda inexistente. Sem chamadas reais de agentes.

### CORE-004 — implementação e primeiro marco verde

- Adicionados RoleBinding/AgentBindings imutáveis; fonte env legada separada, conversão de snapshots sem ler ambiente e validação por registry/capacidades/permissões. Modelos agy default resolvidos deterministicamente; Claude/Codex não aceitam modelos que seus adapters legados ignorariam.
- Core passa por bindings e mantém fachadas/args legados; reviewer interno pode usar runtime registrado com capacidade review/read_only. Novos executores exigem verified; apenas combinações editoras legadas são preservadas nesta etapa. Sem mudar flags/padrões/Q2/Q5.
- Runtime/plugin compartilham invoke_measured; eventos por chamada preservados. execute_scope congela bindings no State e evento started; resume CLI restaura snapshot se presente (runs gerenciados continuam sem retomada).
- execution_runner passa bindings salvos diretamente, sem reescrever variáveis de providers/modelos. Configuração padrão mantém formato/digest antigos; configuração interna explícita inclui bindings e verifica consistência com campos planos.
- Primeiros testes focados: 60 passed (1 warning). Acrescentados testes de digest/preflight, configuração explícita, submissão sem override de bindings e subprocesso real de workflow mockado com ambiente de providers divergente.

### CORE-004 — revisão e ajuste de compatibilidade

- Suíte completa anterior: 171 passed, 1 warning; build/lint verdes. Revisão encontrou dois casos de snapshots antigos sem cobertura: modelo vazio do implementer era convertido para default pelo runner antigo; modelo nulo/vazio do planner usava planner_fallback_model salvo.
- Separada a resolução direta do ambiente (preserva strings vazias) da leitura de snapshots gerenciados antigos (reproduz os testes de truthiness do runner anterior). Adicionados cinco casos de regressão desses formatos.
- Adicionados testes de grafo real LangGraph com reviewer fake e ambiente alterado após planejamento (bindings/contexto persistem sem invocação real), e repetição idempotente após configuração tornar-se inválida.

### CORE-004 — validação de retorno de plugins

- Ao integrar runtimes adicionais, retorno inválido agora é validado dentro da fronteira medida, gera invalid_output e RuntimeError estático. Teste cobre ausência do payload no evento, str e traceback público.
- Revisão adicional detectou que `from exc` preservaria input bruto na cadeia de ValidationError; corrigido para `from None`. Teste inicial do traceback incluía o próprio segredo literal na linha-fonte do teste; movido para variável, mantendo a asserção sobre traceback completo.
- 69 testes focados verdes após correção. Suíte completa anterior: 179 passed, 1 warning; nova execução final será registrada abaixo. Sem mudanças de decisões humanas ou consumo de quota.

### 2026-11-17 — Codex — fechamento V2-CORE-004

1. **Planejado:** bindings por papel/runtime/modelo substituindo env no core, reviewer interno configurável e snapshots/digests legados compatíveis.
2. **Implementado:** RoleBinding/AgentBindings imutáveis, fonte env legada, leitura independente de snapshots, validação de capacidade/permissão/verificação e dispatch; snapshot em State/started e restauração CLI; runner recebe bindings sem reescrever env dos agentes. Config padrão mantém digest/formato; config explícita inclui bindings e confere projeção plana. Sem migração/novo preset, flags ou papéis built-in.
3. **Arquivos:** novos providers/bindings.py e tests/providers/test_bindings.py; core.py, execution_manager.py, execution_runner.py, providers/base.py e errors.py, tests/providers/test_invocation_metadata.py, tests/test_execution_manager.py; DATA_MODEL, PROVIDER_SYSTEM, IMPLEMENTATION_PLAN, BACKLOG, CURRENT_STATE, NEXT_STEPS e SESSION_LOG. `git diff --stat` intermediário (antes de incluir arquivos novos/documentação final): 8 arquivos, 259 inserções/124 remoções; estatística completa no commit.
4. **Testes:** baseline 154 pytest/33 vitest. Testes novos vermelhos antes de implementação por módulo inexistente. Final `ORCH_DB=<tmp> python -m pytest -q -p no:cacheprovider` → 179 passed, 1 warning LangGraph em 9,77 s; 69 focados verdes repetidos pela revisão. Build/lint frontend verdes; frontend inalterado após baseline 33 passed. check_docs/diff --check verdes. E2E não executado. Nenhum agente CLI real/quota.
5. **Decisões:** detalhes registrados em PROVIDER_SYSTEM e DATA_MODEL, coerentes com ADR-0004 e sem resolver Q2/Q5 ou outros ADRs humanos. Exceções editoras preservam somente comportamento legado; novos executores exigem verified. Fallbacks genéricos/novos modos/API models ficam nas tarefas próprias.
6. **Problemas resolvidos:** revisão detectou semântica truthy de modelos em snapshots antigos, corrigida e separada do ambiente direto com regressões. Retornos de plugins validados dentro da fronteira medida; erro estático invalid_output suprime cadeia ValidationError para não vazar input no traceback. Grafo LangGraph mockado, despacho com drift e idempotência após config inválida cobertos.
7. **Pendências:** segurança SEC-001/002/006, validação real SEC-003 só com autorização; F0-002/Q2–Q12/ADRs humanos continuam pendentes. Revisão independente `review_core004` aprovada após correções e delta de privacidade (69 focados).
8. **Próxima tarefa recomendada:** V2-SEC-001, proteger todas as rotas.
9. **Aceite:** SECURITY_GOVERNANCE CA1, Host/loopback/token e integração frontend compatível, testes API/vitest/e2e mockados; revisão e handoff, sem quota real.
10. **Comandos:** ativar .venv; ORCH_DB temporário python -m pytest -q -p no:cacheprovider; npm --prefix frontend test; build/lint; python scripts/check_docs.py. Commit somente dev autorizado; sem merge/push/deploy.

## 2026-11-17 — Codex — início V2-SEC-001

- [FATO] dev, HEAD `db12642`, árvore limpa; origin/dev sincronizada após push autorizado na sessão anterior. Handoff ainda dizia sem push como regra geral; envio anterior foi exceção explícita já executada, nenhum novo push inferido.
- Baseline: 179 pytest (1 warning) e 33 vitest verdes.
- Escopo: middleware local em todas as rotas, token de leitura/escrita (CSRF navegador ou bearer nativo), bootstrap GET /session com controles locais e /health sem token conforme §6.2. Frontend obtém token em memória por chamada sem armazenamento persistente. Não alterar agentes/credenciais nem antecipar supervisor desktop.

### SEC-001 — testes vermelhos

- Escritos tests/security/test_routes_protected.py (matriz global Host/origem/peer/token, bootstrap/headers, bearer, rotação, tamanho de corpo) e frontend/src/lib/api.test.ts (leituras autenticadas, cancelamento, rotação, falha fechada e ausência de replay de escrita).
- Testes backend executados antes da implementação apresentam falhas esperadas nas rotas ainda públicas/sem bearer. Nenhum agente real chamado.

### SEC-001 — middleware e frontend verdes, início de E2E

- Primeira execução de segurança antes do código: 74 failed / 20 passed (vermelho esperado). Após implementação: 94 testes de segurança passaram; suíte completa 273 pytest passed (1 warning), frontend 38 vitest passed.
- Middleware agora cobre todas as rotas, inclusive docs e rotas inexistentes: Host estrito/único, peer loopback, origem, token CSRF para reads/writes ou bearer nativo, corpo limitado em bytes reais e headers em sucessos/rejeições. GET/HEAD health e session são exceções locais de bootstrap/liveness. API_TOKEN nativo não exposto por session; override opcional app.state.api_token apenas em memória.
- Frontend busca token por operação (também leituras), sem armazenamento/replay; cancelamento propagado. Clientes de testes API adaptados para autenticação real sem afrouxar política.
- Build frontend passou; lint inicial encontrou nome de callback Playwright `use` confundido com React hook; renomeado `provide`, sem desabilitar regra. Lint novamente em execução.
- E2E iniciado em banco/repositórios temporários /tmp/orchestrator-execution-qa.*, API/worker do harness de mocks e Vite dedicados, sem quotas. Fixtures de request Playwright obtêm token e novas verificações cobrem acesso anônimo e recarga da UI.

### SEC-001 — E2E verde

- Playwright em API/worker/Vite de QA temporários: 9 passed, 2 skipped em 11,3 s. Fluxo completo supervisionado com agentes mockados passou, assim como autenticação browser, reads anônimos negados, recarga, temas e navegação responsiva.
- Dois opt-ins não habilitados: escrita/criação de projetos em raiz projects-qa e cenário de exclusão em raiz ui-qa (guardrails próprios); nenhum teste foi apontado ao banco de uso real.
- Lint passou após renomear callback de fixture; encerrados serviços dedicados de QA. Nenhuma invocação de agente real nem quota.

### 2026-11-17 — Codex — fechamento V2-SEC-001

1. **Planejado:** política local global e token em leituras/escritas, mantendo frontend web e contratos HTTP existentes.
2. **Implementado:** middleware único em todas as rotas, Host estrito/único, peer loopback, Origin/cross-site, CSRF ou bearer independente por processo, corpo real limitado e headers em sucessos/rejeições. GET/HEAD /session bootstrap e /health liveness sem token sob mesmos controles locais. Frontend obtém token por operação sem persistência/replay; API tests/e2e autenticados. Sem alteração de agentes/modelos/Git/credenciais.
3. **Arquivos:** local_security.py, api.py, project_api.py; frontend lib/api.ts e projects.ts, dashboard.test.tsx; novos lib/api.test.ts, e2e/fixtures.ts e security.spec.ts, quatro specs e2e adaptados; tests/security/test_routes_protected.py novo, fixtures de dashboard/projects/execution_manager/provider_api autenticadas; README, frontend/README, execution-manager, SECURITY_GOVERNANCE, plano/backlog/handoff. git diff --stat intermediário antes de novos arquivos/docs finais: 17 arquivos, 133 inserções/49 remoções; completo no commit.
4. **Testes:** baseline 179 pytest/33 vitest. Antes do código, testes novos backend → 74 failed/20 passed (vermelho esperado). Final pytest isolado → 273 passed, 1 warning em 10,36 s; segurança → 94 passed; vitest → 38 passed. Build/lint verdes (callback Playwright use renomeado provide para não conflitar com regra React). E2E → 9 passed/2 skipped em 11,3 s no harness temporário, inclui workflow supervisionado/recarga/autenticação. Dois opt-ins de escrita específicos não executados; nenhuma quota/CLI real.
5. **Decisões:** bootstrap /session e liveness /health documentados explicitamente em SECURITY_GOVERNANCE/READMEs, incluindo limites de mesmo usuário/SO e API em processo único; integração supervisor/Tauri fica em DESK-002/004. Nenhum ADR humano aceito por presunção.
6. **Problemas:** sem bloqueantes na revisão; lint de fixture resolvido sem desabilitar regra. API clients antigos precisam enviar token também em reads; fixtures atualizadas sem alterar asserts de comportamento. Não há replay de mutações em 403 por rotação entre bootstrap e operação.
7. **Pendências:** SEC-002/003/004/006 e F0-002/Q2–Q12 permanecem; SEC-003/004 exigem revisão/validação humana nos termos da especificação. Revisão independente `review_sec001` aprovada: 109 testes Python focados, 38 vitest e docs válidos; sem achados bloqueantes. Serviços QA encerrados.
8. **Próxima tarefa:** V2-SEC-002, ambiente por allowlist.
9. **Aceite:** CA2 segredo-sentinela não chega ao agente fake; preservar variáveis declaradas necessárias, sem quota/CLIs reais; testes de ambiente real do subprocesso, revisão distinta e handoff.
10. **Comandos:** .venv; ORCH_DB temporário python -m pytest -q -p no:cacheprovider; npm --prefix frontend test/build/lint; python scripts/check_docs.py. E2E conforme execution-manager em harness temporário e EXECUTION_E2E_MOCKED=1. Commit dev autorizado; sem merge/deploy/novo push (push anterior era autorização específica até db12642).

## 2026-11-17 — Codex — início V2-SEC-002

- [FATO] dev, HEAD `8d94e7d`, árvore limpa; handoff confere, sem novo push autorizado. Baseline em validação.
- Escopo: allowlist por runner/adapter/tests/git, sem herdar segredos arbitrários. Config paths de CLI declarados, extensões explícitas por escopo e nomes congelados no snapshot/digest quando configurados; sem valores no banco.
- [FATO] ORCH_DISPATCH_TOKEN também prova identidade de descendentes quando o runner encerrou; preservar apenas esse marcador interno nos filhos é necessário para manter recuperação segura de órfãos. Não confundir com credenciais de API.
- Não chamar agentes reais, consumir quota ou mudar flags/permissões/hooks (SEC-006 permanece separada).

### SEC-002 — testes vermelhos

- Baseline 273 pytest (1 warning) / 38 vitest verdes.
- Escrito tests/security/test_env_allowlist.py: allowlist exata, extensões por escopo, configuração inválida sem conteúdo em erros, marcador de supervisão, runtime com manifesto, /proc de agente Python fake real e runner fake via Worker.spawn, helpers Git/testes.
- Coleta vermelha esperada: pacote policy ainda inexistente. Nenhum agente CLI real chamado.

### SEC-002 — primeiro marco verde

- Policy env implementada com nomes exatos, escopos runner/adapter/tests/git, extensões ORCH_ENV_ALLOWLIST e declarações environment_variables no manifesto. Sem glob ou nomes de credenciais/loader/controles reservados em extensões; caminhos Claude/Codex declarados. Valores nunca entram no snapshot.
- Worker.spawn filtra ambiente e preserva apenas controles necessários; permissões de nomes congeladas em managed_runs.config/digest quando não vazias. Runner revalida/aplica snapshot; configuração padrão não muda formato/digest.
- Runtime filtra também com runner injetado; core filtra novamente na fronteira de subprocess.run e resolve executável com PATH efetivo. Helpers Git filtrados sem antecipar flags/hooks de SEC-006. Marcador de supervisão gerado preservado e não substituível por env explícito.
- 16 testes novos de ambiente passaram, incluindo /proc de agente Python fake e runner fake reais. Testes antigos que exigiam env=None/ambiente cru foram ajustados para o contrato de segurança novo mantendo argv/cwd/timeouts/pass_fds. Mocks shutil.which agora aceitam path explícito. Rodada focada com TestClient no sandbox foi interrompida; suíte completa reexecutada fora do sandbox conforme baseline.

### SEC-002 — revisão e correção de colisão de escopo

- Primeira suite completa: 289 passed, 1 warning. Revisão independente encontrou colisão entre adapter/provider e nomes internos runner/tests/git, permitindo selecionar escopo privilegiado.
- Reservados os três IDs em manifestos, registry e environment_scope; CommandRuntime exige provider==manifest.adapter. Testes de regressão cobrem IDs internos e divergência de identidade com proxy autorizado a outro adapter.
- Worker.environment extraído para reutilizar a mesma política na fixture managed_server. Testes adicionais cobrem digest de nomes sem valores, stale confirmation e Worker.spawn/handshake/cleanup reais usando somente executável fake e agentes mockados.

### SEC-002 — validação final e E2E

- Suite completa final: 301 pytest passed, 1 warning, 12,26 s. Frontend baseline 38 vitest e build/lint verdes (frontend inalterado).
- Revisão independente review_sec002 aprovada após correção de escopos: 93 testes focados e documentação válida.
- E2E repetido em QA temporário com managed_server reutilizando Worker.environment de produção: 9 passed / 2 skipped em 11,4 s; workflow supervisionado com agentes mockados passou. Dois opt-ins de criação/exclusão em outras raízes não habilitados. Serviços API/worker/Vite encerrados.
- Teste real de recuperação matou apenas o runner criado pelo teste e comprovou cleanup do descendente Python filtrado pelo marcador interno. Nenhum CLI real, quota ou dados de produção.

### 2026-11-17 — Codex — fechamento V2-SEC-002

1. **Planejado:** substituir ambiente herdado por allowlists por escopo, preservando configuração legítima e identificação de órfãos; testar segredos-sentinela sem CLIs reais.
2. **Implementado:** policy/env.py com base exata, contextos de escopo/configuração, extensões validadas e snapshots; environment_variables em manifestos; filtro em runtime/core/worker/helpers Git. Worker.environment compartilhado com harness. Marcador interno confiável preservado; scopes internos reservados e identidade runtime validada. Default de configuração/digest inalterado, nomes de extensões opcionais cobertos pelo digest, sem valores. Sem mudar flags/hooks/permissões ou instalar dependências.
3. **Arquivos:** novos policy/{__init__,env}.py, tests/security/test_env_allowlist.py, tests/fixtures/environment_workflow.py; core, execution_manager, execution_runner, worker, projects, repository_lock, providers/base/registry e runtimes Claude/Codex; caracterização/contrato/metadata/registry/manager tests e managed_server fixture; README, frontend/README, execution-manager, DATA_MODEL, PROVIDER_SYSTEM, SECURITY_GOVERNANCE, plano/backlog/handoff. git diff --stat intermediário sem arquivos novos/docs finais: 12 arquivos, 78 inserções/32 remoções; completo no commit.
4. **Testes:** baseline 273 pytest/38 vitest. Teste novo vermelho por policy ausente; 16 casos de ambiente iniciais verdes. Após regressões: ORCH_DB temporário pytest final → 301 passed, 1 warning em 12,26 s. Build/lint frontend verdes; frontend inalterado após 38 vitest. E2E com QA isolado/harness filtrado → 9 passed/2 skipped em 11,4 s. Check_docs/diff --check verdes. Nenhum agente CLI real/quota; serviços QA encerrados.
5. **Decisões:** detalhes em SECURITY_GOVERNANCE/PROVIDER_SYSTEM/DATA_MODEL. Credenciais de API ambientais não autorizadas por extensão; keyring/API em SEC-005/PROV-001. ORCH_DISPATCH_TOKEN é identificação interna, não credencial de API; necessário a recovery. Nomes congelados, valores resolvidos no spawn e não salvos nesse campo. Nenhum ADR humano aceito por presunção.
6. **Problemas resolvidos:** testes antigos env=None/ambiente cru ajustados somente para nova política, preservando argv/cwd/timeouts/fds; mocks which aceitam PATH efetivo. Revisão identificou colisão runner/tests/git, corrigida em manifesto/registry/contexto + provider==manifest.adapter, com regressões. Snapshots falsy inválidos não são defaults silenciosos. Um teste focado com TestClient no sandbox foi interrompido e repetido fora como baseline.
7. **Pendências:** SEC-006 hooks/config local Git, SEC-003/004 com revisões/validações humanas próprias; F0-002/Q2–Q12. Revisão independente review_sec002 aprovada (93 focados + docs); sem bloqueantes. Dois opt-ins e2e de criação/exclusão em outras raízes não habilitados. Allowlists não são isolamento de SO ou detector do conteúdo de variáveis autorizadas.
8. **Próxima tarefa:** V2-SEC-006, Git seguro.
9. **Aceite:** CA4 com repositório Git temporário e hook post-checkout sentinela, sem execução do hook em prepare; manter locks/worktree/diffs/status, testes e revisão distinta.
10. **Comandos:** .venv; ORCH_DB temporário python -m pytest -q -p no:cacheprovider; npm --prefix frontend test/build/lint; python scripts/check_docs.py. E2E conforme execution-manager com EXECUTION_E2E_MOCKED=1 em QA temporário. Commit somente dev autorizado, sem merge/push/deploy.

## 2026-11-17 — Codex — início V2-SEC-006

- [FATO] dev, HEAD `065d9ed`, árvore limpa e handoff conferidos; sem novo push autorizado. Baseline em execução. Git local 2.43.0, sem agentes reais.
- Escopo: política compartilhada de hooks/fsmonitor/diff/textconv em Git do orquestrador, preservando ambiente/fds. Testes reais em repositórios temporários com sentinelas.
- Inspeção identificou também filtros clean/smudge/process, que podem executar comandos em status/checkout. Preparação será fail-closed para esses filtros e usará worktree sem checkout antes de validar configuração efetiva da nova branch; não alterar config do repositório ou credenciais.

### SEC-006 — testes vermelhos e confirmação de risco

- Baseline: 301 pytest (1 warning) / 38 vitest verdes.
- Escrito tests/security/test_git_hooks.py: controles positivos e regressões reais para post-checkout, fsmonitor, conversores de diff, filtros de conteúdo, includeIf por branch e aliases/opções globais.
- Primeira rodada antes do código: 13 falhas esperadas de proteção ausente; dois controles de clean/process via status não executaram conversão, corrigidos para hash-object --path (comando explícito de conversão). Post-checkout/fsmonitor/diff/textconv reproduzidos no Git 2.43.0.
- Referências oficiais consultadas: git-scm.com/docs/githooks.html (post-checkout/worktree --no-checkout), git-diff (no-ext-diff/no-textconv), git-config e gitattributes. Nenhum agente real ou quota.

## 2026-11-18 — Codex — continuação V2-SEC-006

- Operador pediu status; trabalho mantido na mesma tarefa. Última suíte completa anterior: 319 passed (1 warning), frontend 38 passed e build/lint verdes.
- Revisão identificou bypass `worktree add --check` e negação `status --no-ignore-submodules`; corrigidos usando formas completas autorizadas, branch agent/run-<12hex> e target absoluto. Adicionadas regressões de abreviações/negações; 47 testes Git+ambiente passaram após correção.
- Revisor review_sec006 atingiu limite de uso antes de aprovar a correção final. Não declarar done nem commitar como tarefa concluída sem revisão distinta, conforme AGENT_HANDOFF §4. Suíte completa final em execução; sem merge/push, credenciais alteradas ou CLI de agente real.

### 2026-11-18 — Codex — fechamento V2-SEC-006

1. **Planejado:** impedir hooks/configuração executável do Git em prepare/run_command e unificar os helpers, com repositórios/sentinelas temporários.
2. **Implementado:** policy/git.py compartilhada por core/projects/locks, formas completas não interativas e configurações fixas de segurança; consulta de filtros efetivos/includes sem revelar valores; prepare em duas etapas sem checkout inicial, validando branch antes de reset --hard HEAD. Sem alterar config original/credenciais/CLI de agentes, merge/push/deploy.
3. **Arquivos:** novos policy/git.py e tests/security/test_git_hooks.py; core.py, projects.py, repository_lock.py, test_env_allowlist.py (mock das consultas extras); README, frontend/README, execution-manager, SECURITY_GOVERNANCE, plano/backlog/handoff. Estatística completa no commit; nenhuma migração/dependência nova.
4. **Testes:** baseline 301 pytest / 38 vitest. Vermelho inicial de 13 casos antes de código; controles clean/process ajustados para conversão explícita. Final pytest isolado → 323 passed, 1 warning, 14,30 s; 47 Git+env focados; revisão 69 focados. Build/lint frontend verdes; frontend inalterado após baseline 38 vitest. Check_docs/diff --check verdes. E2E não repetido; integração Git/worktree/LangGraph/worker com mocks consta no pytest. Nenhum CLI de agente real.
5. **Decisões:** risco post-checkout confirmado em Git2.43 com controle positivo; filtros executáveis recusados em vez de rodar código implicitamente. Formas Git limitadas às necessárias, sem aliases/opções interativas. Includes por branch exigem worktree sem checkout e segunda validação. Documentados limites/compatibilidade e fontes primárias Git; ADRs humanos continuam propostos.
6. **Problemas resolvidos:** revisão reproduziu --check reativando checkout e --no-ignore-submodules alterando inspeção; corrigidos com allowlist de formas completas, branch gerada válida e target absoluto, regressões reais. Um assert antigo contava só comandos e foi adaptado para consultas extras mantendo verificação de ambiente em todos os subprocessos. Revisor atingiu limite de uso, retomou e aprovou delta final.
7. **Pendências/limites:** filtros executáveis locais (incluindo LFS local) não suportados; worktree vazia/branch podem permanecer para inspeção se include condicional é recusado após registro. Não intercepta Git que testes/agentes executem fora do wrapper nem elimina corrida de processo malicioso do mesmo usuário; SEC-008 futura. Revisão independente review_sec006 aprovada, sem bloqueantes. Sem commit/push até fechamento desta entrada; commit dev autorizado a seguir.
8. **Próxima tarefa:** V2-WF-001, schema e validação de workflows.
9. **Aceite:** WORKFLOW_ENGINE §6.2, exemplos válidos/inválidos com registry/capacidades e restrições MVP; sem antecipar compilador/migração/preset padrão ou decisões Q2/Q5, revisão distinta/handoff.
10. **Comandos:** ativar .venv; ORCH_DB temporário python -m pytest -q -p no:cacheprovider; npm --prefix frontend test/build/lint; python scripts/check_docs.py. Commit dev testado/revisado autorizado, sem merge/push/deploy.


## 2026-11-18 — Codex — V2-WF-001 início
- Planejado: schema versionado e regras WORKFLOW_ENGINE §6.2; CORE-003 satisfeita. ADR-0005 proposto consultado, sem mudar defaults/decisões humanas.
- Branch dev limpa, HEAD 7ac3634, sem divergência; 3 commits locais já registrados, sem push autorizado novo.
- Baseline: ORCH_DB temporário python -m pytest -q -p no:cacheprovider: 323 passed, 1 warning; npm --prefix frontend test: 38 passed. Sem CLI real.

### WF-001 — testes/primeiro marco
- Testes novos tests/workflows/test_schema.py: vermelho confirmado por ModuleNotFoundError antes do schema; depois 37 passed. Contratos e validação estrutural criados em orchestrator/workflows/{schema,validation}.py; validação de bindings ainda sendo coberta.

### WF-001 — validação verde / revisão
- 68 testes focados passaram. Fakes verificam capacidades/permissões, code_edit verificado, fallback superset, aprovação e topologia; nenhuma invocação/probe. Inconsistência no fake corrigida para usar enum Capability ao mutar manifesto.
- Limites de contrato complementam faixas existentes: 100 etapas declaradas/10000 passos; documenter é papel de document, escrita exige runtime code_edit verificado. Retornos MVP somente review→implement com max_attempts e no mesmo bloco. Não alteram decisões de default nem política de CLI.

### WF-001 — fim / revisão aprovada
- Implementado: V2-WF-001, schema v1 e validação pura, sem dependências novas, sem integração ao executor/API/persistência. Definição e bindings separados; erros Pydantic por campo. Código em orchestrator/workflows/{__init__,schema,validation}.py; testes em tests/workflows/{__init__,conftest,test_schema,test_validation}.py.
- Revisão review_wf001 apontou container inválido e Literal[False] aceitando 0; corrigidos com TypeAdapter/caminho bindings e validator booleano estrito. Revisor reexecutou 75 focados e aprovou. Falhas de manifesto de plugins são estáticas; document write verificado também coberto.
- Testes: ORCH_DB temporário python -m pytest -q -p no:cacheprovider: 398 passed, 1 warning LangGraph, 22,19s; npm --prefix frontend test: 38 passed no baseline, frontend inalterado; npm --prefix frontend run build e run lint: sucesso. python scripts/check_docs.py e git diff --check: sucesso. E2E não rodado; agentes reais não chamados.
- Arquivos: sete novos arquivos de código/testes, além de CURRENT_STATE, NEXT_STEPS, SESSION_LOG, IMPLEMENTATION_PLAN, BACKLOG e WORKFLOW_ENGINE. Estatísticas finais verificadas no diff antes do commit.
- Decisões: ADR-0005 continua proposto, sem alteração de ADR/padrão. Faixas de servidor e refinamentos do schema documentados em WORKFLOW_ENGINE §6.2.1. Sem bypass legacy por nome; compatibilidade no caminho atual e futura equivalência WF-003/004.
- Pendências: compilador/migração/API/presets fora desta tarefa; F0-002 decisões humanas ainda pendentes. Sem merge/push/deploy; commit local em dev autorizado.
- Próxima tarefa recomendada V2-WF-002: migração aditiva v4 preservando dados v3 e snapshots/digests; upgrade/reabertura idempotente com DB temporário. Ler DATA_MODEL/PERSISTENCE/WORKFLOW_ENGINE e iniciar com git status/log, baseline pytest isolado e npm --prefix frontend test. Handoff, revisão e commit dev após verdes.


## 2026-11-18 — Codex — V2-WF-002 início
- Planejado: migração aditiva v4 conforme DATA_MODEL, WORKFLOW_ENGINE e PERSISTENCE, com upgrade v3, atomicidade/reabertura e concorrência. CORE/WF-001 prontos; ADR-0005 proposto consultado. Q2–Q12 não bloqueiam esta tarefa, sem presumir respostas.
- Dev limpa em caee20e, 4 commits à frente de origin/dev sem autorização nova de push; sem divergência com handoff. Baseline ORCH_DB temporário python -m pytest -q -p no:cacheprovider: 398 passed, 1 warning (14,49 s); npm --prefix frontend test: 38 passed.

### WF-002 — testes vermelhos
- Criados tests/workflows/test_migration.py e fixture SQL v3 congelada de caee20e, independente das constantes atuais. 14 falhas esperadas antes da implementação: versão 4/tabelas/colunas ausentes. Cobertura de preservação integral de linhas e índices, fresh/reopen, concorrência, rollback, integridade de referências/JSON e imutabilidade de versões.

### WF-002 — migração verde / revisão
- 26 testes novos passaram após WORKFLOW_MIGRATION e aplicação em transação BEGIN IMMEDIATE com rechecagem sob lock. Schema congelado garante independência do teste de upgrade.
- Tabelas workflow_definitions/workflow_versions/provider_configs, colunas managed_runs anuláveis, índice de FK e constraints básicas. Triggers recusam update/delete/replace de versões. Sem seed/provider habilitado, sem inferir Q2/Q5; estado padrão legado intacto.
- Contrato de implantação: JSON1 disponível no SQLite 3.36.0 local; checks apenas integridade JSON básica. Validação Pydantic de body deve ser aplicada no futuro caminho de escrita, ainda inexistente nesta tarefa de migração.

### WF-002 — fim / revisão aprovada
- Implementado V2-WF-002: migração v4 aditiva em orchestrator/project_store.py; três tabelas e três colunas nullable, índice/FKs/JSON/digests, versões imutáveis inclusive REPLACE. Nenhuma tabela legada recriada, nenhum dado alterado/seed inserido. Registry/execução permanecem iguais.
- Arquivos: project_store.py, tests/workflows/test_migration.py, tests/fixtures/platform_v3.sql, DATA_MODEL, IMPLEMENTATION_PLAN, BACKLOG e três documentos de handoff. Estatísticas finais inspecionadas no staged diff antes do commit.
- Testes: ORCH_DB temporário python -m pytest -q -p no:cacheprovider: 424 passed, 1 warning LangGraph, 15,09s; 26 novos casos de migração. npm --prefix frontend test: 38 passed no baseline (frontend intacto); npm --prefix frontend run build e run lint: sucesso. python scripts/check_docs.py e git diff --check: sucesso. E2E não reexecutado; nenhum agente CLI real ou quota consumida.
- Revisão review_wf002: 101 testes de workflows verdes, aprovada sem bloqueios. SQL v3 congelado garante que upgrade não reaproveita schema novo como baseline.
- Decisões: ADR-0005 permanece proposto; nenhuma resposta Q2–Q12 presumida. JSON1 requerido e disponível no SQLite3.36.0; provider_configs vazio/enabled default0. Escrita futura de body deve validar Pydantic e impedir segredos em settings; não há CRUD/API/caminho de escrita nesta tarefa, apenas constraintsSQL básicas. Imutabilidade impõe nova versão para editar.
- Problemas: nenhum bloqueio; triggers incluem proteção BEFORE INSERT para REPLACE, que pode omitir DELETE triggers com configuração SQLite padrão. Rollback/concurrency/failure injection e preservação de sequência de eventos cobertos.
- Pendências: Q2–Q12, integração de CRUD/API, presets, compilador e snapshot no executor em tarefas próprias. Sem merge/push/deploy; commit local dev autorizado após testes/revisão.
- Próxima recomendada: V2-WF-003. Aceite: equivalência legacy-v1 ao core.graph, snapshot de topologia e suíte existente. Ler WORKFLOW_ENGINE/ADR-0005/core/bindings; compatibilidade explícita sem bypass por nome ou mudanças dependentes de Q2/Q5. Comandos: git status/log; source .venv/bin/activate; ORCH_DB temporário python -m pytest -q -p no:cacheprovider; npm --prefix frontend test; revisão/handoff/commit dev após verdes.


## 2026-11-18 — Codex — V2-WF-003 início
- Solicitado resumo de entregas/pendências, apresentado antes da implementação. Planejado compilador definição→StateGraph, equivalência exata do legado, limites/loop e executores injetados; integração CLI/API/snapshots/fallbacks/presets ficam em tarefas próprias.
- Plano/handoff/WORKFLOW_ENGINE/ADR-0005 lidos; dependências WF-001/CORE-004 done. Dev limpa fc93cd1, cinco commits locais sem push novo autorizado. Baseline pytest isolado:424 passed,1 warning,14,86s; vitest38. Sem divergência ou quota real.

### WF-003 — marcos de testes e código
- Snapshot legacy_graph_topology.json capturado de fc93cd1 antes de alterar core.graph: três pontos de entrada passaram na caracterização original. Teste novo de compilador vermelho (ModuleNotFoundError) antes da implementação.
- compiler.py/nodes.py criados; core.graph agora delega ao layout privado legado com os mesmos callbacks (testes continuam dentro de review). Compilador público estrito usa executores injetados, sem bypass por nome.
- 28 testes novos de compilador/topologia verdes: retries/tarefas/limites/gates/falhas/imutabilidade/ordem e evidência fresca após escrita. Budget e fallback configurados recusados até integrações próprias, sem ignorar configuração.

### WF-003 — regressão completa intermediária
- Suite completa após primeiro conjunto: 452 passed, 1 warning LangGraph,15,06s. Build/lint verdes. Dois casos adicionais (test global inicial e gate explícito reutilizado) entram na suíte final após revisão. Contrato/limitações dos executores e fronteiras com WF/OBS/RES documentados em WORKFLOW_ENGINE §6.3.1.

### WF-003 — fim / revisão aprovada
- Implementado V2-WF-003: compiler.py/nodes.py, core.graph delegando ao layout legado privado e duas suítes novas com fixture JSON congelada antes da refatoração. Compilador strict de definições com executores host síncronos obrigatórios, configuração congelada, etapas/gates/bloco por tarefa/loops limitados, contagem/prazo e evidências ligadas à última escrita. Contrato documentado em WORKFLOW_ENGINE §6.3.1.
- Arquivos: core.py, workflows/compiler.py e nodes.py, tests/workflows/test_compiler.py e test_legacy_topology.py, tests/fixtures/legacy_graph_topology.json, WORKFLOW_ENGINE, IMPLEMENTATION_PLAN, BACKLOG e três documentos de handoff. Estatísticas finais inspecionadas no staged diff antes do commit.
- Testes finais: ORCH_DB temporário python -m pytest -q -p no:cacheprovider: 454 passed, 1 warning LangGraph,14,83s; 30 casos novos. npm --prefix frontend test:38 passed no baseline (frontend intacto); build/lint verdes. python scripts/check_docs.py e git diff --check:sucesso. E2E não rodado; nenhum agente CLI real/quota de agente.
- Revisão review_wf003 aprovada sem bloqueios,134 focados workflows/core verdes. Revalidados casos adicionais de teste global inicial e gate explícito reutilizado. Nenhum assert de testes existentes alterado; topologia e callbacks/entradas plan/implement/review do legado preservados.
- Decisões/limites: ADR-0005 permanece proposto, sem presumir Q2–Q12. Novo compiler não é ativado na UI/worker; executores são dependência confiável do host e não carregam CLIs implicitamente. Ledger/uso/gates persistidos/concretização CLI/API pertencem a tarefas próprias. Budget/fallback configurados falham explicitamente em vez de ignorar campos. Deadline síncrono é cooperativo via timeout_s; verificações antes/depois não interrompem callback arbitrário.
- Problemas prevenidos nos testes: falha no segundo bloco não repete tarefa; revisão anterior a escrita não aprova mudanças posteriores; documento escritor exige novas evidências; gate existente após plano não pede duas aprovações. Sem bloqueios atuais.
- Pendências: presets WF-004 com Q2 antes de concluir/ativar; snapshots WF-007 e demais áreas. Nenhum merge/push/deploy. Commit local dev após revisão/testes autorizado.
- Próxima tarefa: WF-004 após decisão humana Q2; alternativa liberada WF-007 (snapshot/digest por run). Aceite WF-004: presets A/B/C/legacy validam com fakes, CLI legado e decisões registradas; B sem ativação até PROV-001. Aceite WF-007: edição após enfileirar não muda snapshot, idempotência/digest testados. Ler NEXT_STEPS/WORKFLOW_ENGINE/OPEN_QUESTIONS; git status/log; source .venv/bin/activate; ORCH_DB temporário python -m pytest -q -p no:cacheprovider; npm --prefix frontend test; revisão/handoff/commit dev após verdes.


## 2026-11-18 — Codex — V2-F0-002 registro de decisões / início
- Planejado registrar decisões humanas recebidas Q2–Q12, ajustar dependências e pontos específicos dos ADRs sem declará-los integralmente aceitos. Uma tarefa por vez; nenhuma nova implementação executada.
- Dev limpa em 1474f4b (seis commits locais à frente de origin/dev), sem divergência. Baseline pytest com ORCH_DB temporário:454 passed,1 warning LangGraph,15,49s; vitest38. Sem build/lint/e2e nesta sessão exclusivamente documental; sem consumo de quota real.
- Esclarecimentos via operador: Q2 novo padrão Claude → Codex → Antigravity, com liberdade de escolha por etapa; Q7 licença específica explicitamente adiada. Q10 autoriza poucos prompts triviais nos spikes previstos; mocks permanecem obrigatórios em testes automatizados. Q11 autoriza commits apenas em worktree/branch de run após tarefa aprovada.

### F0-002 — marco documental / revisão
- OPEN_QUESTIONS registra respostas com data; Q2 esclarecida presetA, Q7 explicitamente adiada, Q6 assinatura/Q8 valor ainda indefinidos. Pontos específicos de ADR-0001/2/3/6/7 sincronizados sem aceitar ADRs integralmente. Q11 deixa de figurar como alternativa rejeitada ao ledger: commits aprovados são complemento, não substituição.
- Backlog/DEPENDENCIES/IMPLEMENTATION_PLAN/WORKFLOW_ENGINE e handoff atualizados. Nenhum código, dependência, configuração ou LICENSE criado/alterado. check_docs e diff --check verdes. Revisão independente solicitada antes de commit documental.

### F0-002 — fim do registro parcial / revisão aprovada
- Registradas decisões Q2–Q12 em OPEN_QUESTIONS com data, incluindo esclarecimento de novo default preset A e adiamento explícito da licença. ADRs específicos alinhados a Q3/4/6/8/9/11 sem mudar status integral de proposto. Nenhum LICENSE/código/configuração/dependência alterado.
- Arquivos modificados: OPEN_QUESTIONS, BACKLOG, DEPENDENCIES, IMPLEMENTATION_PLAN, WORKFLOW_ENGINE, ADR-0001/0002/0003/0006/0007 e CURRENT_STATE/NEXT_STEPS/SESSION_LOG (13 documentos). Estatísticas finais verificadas no staged diff antes do commit.
- Testes/verificações: baseline pytest isolado454 passed,1 warning,15,49s; vitest38. check_docs e git diff --check verdes após mudanças. Não reexecutados build/lint/e2e por escopo só documental; nenhum agente CLI real/quota executado.
- Revisão independente review_decisions_f0002 aprovada, sem achados bloqueantes; escopo das decisões/autorização preservado. F0-002 retorna blocked residual por revisão formal integral dos ADRs, sem reaplicar bloqueios a perguntas já respondidas. Registro desta sessão completo, tarefa ampla não declarada done.
- Decisões não escolhidas: licença específica (adiada pelo operador), assinatura de pacotes, valor monetário de orçamento e identidade definitiva. Não bloqueiam tarefas independentes.
- Próxima recomendada WF-004: presets A/B/C/legacy e escolha por etapa; Q2/Q5 resolvidas, execução concreta ainda depende de segurança/capacidades implementadas, B desabilitado até PROV-001. F0-005 Python3.12 e spikes F0-003/SEC-003 especificamente autorizados podem ser escolhidos em sessões separadas; uma tarefa por vez.
- Para continuar: git status/log; ler IMPLEMENTATION_PLAN/NEXT_STEPS/OPEN_QUESTIONS e especificação da tarefa; source .venv/bin/activate; ORCH_DB temporário python -m pytest -q -p no:cacheprovider; npm --prefix frontend test. Critérios WF-004: presets com fakes, escolhas por etapa, CLI legado preservado, revisão/handoff após verdes. Sem merge/push/deploy.


## 2026-11-18 — Codex — V2-WF-004 início
- Planejado catálogo legacy-v1/A/B/C, clonagem/configuração por etapa, validação de manifestos/fakes e compatibilidade CLI, sem API/editor/seed/novas flags reais. Q2/Q5 recebidas no registro588c6db; ADR-0005 consultado e permanece proposto.
- Dev limpa em588c6db, sete commits locais à frente de origin/dev; sem divergência. Baseline ORCH_DB temporário python -m pytest -q -p no:cacheprovider:454 passed,1 warning LangGraph,31,83s; npm --prefix frontend test:38 passed. Nenhum CLI real/quota.

### WF-004 — testes e primeiro marco verde
- tests/workflows/test_presets.py vermelho por ModuleNotFoundError antes do módulo; após criação presets.py,16 casos iniciais passaram. Ampliados com clonagem/seleção inválida, execução LangGraph com runtimes fakes e CLI.main→execute_scope sem subprocessos/agentes reais.
- Catálogo sem env/discovery/DB, quatro entradas, default futuro UI A/CLIlegacy; B bloqueado por PROV-001. A/C validados contra manifestos reais são recusados corretamente até capacidades/permissões disponíveis. Clones são workflows estritos sem identidade legada, incluindo normalização explícita de clonelegacy (planner read_only, teste separado, só primários).

### WF-004 — revisão e regressão intermediária
- Suite anterior completa483 passed,1 warning,15,77s; build/lint verdes. Revisor achou clone legado com modelo agy vazio bloqueando override válido: corrigido para normalizar vazio→null somente em clone, original legacy intacto. Duas regressões adicionadas;31 presets verdes.
- Contrato em WORKFLOW_ENGINE §6.3.2 e seção Evolução planejada do README agora distinguem fundação interna implementada de UI/execução futura, removendo afirmação absoluta desatualizada. Validação completa final após correção em andamento.

### WF-004 — fim / revisão aprovada
- Implementado V2-WF-004: catálogo interno somente leitura em presets.py com quatro entradas, defaults UI A/CLIlegacy, clone/configuração por etapa e validação contra registry real. Templates A/B/C separam definição/bindings; modelos null preservam escolha do provider. Referências de configuração são lógicas; não há seed/API/editor ou execução implícita de agentes.
- Sistema B recusado até PROV-001, inclusive com fakes. A/C respeitam capacidades/permissões/verificação atuais e são recusados quando indisponíveis. Legacy usa contratos originais; clone é novo workflow estrito com planner read_only, testes separados e primários sem fallback, sem identidade de execução confiável baseada no nome.
- Arquivos: orchestrator/workflows/presets.py, tests/workflows/test_presets.py, seção Evolução planejada do README, WORKFLOW_ENGINE, IMPLEMENTATION_PLAN, BACKLOG e três handoffs (9 arquivos). Estatísticas finais verificadas no staged diff antes do commit.
- Testes finais: ORCH_DB temporário python -m pytest -q -p no:cacheprovider:485 passed,1 warning LangGraph,15,00s;31 novos presets. npm --prefix frontend test:38 passed no baseline; frontend intacto; build/lint verdes. check_docs e diff --check verdes. Sem E2E nesta sessão ou CLI de agente real/quota.
- Revisão review_wf004 aprovada após corrigir clone com modelo vazio impedindo override;181 focados passaram. Duas regressões garantem vazio→null só no clone e valor original no legacy. Nenhum outro achado bloqueante; CLI.main/default env e chamada execute_scope testados sem processos.
- Decisões: Q2/Q5 existentes aplicadas ao catálogo; ADR-0005 permanece proposto, sem decisões humanas adicionais ou flags/capacidades não verificadas. Nenhum merge/push/deploy. Commit local dev autorizado após testes/revisão.
- Pendências: UI/CRUD/persistência das escolhas, snapshots por run, executores reais/permissões, OpenRouter e fallbacks nas tarefas próprias. Novo padrão é metadado do catálogo e não foi ativado no produto atual.
- Próxima recomendada WF-007: snapshots imutáveis workflow+bindings/workflow_version_id/digest, CA4 de WORKFLOW_ENGINE; editar preset/config depois de enfileirar não altera run, idempotência e digest legados preservados. Ler NEXT_STEPS/WORKFLOW_ENGINE/DATA_MODEL/PERSISTENCE; mapear referências lógicas para configurações habilitadas e validar manifestos reais, sem bypass por preset/nome.
- Comandos para continuar: git status/log; source .venv/bin/activate; ORCH_DB temporário python -m pytest -q -p no:cacheprovider; npm --prefix frontend test; build/lint/check_docs/diff --check conforme escopo; revisão/handoff e commit dev após verdes. Uma tarefa por vez; nenhum agente real em testes.


## 2026-11-18 — Codex — push autorizado + V2-WF-007 início
- Operador solicitou push dev e depois WF-007. Remoto confirmado https://github.com/felipesembay/multi_agent-coding-orchestrator.git, dev remoto db12642. git push origin refs/heads/dev:refs/heads/dev enviou8 commits até7431745; sem force/merge/main/master. Árvore sincronizada/limpa; sem divergência com handoff exceto atualização esperada do remoto.
- Planejado WF-007: snapshot opcional definition/version/bindings/providers/digest, versões imutáveis validadas antes de gravar, confirmação/idempotência e runner consumindo snapshot; configuração default antiga preservada. HTTP/editor permanecem WF-008/009; nenhum preset real promovido.
- Plano/handoff/spec WORKFLOW_ENGINE/DATA_MODEL/PERSISTENCE/ADR-0005 consultados; dependências WF-002/003 done. Baseline ORCH_DB temporário python -m pytest -q -p no:cacheprovider:485 passed,1 warning LangGraph,14,79s; npm --prefix frontend test:38 passed. Nenhum agente real/quota.

### WF-007 — marcos de testes/implementação
- tests/workflows/test_snapshot.py vermelho por ModuleNotFoundError antes de snapshot.py/store.py.14 testes unitários verdes após implementação;21 novos com integração manager/runner/Git/worktree temporários e runtime.invoke fake. Fixture compartilhada em conftest.
- Configuração sem workflow conserva formato/digest; seleção interna (sem campos novos no HTTP StartInput) resolve versões imutáveis/providers habilitados, congela config.workflow e colunas novas e revalida na reserva. Runner valida integridade e usa snapshot com host AgentRuntime estrito, sem exceções do legado.
- Store append_version valida Pydantic/canonicalSHA e respeita definição read_only/archived. Recursos não integrados (gates/budgets/fallbacks/parâmetros/API provider/settings/credential refs) falham antes da fila. Legado continua separado sem mudança de flags/prompts. Revisão independente antes de done.

### WF-007 — revisão aprovada / regressão
- Revisor review_wf007 apontou prazo compartilhado: Git/testes/eventos consumiam tempo antes de invocar agente com timeout antigo. Host agora calcula restante do deadline absoluto (state.workflow_started) para Git/testes/invocações. Oito regressões com clock fake cobrem atraso em review/test e prazo esgotado sem iniciar comando. Manifestos dict também normalizados conforme registry.
- Revisão aprovada:214 focados workflows/bindings e35 manager passaram, sem outros bloqueios. Suite completa intermediária518 passed,1 warning,17,15s; build/lint verdes. Três casos adicionais pós-revisão de código passaram (testes falhos sobre QA positiva, falha de runtime sem payload sensível, verificação revogada antes de worktree), sem nova mudança no código revisado. Resultado final da suíte será registrado a seguir.
- Contratos e limitações atualizados em WORKFLOW_ENGINE §6.3.3 e DATA_MODEL; README só na seção Evolução planejada passa a incluir snapshots internos, sem prometer seleção de UI disponível.

### WF-007 — fim / revisão aprovada
- Implementado V2-WF-007: snapshots internos opcionais, writer de versões Pydantic/canônico, confirmação/reserva/idempotência e runner verificando integridade/capacidades antes da worktree, sem reler configuração mutável. Novo host AgentRuntime estrito envia modelos/permissões diretamente, mede chamadas e usa perfil de testes congelado/tempo restante. Caminho default/legacy sem workflow mantém forma/digest/colunas nulas e callbacks antigos.
- Arquivos: execution_manager.py/execution_runner.py; novos workflows/snapshot.py/store.py/execution.py; tests/workflows/conftest.py e três suítes novas test_snapshot/test_run_snapshot/test_snapshot_execution; README (somente Evolução planejada), DATA_MODEL, WORKFLOW_ENGINE, IMPLEMENTATION_PLAN, BACKLOG e três handoffs. Estatísticas finais verificadas no staged diff antes do commit.
- Testes finais: ORCH_DB temporário python -m pytest -q -p no:cacheprovider:521 passed,1 warning LangGraph,17,57s;36 novos. npm --prefix frontend test:38 passed no baseline; frontend intacto; build/lint verdes. check_docs e diff --check verdes. Sem E2E nesta sessão, sem CLIs reais/quota de agente.
- Revisão review_wf007 aprovada após correção de prazos,214 workflows/bindings+35 manager passaram. Três regressões adicionais passaram depois sem mudança no código revisado. Gates/budgets/fallbacks/params/ModelProvider/settings/credential_ref não integrados recusados antes da fila; sem campos novos no StartInput HTTP ou autoativação de presets/built-ins.
- Decisões: ADR-0005 permanece proposto, sem decisão humana nova ou credenciais copiadas. Deadline síncrono respeitado por chamadas suportadas, com timeout inteiro de runtime arredondado até1s; wrapper verifica prazo após retorno. Snapshots não são checkpoints/retomada gerenciada. Arquivar/alterar cfg depois de enfileirar não redireciona run; revogação de capacidades do runtime instalado falha fechado.
- Push autorizado anterior à implementação concluído db12642..7431745 em origin/dev. Commit novo WF-007 fica local conforme escopo solicitado (push dos arquivos existentes, depois implementação); sem force/merge/main/master/deploy.
- Pendências: HTTP/seleção UI WF-008; editor WF-009; capacidades/permissões/adapters de presetA e integração ModelProvider/creds/fallbacks/observabilidade/gates nas tarefas próprias. Nenhum bloqueio de WF-007 restante.
- Próxima WF-008: endpoints §6.6 e StartExecution selecionando workflow_version_id/bindings, reutilizando snapshots, readonly de presets, configs habilitadas e confirmação/digests. Aceite com API/vitest e compatibilidade antiga; não habilitar plugins por HTTP ou escolher legacy por nome. Ler NEXT_STEPS/WORKFLOW_ENGINE/DATA_MODEL/SECURITY e módulos snapshot/store/manager/runner/api. Comandos baseline isolado+vitest e build/lint/docs, revisão/handoff e commit dev após verdes. Uma tarefa por vez, sem novo push/merge/deploy e sem agentes reais em testes.
