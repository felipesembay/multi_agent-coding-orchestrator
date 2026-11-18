# TASK 03 — Workflows personalizáveis

## 1. Identificador e título
`V2-T03` — Workflow engine configurável. Subtarefas `V2-WF-001..012`.

## 2. Objetivo
Desacoplar papéis de modelos; manter Planejamento → Execução → Revisão como padrão; permitir presets, reordenação, etapas adicionais, limites, critérios de aprovação e fallbacks, executados pelo LangGraph a partir de definição persistida e validada ([ADR-0005](../architecture/DECISIONS/ADR-0005-workflow-como-dado.md)).

## 3. Estado atual comprovado
Grafo fixo em `core.graph()`; papéis planner/implementer via env; reviewer fixo; `MAX_ATTEMPTS` global; `recursion_limit=250`; config congelada por run em `managed_runs.config`.

## 4. Requisitos funcionais
- RF1 Definição com etapas tipadas: `plan`, `implement`, `test`, `review`, `document`, `human_gate`.
- RF2 Bindings: para cada etapa, `provider_config_id` + `model` + parâmetros + lista ordenada de fallbacks com condições (`on: [rate_limited, quota_exhausted, unavailable]`).
- RF3 Presets de sistema (somente leitura, clonáveis):

| Preset | Plan | Implement | Review | Observação |
|---|---|---|---|---|
| `default-v2` (A) | Claude Code | Codex CLI (`workspace_write`) | Antigravity | Padrão desejado; depende de Q2/Q5 |
| `openrouter-plan` (B) | OpenRouter (modelo escolhido) | Codex CLI | Claude Code (`read_only`) | Requer V2-PROV-001 |
| `claude-heavy` (C) | Claude Code | Claude Code | Codex CLI (`read_only`) | |
| `legacy-v1` | env `ORCH_PLANNER` | env `ORCH_IMPLEMENTER` | Codex | Comportamento atual exato; usado pelo CLI |

- RF4 Editor (MVP em lista): selecionar provider/modelo por etapa, reordenar dentro das regras, adicionar/remover etapas opcionais (`document`, `human_gate`, `test` extra), salvar como preset do usuário.
- RF5 Limites: `max_attempts` por etapa de implementação, `max_total_steps`, `max_duration_s`, `budget_usd` (link com [TOKEN_ACCOUNTING.md](TOKEN_ACCOUNTING.md)).
- RF6 Critérios de aprovação: testes passam (obrigatório se existir etapa `test`), reviewer `approved=true`, opcional `human_gate`.
- RF7 Estado por etapa visível em tempo real (eventos `stage_started`/`stage_finished` com `step_id`).

## 5. Requisitos não funcionais
- RNF1 Compilação determinística: mesma versão + bindings → mesmo grafo (teste por snapshot da topologia).
- RNF2 Terminação garantida: toda aresta de retorno tem contador e limite; `recursion_limit` derivado de `max_total_steps`.
- RNF3 Compatibilidade: `legacy-v1` reproduz o comportamento atual nos testes existentes.

## 6. Arquitetura proposta

### 6.1 Schema (v1 do schema)
```json
{
  "schema_version": 1,
  "name": "default-v2",
  "steps": [
    {"id": "plan", "type": "plan", "role": "planner", "requires": ["planning", "structured_output"]},
    {"id": "impl", "type": "implement", "role": "implementer", "requires": ["code_edit"], "per_task": true,
     "max_attempts": 3},
    {"id": "tests", "type": "test", "per_task": true, "command_profile": "server_default"},
    {"id": "review", "type": "review", "role": "reviewer", "requires": ["review", "structured_output"],
     "per_task": true, "on_reject": "impl"}
  ],
  "limits": {"max_total_steps": 200, "max_duration_s": 14400, "budget_usd": null},
  "approval": {"require_tests": true, "require_reviewer": true, "human_gate_after_plan": false}
}
```
Bindings ficam fora (`managed_runs.bindings`):
```json
{"plan": {"provider_config_id": "pc-claude", "model": null,
          "fallbacks": [{"provider_config_id": "pc-agy", "model": "…", "on": ["quota_exhausted", "rate_limited"]}]},
 "impl": {"provider_config_id": "pc-codex", "model": null, "permission": "workspace_write"},
 "review": {"provider_config_id": "pc-agy", "model": "…", "permission": "read_only"}}
```

### 6.2 Validação (`workflows/validation.py`)
1. Schema Pydantic estrito (`extra='forbid'`).
2. Ordem: `plan` primeiro; etapas `per_task` formam um bloco contíguo; `on_reject` só aponta para etapa anterior do mesmo bloco.
3. Capacidades: `requires` ⊆ manifesto do binding; `code_edit` exige `agent_runtime` verificado.
4. Permissão: papel `reviewer`/`planner` só `read_only`; `implementer` só `workspace_write` (matriz de segurança).
5. Limites dentro de faixas do servidor (como hoje `1 ≤ max_attempts ≤ 20`).
6. Fallback não pode ter capacidades menores que o primário.
7. Ciclos: apenas arestas `on_reject` com contador; qualquer outro ciclo é erro.

