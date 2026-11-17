# ADR-0005 — Workflow como dado versionado compilado para LangGraph

- **Status:** proposto · **Data:** 2026-11-17 · **Tarefas:** V2-WF-*

## Contexto
O grafo atual está codificado em `core.graph()`. O usuário quer escolher modelos por etapa, reordenar/adicionar etapas, presets, fallbacks e limites, com editor visual futuro.

## Decisão
- Definição JSON validada por Pydantic (`schema_version` explícito), armazenada em `workflow_versions` **imutáveis**.
- Separação entre **definição** (etapas, papéis, gates, limites) e **bindings** (qual runtime/modelo atende cada etapa), para que presets A/B/C compartilhem a mesma definição.
- Compilador gera `StateGraph`; primeira versão deve produzir grafo **comportamentalmente equivalente** ao atual (teste de equivalência).
- MVP: sequência linear com loop de correção review→implement limitado; ramificações e loops arbitrários em fase futura, sempre com limite global de passos.
- Editor MVP em lista/formulário; React Flow (`@xyflow/react`) como editor visual posterior e como visualização somente leitura do run já na F5.

## Alternativas rejeitadas
| Alternativa | Motivo |
|---|---|
| YAML no repositório alvo | Útil como export/import futuro; persistência principal precisa de versão imutável e digest por run |
| Gerar código Python do grafo | Inseguro e difícil de validar |
| Grafo arbitrário desde o MVP | Validação de terminação complexa; presets A/B/C não precisam |

## Consequências
`ExecutionConfiguration` (env-based) vira binding derivado do preset legado para compatibilidade do CLI.
