# Design System — "Conductor" (nome de trabalho)

Estado: **proposta**. Base existente: tokens tonais em `frontend/src/styles/theme.css` (neutral, blue, green, red, amber; escala 100–950; variante clara por `data-theme`). Este documento **não substitui** esses tokens: adiciona uma camada semântica sobre eles.

## 1. Princípios
1. **Densidade calma** — muita informação técnica, pouca decoração; cor reservada para estado.
2. **Estado antes de estética** — todo elemento que representa execução mostra estado com cor + ícone + texto (nunca só cor).
3. **Verdade dos dados** — estimado, indisponível e reportado têm tratamentos visuais distintos.
4. **Teclado primeiro** — paleta de comandos, atalhos, foco visível.
5. **Escuro por padrão**, claro com paridade.

Identidade própria: sem logotipos, ícones, nomes ou layouts de terceiros (incluindo ORCA). Ícones de Lucide (já em uso).

## 2. Cores

### 2.1 Camada semântica (novos tokens, mapeados para os tonais existentes)
| Token semântico | Escuro (tonal) | Claro (tonal) | Uso |
|---|---|---|---|
| `--bg-app` | `neutral-950` | `neutral-950` | Fundo da janela |
| `--bg-surface` | `neutral-900` | `neutral-900` | Painéis, cards |
| `--bg-raised` | `neutral-850` | `neutral-850` | Hover, popovers |
| `--bg-inset` | `neutral-950` | `neutral-800` | Terminal, código |
| `--border-subtle` | `neutral-800` | `neutral-700` | Divisórias |
| `--border-strong` | `neutral-700` | `neutral-600` | Inputs, foco secundário |
| `--text-primary` | `neutral-100` | `neutral-100` | Texto |
| `--text-secondary` | `neutral-300` | `neutral-300` | Metadados |
| `--text-muted` | `neutral-500` | `neutral-500` | Placeholders (não usar para conteúdo essencial) |
| `--accent` | `blue-500` | `blue-500` | Ação primária, seleção, links |
| `--focus-ring` | `blue-200` | `blue-400` | Foco |
| `--status-running` | `blue-400` | `blue-500` | Em execução |
| `--status-success` | `green-400` | `green-500`* | Aprovado, testes ok |
| `--status-warning` | `amber-400` | `amber-500`* | Orçamento, aguardando aprovação |
| `--status-danger` | `red-400` | `red-500`* | Falha, bloqueado |
| `--status-neutral` | `neutral-400` | `neutral-400` | Fila, desconhecido |
| `--data-estimated` | `amber-300` + padrão tracejado | idem | Valores estimados |
| `--data-unavailable` | `neutral-500` | idem | Telemetria ausente |
\* verificar contraste AA no tema claro durante `V2-DESK-005`.

### 2.2 Cores por agente/papel (gráficos e grafo)
Paleta categórica independente de marca: papel `planner` = blue, `implementer` = green, `reviewer` = amber, `tests` = neutral, `document` = red-300 (suave). Provider é mostrado por **rótulo e ícone genérico**, não por cor de marca.

## 3. Tipografia
| Token | Família | Tamanho/altura | Uso |
|---|---|---|---|
| `--font-ui` | Inter, system-ui (já em uso) | — | Interface |
| `--font-mono` | JetBrains Mono, ui-monospace | — | IDs, logs, diffs, terminal |
| `text-xs` | ui | 12/16 | Badges, metadados |
| `text-sm` | ui | 13/20 | Tabelas, padrão denso |
| `text-base` | ui | 14/22 | Corpo |
| `text-lg` | ui | 16/24 | Títulos de painel |
| `text-xl` | ui | 20/28 | Título de página |
| `text-2xl` | ui | 24/32 | Números de KPI |
Pesos: 400, 500, 600. Números tabulares (`font-variant-numeric: tabular-nums`) em custos, tokens, durações.
Fontes embarcadas no app (sem CDN) para funcionar offline.

## 4. Espaçamento, raio, elevação
- Escala de 4 px: `space-1`=4 … `space-8`=32, `space-12`=48.
- Raio: `radius-sm` 4, `radius-md` 6, `radius-lg` 10.
- Elevação por cor de superfície + borda; sombra apenas em popover/dialog.
- Layout: sidebar 248 px (colapsável para 56), painel inferior (terminal) redimensionável 160–60 % da altura.

## 5. Componentes
| Componente | Variantes | Estados | Observação |
|---|---|---|---|
| Button | primary, secondary, ghost, danger | default, hover, active, focus, disabled, loading | `button.tsx` existente vira base |
| IconButton | — | idem + tooltip obrigatório | |
| Badge / StatusPill | por status (§2.1) | — | ícone + texto |
| StatusDot | running (pulso), success, warning, danger, neutral | — | pulso respeita `prefers-reduced-motion` |
| Card / Panel | default, interactive | hover, selected | |
| Tabs | line, pill | | |
| Table | dense, comfortable | sort, selected, empty, loading | paginação existente |
| Input, Textarea, Select, Combobox | — | error, disabled, readonly | Combobox para modelos (busca por ID) |
| Dialog / ConfirmDialog | default, destructive (digitação de nome — padrão já usado em exclusão) | | |
| Toast | info, success, warning, danger | | |
| Tooltip, Kbd | | | |
| CommandPalette | | | `Ctrl+K` |
| Terminal | follow, paused, filtered | streaming, disconnected | xterm.js ou lista virtualizada (decidir no spike) |
| DiffViewer | split, unified | | somente leitura, texto escapado |
| AgentNode (grafo) | por papel | idle, running, success, failed, skipped, awaiting | React Flow custom node |
| CostValue | reported, estimated, unavailable, subscription | | regra §6 |
| EmptyState, ErrorState, LoadingSkeleton | | | já há padrões em `shared.tsx` |

## 6. Padrões de dados
- **Custo reportado**: `US$ 0,42` normal.
- **Estimado**: `≈ US$ 0,42` + ícone `~` + tooltip "estimativa com catálogo <data>".
- **Assinatura**: `≈ US$ 0,42 equivalente · não cobrado`.
- **Indisponível**: `—` + tooltip "o provedor não reportou uso". Nunca `0`.
- Tokens com separador de milhar e unidade compacta (`12,4 k`).
- Durações: `1 min 32 s`; timestamps relativos com absoluto no tooltip.

## 7. Interação
- Ações com efeito (iniciar run, retomar, override de orçamento, salvar credencial) exigem confirmação explícita com resumo do que acontecerá (padrão atual de "Confirmar e iniciar").
- Ações destrutivas: digitação do nome (padrão atual de exclusão).
- Atalhos: `Ctrl+K` paleta, `Ctrl+\`` terminal, `G P` projetos, `G R` runs, `?` ajuda.
- Movimento: 120–200 ms, `ease-out`; desativado com `prefers-reduced-motion`.
- Atualização em tempo real não rouba foco nem rola o terminal se o usuário rolou para cima (modo "pausado").

## 8. Acessibilidade
Contraste AA (texto) e 3:1 (UI); foco visível; `aria-live=polite` para mudanças de status; nenhuma informação só por cor; alvos ≥ 32 px em desktop.

## 9. Implementação
Tokens semânticos em `frontend/src/styles/tokens.css` (novo) importando `theme.css`; componentes em `frontend/src/components/ui/`; catálogo visual opcional (Storybook ou página `/dev/components` só em dev) — decidir em `V2-DESK-005`.