### 6.2.1 Contrato entregue em V2-WF-001

`orchestrator/workflows/schema.py` e `validation.py` implementam somente os dados e a validação pura. Não executam grafo, probe ou agente e não mudam bindings/preset legados. API/422 será integrada em WF-008; por enquanto os erros são `pydantic.ValidationError`, com localização por campo.

- `WorkflowDefinition.model_validate(payload)` valida estrutura; `validate_workflow(definition, bindings, provider_configs=..., registry=...)` acrescenta a validação dos bindings. `provider_configs` é um mapa confiável de ID de configuração para adapter já habilitado no registry, até a persistência em WF-002. Nenhum ID do workflow habilita plugins.
- Todos os objetos têm `extra=forbid`; números inteiros e booleanos não são coercidos. O schema JSON discrimina etapas por `type`. Bindings ficam separados, com modelo opcional, `parameters` JSON e fallbacks ordenados sem fallback aninhado. Permissão default `read_only`, inclusive em fallback; implementers precisam declarar `workspace_write` explicitamente.
- Papéis são coerentes com o tipo: `planner`, `implementer`, `reviewer`, `documenter` (para `document`). `test` e `human_gate` não recebem binding. Capacidades mínimas `text` + `planning`/`code_edit`/`review` conforme tipo são exigidas mesmo se omitidas em `requires`; `document` exige ao menos `text`. Escrita de documentos também exige runtime verificado com `code_edit`; planners/reviewers continuam somente leitura.
- Faixas do servidor no contrato v1: 1–100 etapas declaradas, 1–10000 passos totais, duração 1–86400 s, 1–20 tentativas por implementação e orçamento finito não negativo ou null. Defaults: 200 passos, 14400 s, 3 tentativas, orçamento null. Até 10 fallbacks por binding; condições não vazias/únicas entre `rate_limited`, `quota_exhausted`, `unavailable`.
- `plan` ocorre exatamente uma vez, primeiro e fora de `per_task`. No MVP apenas `review.on_reject` representa retorno, para um `implement` anterior com `max_attempts`, no mesmo bloco contíguo `per_task`. Arestas arbitrárias são campos desconhecidos e recusadas.
- Se houver `test`, `approval.require_tests` deve ser true; se true, deve haver `test`. `require_reviewer=true` exige etapa `review`. `human_gate_after_plan` permanece uma política declarativa para o compilador futuro; não cria execução nesta tarefa.
- Não há exceção de segurança baseada no nome `legacy-v1`. A compatibilidade legada permanece no caminho existente, até compilador/presets com equivalência comprovada em WF-003/004. Manifestos atuais não verificadas não são promovidas automaticamente.

### 6.3 Compilador (`workflows/compiler.py`)
Gera nós genéricos (`make_plan_node(step, binding)`, …) que usam o envelope de invocação (ledger + uso + eventos). Para `legacy-v1` a topologia resultante é a mesma de `core.graph()` (teste de equivalência por snapshot e pelos testes de integração existentes).

### 6.3.1 Contrato entregue em V2-WF-003

`compile_workflow(definition, bindings, provider_configs=..., registry=..., executors=..., event_sink=...)` retorna um grafo LangGraph executável com configuração de recursão derivada do limite de passos. Valida novamente a definição/bindings, congela cópias e não seleciona presets nem carrega/invoca agentes. Os executores síncronos, confiáveis e obrigatórios são fornecidos pelo host por tipo de etapa; não existem executores CLI implícitos nesta tarefa.

