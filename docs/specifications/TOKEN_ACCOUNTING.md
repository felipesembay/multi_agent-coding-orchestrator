# TASK 04 — Monitoramento de tokens e custos

## 1. Identificador e título
`V2-T04` — Observabilidade financeira. Subtarefas `V2-OBS-001..008`.

## 2. Objetivo
Registrar uso e custo por projeto, execução, etapa/agente, provedor e modelo, com distinção explícita entre dado reportado, estimado e indisponível ([ADR-0006](../architecture/DECISIONS/ADR-0006-contabilidade-de-uso.md)).

## 3. Estado atual comprovado
Nenhuma métrica de tokens/custo. Duração por run apenas (`started_at`/`finished_at`). Saídas de CLI descartadas exceto texto (Claude, Codex) ou `response/status/denied_actions` (agy).

### Estado incremental após V2-WF-010

O host de workflows estritos persiste um evento `usage_record` por invocação no SQLite events, associado a agent_call por call_id e a fallback por retry_of. Campos numéricos permanecem null com token_source=unavailable na ausência de telemetria; raw é omitido e billing_mode vem do manifesto. Isso não implementa a tabela usage_records/migração5 nem a captura universal no caminho legado. OBS-001 deve integrar por call_id sem duplicar os registros históricos. Parsers, preços, estimativas, orçamento, APIs e UI financeira permanecem pendentes.

## 4. Requisitos funcionais
- RF1 Por chamada: input, output, cache read/write, reasoning (se reportados), custo reportado, custo estimado, duração, erro, tentativa (`retry_of`).
- RF2 Agregações: por projeto, modelo, agente/papel, período (dia/semana/mês), run; comparação entre modelos (custo/tarefa aprovada, tokens/tarefa, taxa de aprovação na 1ª tentativa).
- RF3 Catálogo de preços versionado (moeda, unidade, origem, data, vigência).
- RF4 Orçamentos por run, projeto e global; ações `warn` ou `block`; override exige aprovação registrada.
- RF5 Dashboard e alertas na UI.

## 5. Requisitos não funcionais
- RNF1 Rótulos obrigatórios: toda cifra exibida carrega fonte (`reportado`, `estimado`, `indisponível`) e modo de cobrança.
- RNF2 Assinatura/quota (CLIs) nunca somada a gasto API sem separação visual.
- RNF3 Agregações em < 300 ms com 10⁵ registros (índices por `project_id, started_at`, `model`).
- RNF4 `raw_usage` redigido e limitado (≤ 8 kB).

## 6. Arquitetura proposta

### 6.1 Classificação
| Situação | `token_source` | `billing_mode` | Exibição |
|---|---|---|---|
| API devolve `usage` | `provider_reported` | `api_metered` | Tokens reais; custo = reportado se houver, senão estimado (rotulado) |
| CLI imprime uso em JSON | `cli_reported` | `subscription_quota` ou `api_metered` conforme autenticação (Q9) | "Equivalente estimado" quando assinatura |
| Sem telemetria | `unavailable` | conforme adapter | "Indisponível" — nunca zero |
| Estimativa local (tokenizer/heurística chars/4) | `estimated` | — | Somente se usuário habilitar; ícone de estimativa |
| Ollama | `provider_reported` | `local` | Custo marginal 0, exibido como "local" |

### 6.2 Telemetria por CLI — a investigar (spike `V2-F0-003`)
| CLI | Flag candidata | Campos esperados (hipótese) | Como verificar |
|---|---|---|---|
| Claude Code 2.1.92 | `-p --output-format json` | `usage.{input_tokens,output_tokens,cache_*}`, `total_cost_usd`, `session_id`, `num_turns` | Rodar 1 prompt trivial em diretório temporário com autorização do operador; salvar fixture redigida |
| Codex 0.166.0 | `exec --json` | Eventos JSONL com contagem de tokens por turno | Idem; registrar formato por versão |
| Antigravity 1.5.1 | `--output-format json` / `stream-json` | Desconhecido além de `status`, `response`, `denied_actions` | Idem |
O spike consome quota e exige autorização explícita. Resultado documentado em `docs/specifications/telemetry/<cli>-<versão>.md` com fixture em `tests/fixtures/telemetry/`.

### 6.3 Catálogo de preços
`price_catalog_versions` + `price_entries` ([DATA_MODEL](../architecture/DATA_MODEL.md)). Fontes: `manual` (UI/CSV), `openrouter_api` (sincronização), futuramente páginas oficiais (manual). Cálculo usa a entrada vigente em `started_at` da chamada e grava `price_entry_id` para auditoria. Mudança de preço não altera custos passados.

### 6.4 Orçamento
- Antes de cada chamada: `projected = gasto_atual + estimativa_conservadora(max_tokens)`; se `> limite` e ação `block` → etapa vai para `awaiting_approval` (não falha silenciosa).
- Após chamada: atualiza gasto; `warn_ratio` (ex.: 0,8) emite `budget_events`.
- Orçamento só considera custos `api_metered`; quotas de assinatura geram contador separado de chamadas/tokens (Q9).
- Claude `--max-budget-usd` (existe no `--help`) pode ser passado como limite adicional por chamada — complementar, não substituto.

