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