- Cada executor recebe `StepContext`: cópias da etapa, binding (ou null para test/gate), adapter resolvido, snapshot de estado e `timeout_s` com tempo restante. Retorna um payload dict: plan `{tasks:[{id:...},...]}` quando há bloco por tarefa; test `{passed:bool}`; review `{approved:bool,findings:[...]}`; human_gate `{approved:bool}`; implement/document retornam seu payload. Counters/roteamento são mantidos pelo compilador, não pelo payload.
- `nodes.py` gera envelopes e eventos stage_started/stage_finished com step_id, sem incluir resultados brutos nos eventos. O host pode conectar event_sink ao armazenamento; esta tarefa não cria ledger/usage_records, que permanecem em RES-001/OBS-001.
- Bloco per_task executa sobre as 1–30 tarefas do plano. Cada implementação tem contador por etapa/tarefa; a rejeição de review retorna ao implement anterior, ou bloqueia ao esgotar max_attempts. Testes falhos impedem aprovação mesmo que o reviewer retorne true. Sufixos executam após todas as tarefas.
- Escritas declaradas por workspace_write avançam uma revisão lógica das evidências. Aprovações/testes de uma tarefa precisam corresponder à escrita corrente ao sair do bloco; o fechamento exige evidência de testes/review após a última escrita. Documento com escrita posterior à revisão exige novas etapas de teste/review. Isso não substitui digest/ledger de efeitos colaterais futuros.
- Limite de passos é verificado em cada etapa, independente de override de recursion_limit pelo caller. Prazo é checado antes/depois da chamada e nos controles; o executor deve respeitar context.timeout_s para interromper subprocessos em andamento. O compilador síncrono não interrompe um callback arbitrário por conta própria.
- human_gate_after_plan reutiliza gate global explícito logo após plan ou adiciona um de ID único. Sem executor de gate, compilação falha; só approved=true permite seguir. Aprovação humana persistida/proveniência será conectada em RES-004; nunca há autoaprovação de produção.
- Budget não nulo e fallbacks configuráveis são recusados explicitamente até as integrações OBS/WF-010; não são silenciosamente ignorados. Parâmetros/modelos são encaminhados ao executor via binding, sem supor flags de CLI não verificadas.
- `core.graph` delega a `compile_legacy`, um layout privado de compatibilidade, com os mesmos callbacks/topologia e entradas plan/implement/review. Review legado continua executando testes internamente e o caller mantém recursion_limit=250. Não usa nome de workflow para contornar validação: o caminho legado é separado e somente chamado pelo host existente. Snapshot da topologia foi capturado antes da refatoração; testes legados continuam inalterados.
- API/editor/presets, snapshot de workflow no run, executores concretos por integração e fallbacks ficam nas tarefas próprias; nenhum novo padrão foi ativado.

### 6.4 Fallbacks
Envelope captura erro normalizado; se casar com `on`, registra evento `agent_fallback` (formato atual estendido com `step_id`) e tenta o próximo binding; cada tentativa gera `usage_record` próprio. Generaliza o fallback hoje embutido em `coding_agent`.

### 6.5 Editor visual
- MVP (F2): formulário em lista com drag-and-drop de reordenação restrita, seletores filtrados por capacidade, painel de validação ao vivo (`POST /workflows/validate`).
- F5: React Flow (`@xyflow/react`) para **visualizar** o run (nós = etapas, cor = estado).
- F6+: React Flow como editor, gerando o mesmo JSON; ramificações condicionais e loops adicionais com limites (`V2-WF-012`).

### 6.6 API
`GET/POST /workflows`, `GET /workflows/{id}/versions`, `POST /workflows/{id}/versions`, `POST /workflows/validate`, `GET /workflow-presets`; preflight passa a receber `workflow_version_id` + bindings e retorna digest sobre ambos.

## 7. Componentes afetados
`core.py`, `execution_manager.py` (config/digest), `execution_runner.py`, `project_store.py` (migração 4), `api.py`, frontend `StartExecution.tsx`, nova feature Workflows.

## 8. Arquivos previstos
`orchestrator/workflows/{schema,validation,compiler,presets,store,nodes}.py`, `tests/workflows/test_{schema,validation,compiler_equivalence,fallback}.py`, `frontend/src/features/Workflows.tsx`, `frontend/src/features/WorkflowEditor.tsx`.

## 9. Dependências
`V2-CORE-001..004` (adapters uniformes), `V2-SEC-004` (matriz de permissões), `V2-PROV-001` para preset B.

## 10. Riscos
| Risco | Mitigação |
|---|---|
| Regressão do comportamento atual | `legacy-v1` + equivalência + suíte atual |
| Combinações permitidas mas ruins (ex.: modelo fraco como reviewer) | Aviso, não bloqueio |
| Codex executor com exec livre | Q5; ledger; política de rede |
| Mudança do padrão surpreende usuários | Q2; nota de migração; preset legado sempre disponível |

## 11. Critérios de aceite verificáveis
- CA1 Preset `legacy-v1` passa nos 72 testes atuais sem alteração de asserts.
- CA2 Presets A, B e C validam com fakes; trocar binding muda apenas `argv`/provider chamado (teste).
- CA3 Workflow com ciclo não limitado, `code_edit` em `model_provider`, ou `max_attempts=0` é rejeitado com 422 e mensagem por campo.
- CA4 Run registra `workflow_version_id`, bindings e digest; alterar preset após enfileirar não altera o run.
- CA5 Fallback por `quota_exhausted` grava `agent_fallback` com `step_id` e dois `usage_records`.

## 12. Testes necessários
Schema (válido/inválido), validação de capacidades, equivalência do compilador, integração com subprocesso e agentes mockados por preset, testes de UI do editor (vitest) e e2e mockado de início com preset.

## 13. Complexidade
WF-001: S · WF-002: S · WF-003: L · WF-004: S · WF-005: M · WF-006: M · WF-007: M · WF-008: M · WF-009: M · WF-010: M · WF-011: L · WF-012: XL.

## 14. Prioridade
P0: WF-001..004, 007. P1: WF-005, 006, 008, 009, 010. P3: WF-011, 012.

## 15. Perfil recomendado
Backend Python com LangGraph (compilador); frontend React (editor). Revisor independente obrigatório para WF-003.