### 6.5 API e UI
`GET /usage/summary?group_by=project|model|role|day&from&to`, `GET /runs/{id}/usage`, `GET/POST /pricing`, `GET/PUT /budgets`. Telas em [UI_UX.md](../design/UI_UX.md) §Custos: cards (gasto API período, equivalente assinatura, chamadas sem telemetria), série temporal, tabela por modelo, comparação, custo por run, alertas.

## 7. Componentes afetados
Envelope de invocação (providers), `project_store.py`, `api.py`, `dashboard.py`, frontend Overview/Details.

## 8. Arquivos previstos
`orchestrator/accounting/{usage,pricing,budget,estimator,redact}.py`, `orchestrator/providers/runtimes/*_telemetry.py`, `tests/accounting/*`, `tests/fixtures/telemetry/*`, `frontend/src/features/Usage.tsx`.

## 9. Dependências
`V2-CORE-002` (resultado estruturado), `V2-F0-003` (spike), migração 5.

## 10. Riscos
| Risco | Mitigação |
|---|---|
| CLI não reporta uso | `unavailable` explícito |
| Custo reportado por CLI em assinatura confundido com cobrança | `billing_mode` + rótulo |
| Mudança de formato entre versões de CLI | Parser versionado, fallback para `unavailable` com aviso |
| Preço desatualizado | Data de atualização visível; alerta se > 30 dias |

## 11. Critérios de aceite verificáveis
- CA1 Fixture de cada CLI produz `UsageReport` esperado; fixture sem campos → `unavailable`.
- CA2 Nenhuma tela soma `subscription_quota` com `api_metered` em um único número (teste de componente).
- CA3 Orçamento `block` impede chamada seguinte e cria `approval` pendente (teste de integração com fake).
- CA4 Alterar preço não altera `estimated_cost_usd` de registros anteriores.

## 12. Testes necessários
Parsers por fixture, cálculo de custo com catálogo versionado, orçamento (warn/block/override), agregações SQL, componentes de dashboard com dados mistos.

## 13. Complexidade
OBS-001: M · OBS-002: M (por CLI S) · OBS-003: M · OBS-004: S · OBS-005: M · OBS-006: M · OBS-007: L · OBS-008: S.

## 14. Prioridade
P1 (OBS-001, 002, 003) · P2 (OBS-004..008).

## 15. Perfil recomendado
Backend Python com SQL; frontend com dataviz. Revisão de rótulos por humano.

## Implementação incremental OBS-003 — 2026-11-19

- GET/POST `/pricing` expõem versões do catálogo nas tabelas já criadas em OBS-001, e GET `/pricing/quote` seleciona cotação por adapter/modelo/moeda/instante. Rotas recebem a autenticação local global. POST aceita source=manual ou import (lote JSON, até1000entradas), notes e entries; source=openrouter_api fica reservado à futura sincronização PROV-002. Sem arquivos/caminhos/shell ou fetch externo.
- Cada entrada declara unidade per_1m_tokens, moeda de3letras, preços por componente finitos/não negativos ou null, effective_from com timezone e effective_to opcional posterior. Normalização internaUTC com precisão de microssegundos; fim exclusivo. Versões são acrescidas, sem endpoints UPDATE/DELETE. Conflito de adapter/modelo/moeda/início é recusado atomicamente, inclusive no meio de um lote, sem alterar versões anteriores. A imutabilidade é do contrato do writer/API; editar o SQLite manualmente não é operação suportada.
- A entrada de início mais recente prevalece na consulta. Após seu fim explícito, um preço antigo aberto não reaparece automaticamente. Origem, captura, moeda, unidade, vigência e identificador permanecem auditáveis; pricing.catalog_created grava apenas ID/source/count, não notas ou valores arbitrários.
- AgentCall captura started_atUTC antes de executar o provider; record_usage escolhe a entrada vigente nesse início, calcula com Decimal/preço por milhão e congela estimated_cost_usd+price_entry_id no primeiro INSERT por call_id. Mudanças de catálogo não reprecificam nem preenchem retroativamente chamadas já registradas. Custo reportado não é sobrescrito; billing_mode assinatura/API permanece separado.
- Estimativa automática apenas para tokens reportados e modos api_metered/subscription_quota em USD. Sem FX, heurística de tokens ou preços default. Falta de preço/contagem, componente sem preço, valores fora da precisão representável ou subcontagens cache/reasoning ainda ambíguas mantêm estimativa null; zero somente se os dados permitirem custo zero explícito. Preços cache/reasoning ficam disponíveis no catálogo para parsers futuros normalizarem sem dupla contagem. Token_source continua reportado quando os tokens são reportados, mesmo que o campo de custo separado seja estimado.
- Não entrega OBS-004/005/006/007/008: tokenizer opt-in, orçamento, agregações, dashboard e aba de uso permanecem pendentes. Não cadastra nenhum preço real nem consulta APIs de preços. Dados de teste são sintéticos.
