# Estado atual

Atualizado: 2026-11-18 · Por: Codex (V2-WF-004)

## Repositório
- Branch `dev`; commits testados/revisados autorizados pelo operador. Sem merge/deploy/main/master. Novo push não autorizado.
- Baseline `f8e6949`; CORE-001..004 em `87a034f`, `56e44d2`, `6737c2f`, `db12642`. Push anterior somente até db12642 em origin/dev.
- SEC-001 `8d94e7d`, SEC-002 `065d9ed`, SEC-006 `7ac3634`, WF-001 `caee20e`, WF-002 `fc93cd1` locais. WF-003 `1474f4b`. Registro parcial F0-002 em `588c6db`. WF-004 registrada no commit `V2-WF-004: add system preset catalog and stage choices`; consultar git log para hash final.
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
- **WF-003:** compiler.py/nodes.py compilam definições estritas com executores confiáveis obrigatórios por tipo, snapshots em memória de configuração, envelopes/eventos e contadores por etapa/tarefa, prazo, revisão lógica das evidências e aprovação/gates explícitos. Sem executores CLI implícitos, API ou ledger. Budget não nulo e fallback configurável recusados até integrações OBS/WF-010.
- core.graph usa compile_legacy com layout privado e callbacks/entradas/topologia/recursion250 preservados. Snapshot topológico capturado de fc93cd1 antes da mudança; não existe bypass por nome legacy-v1 em workflows de usuário. Execução genérica deriva recursion de max_total_steps e verifica contagem por etapa.
- Deadline checado antes/depois e nos controles; executor deve aplicar context.timeout_s aos subprocessos. Gates têm payload booleano obrigatório mas persistência/proveniência em RES-004; nenhum autoapprove de produção. Testes/review precisam cobrir a última escrita para finalizar.
- **WF-004:** presets.py fornece catálogo interno legacy-v1/A/B/C e clonagem/configuração por etapa. Padrão UI recomendado A e CLIlegacy identificados; cada consulta cria cópias independentes, modelos null mantêm defaults do provider e escolhas substituem bindings inteiros.
- validate_preset respeita manifestos reais, sem promover capacidades. A/C não executáveis com manifestos atuais incompletos; B bloqueado por PROV-001 mesmo com fakes. Legacy continua com resolução/validação original; clone vira workflow estrito com planner read_only/testes separados/só primários, sem bypass por nome. Modelo vazio normalizado só no clone, original intacto.
- Sem seed de banco, endpoints, editor ou mudança do fluxo atual. CLI flags intactas: Claude ainda acceptEdits, Codex read-only. SEC-003/004 permanecem sem implementação; Q2–Q12 recebidas nesta sessão, conforme seção de decisões abaixo.

## Evidências WF-004
| Verificação | Resultado |
|---|---|
| Baseline pytest isolado / vitest | 454 passed,1 warning /38 passed |
| Pytest final isolado | 485 passed,1 warning LangGraph,15,00 s |
| Novos testes de presets | 31 passed; inclui execução LangGraph fake e CLI.main→execute_scope sem subprocessos |
| Revisão independente review_wf004 | aprovada após correção de modelo vazio em clone legado;181 focados passaram |
| Frontend | 38 vitest no baseline; build/lint verdes; frontend inalterado |
| Docs / diff --check | sucesso |
| E2E | não reexecutado em WF-004; última SEC-002:9 passed /2 skipped com mocks |
| Agentes CLI reais | nenhum; sem quota real |

## Decisões do operador — 2026-11-18
- Q2 esclarecida: novo padrão desejado Claude → Codex → Antigravity, usuário pode escolher providers/modelos por etapa. Q5 aceita workspace-write como necessário para preset A, com alternativa sem execução a verificar. Não ativados nesta sessão; default executado ainda Claude/Claude/Codex.
- Q3 alvo Python3.12 autorizado, ainda não migrado. Q4 perguntar ao fechar com run ativo, opção background. Q6 Ubuntu/.deb primeiro, AppImage depois; assinatura não escolhida.
- Q7 explicitamente adiada: intenção pública/open source sem licença específica; nenhum LICENSE criado. Q8 alertar por padrão, bloqueio opt-in, valor indefinido. Q9 contador separado/equivalente estimado não cobrado.
- Q10 autoriza poucos prompts triviais em diretório temporário para spikes de telemetria/Planner read-only. Nenhum consumo real nesta sessão; testes automáticos com mocks continuam obrigatórios.
- Q11 commits automáticos em worktree/branch agent/<run> por tarefa aprovada, não por tentativa/chamada nem na origem; sem merge/push/deploy. Q12 Conductor provisório/reversível.
- Registro não é implementação nem aceitação integral dos ADRs; revisão específica dos dez ADRs continua pendente. F0-002 fica parcial/blocked residual por esse critério, não por perguntas já respondidas.

## Próximos passos
- WF-007: snapshot/digest workflow+bindings por run, com versões imutáveis e preservação de idempotência/configs anteriores. Referências lógicas pc-* do catálogo não são configurações persistidas/habilitadas; resolver no host e validar.
- Execução real do padrão A depende de SEC-003/004, WF-005/006 e seleção/editor em WF-008/009. B continua bloqueado por PROV-001. Decisões Q2/Q5 já recebidas; não promover manifestos não verificados.
- Python3.12/compatibilidade em F0-005 e spikes autorizados em F0-003/SEC-003 podem avançar no escopo decidido; uma tarefa por vez, com revisão pertinente. Não confundir o bloqueio residual de F0-002 com as questões já resolvidas.
- Licença específica, assinatura, valor de orçamento, identidade final e revisão integral dos ADRs continuam pendentes nos seus respectivos escopos.

## Ambiente
Python 3.9.7 (.venv), LangGraph 0.6.11, Node 22.18.0, Git 2.43.0. Sem dependências novas ou alterações em credenciais.
