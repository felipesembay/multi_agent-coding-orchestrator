# Estado atual

Atualizado: 2026-11-18 · Por: Codex (V2-WF-009)

## Repositório
- Branch `dev`; commits testados/revisados autorizados pelo operador. Sem merge/deploy/main/master. Push solicitado pelo operador em 2026-11-18 concluído até 7431745 em origin/dev; sem force/main/master. Commits WF-007 e CI-DIST-004 continuam locais; WF-008 (58051a2) e WF-009 também ficam locais; nenhum novo push solicitado. Sem novo push solicitado.
- Baseline `f8e6949`; CORE-001..004 em `87a034f`, `56e44d2`, `6737c2f`, `db12642`. Histórico remoto dev atualizado até 7431745 nesta sessão.
- SEC-001 `8d94e7d`, SEC-002 `065d9ed`, SEC-006 `7ac3634`, WF-001 `caee20e`, WF-002 `fc93cd1` locais. WF-003 `1474f4b`. Registro parcial F0-002 em `588c6db`. WF-004 em `7431745` (já em origin/dev). WF-007 em `6f1c167`, CI-DIST-004 em `feb4caf`. WF-008 no commit `V2-WF-008: expose workflow APIs and execution selection`; consultar git log para hash final.
- WIP original de tema/exclusão/migração v3 preservado no baseline. Nenhum WIP externo identificado.

## Implementado
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
- WF-009: editor em lista de definições/etapas com validação ao vivo, clone de presets e salvar nova versão imutável, reutilizando a API/seleção atuais.
- Execução real do padrão A depende de SEC-003/004, WF-005/006 e editor completo em WF-009 (seleção já entregue). B continua bloqueado por PROV-001. Decisões Q2/Q5 já recebidas; não promover manifestos não verificados.
- Python3.12/compatibilidade em F0-005 e spikes autorizados em F0-003/SEC-003 podem avançar no escopo decidido; uma tarefa por vez, com revisão pertinente. Não confundir o bloqueio residual de F0-002 com as questões já resolvidas.
- Licença específica, assinatura, valor de orçamento, identidade final e revisão integral dos ADRs continuam pendentes nos seus respectivos escopos.

## Ambiente
Python 3.9.7 (.venv), LangGraph 0.6.11, Node 22.18.0, Git 2.43.0. Sem dependências novas ou alterações em credenciais.

## CI e versão de Python
O email remoto não descrevia testes vermelhos: o setup não encontrou3.9 para26.04. Imagem compatível22.04 fixada em commit separado; migração3.12 continua em F0-005, já autorizada. CI remoto só poderá ser declarado verde após push/execução dos commits novos.

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
