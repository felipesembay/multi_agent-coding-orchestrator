# UI/UX — Aplicação desktop

Estado: **proposta**. Telas atuais: Projetos, Workspace, Overview, Execuções, Detalhes, Agentes, Revisões, Configurações (somente leitura).

## 1. Arquitetura de informação
```
App
├── Sidebar
│   ├── Projetos (lista, busca, status do último run por projeto)
│   ├── Execuções (global)
│   ├── Workflows
│   ├── Modelos & Providers
│   ├── Custos
│   └── Configurações
├── Área principal (rota)
└── Painel inferior: Terminal / Logs (global, colapsável)
Topbar: breadcrumb · paleta de comandos · status do backend (dot) · status do worker · tema
```

## 2. Layout base
```
┌───────────┬─────────────────────────────────────────────────────────┐
│ ◉ Conductor│ Projetos / Task API / run-3f2a…        ⌘K   ● API ● Worker│
│───────────│─────────────────────────────────────────────────────────│
│ PROJETOS  │                                                         │
│ ▸ Task API●│               Área principal                            │
│ ▸ CLI tool│                                                         │
│ + Novo    │                                                         │
│───────────│                                                         │
│ Execuções │                                                         │
│ Workflows │─────────────────────────────────────────────────────────│
│ Modelos   │ ▾ Terminal  [run-3f2a ▾] [planner|impl|review|tests] ⏸  │
│ Custos    │ 12:01:03 impl  T2 tentativa 1 iniciada (codex_cli)      │
│ Config    │ 12:02:40 tests python -m pytest -q → 14 passed           │
└───────────┴─────────────────────────────────────────────────────────┘
```

## 3. Telas

### 3.1 Dashboard de execução (`/executions/:runId`)
```
┌ run-3f2a · Task API · "CRUD de tarefas"      ● running · 12 min · ≈US$0,31 ┐
│ Workflow: default-v2 v3   [Pausar] [Ver worktree] [Exportar handoff]       │
├──────────────── Grafo de agentes ─────────────────┬──── Etapa atual ───────┤
│ (Plan ✓)──▶(Impl T2 ◐)──▶(Tests ○)──▶(Review ○)   │ Implementer · codex_cli│
│               ▲________reject (1/3)________│      │ Tentativa 1 de 3       │
├──────────────── Tarefas ──────────────────────────│ Tokens: 12,4k in/3,1k │
│ T1 ✓ Modelo de dados   2 tent.  ≈US$0,12          │ out (cli_reported)     │
│ T2 ◐ Endpoints CRUD    1 tent.                    │ Duração: 1 min 37 s    │
│ T3 ○ Documentação                                 │                         │
├──────────── Abas: Timeline · Testes · Revisões · Diff · Uso · Config ─────┤
```
Estados: `queued` (posição na fila), `running`, `awaiting_approval` (banner âmbar com ação), `ready_for_human_review` (banner verde + checklist de revisão humana), `blocked`, `failed`, `interrupted` (banner com "Inspecionar e retomar").

### 3.2 Visualização gráfica dos agentes
React Flow somente leitura; nós = etapas do workflow; badge com provider/modelo; aresta de rejeição com contador; clique no nó filtra timeline e terminal.

### 3.3 Terminal e logs
Fontes: eventos do run (SSE), stdout/stderr redigido dos agentes (quando o adapter disponibilizar streaming), logs do backend. Filtros por run, papel, nível; busca; pausar auto-scroll; copiar; download. Nunca interpreta ANSI arbitrário além de cores básicas; texto sempre escapado.

### 3.4 Modelos & Providers
```
Agentes CLI (executam no repositório)          Modelos via API (só texto)
┌───────────────────────────────┐              ┌────────────────────────────┐
│ Claude Code  2.1.92  ● pronto │              │ OpenRouter  ● chave salva  │
│ planning·edit·review          │              │ 312 modelos · sync há 2 d  │
│ uso: cli_reported (verificar) │              │ [Gerenciar modelos]        │
│ Codex CLI    0.166   ● pronto │              │ Ollama  ○ não configurado  │
│ Antigravity  1.5.1   ● pronto │              └────────────────────────────┘
└───────────────────────────────┘
```
Separação visual obrigatória entre as duas colunas ([ADR-0004](../architecture/DECISIONS/ADR-0004-model-provider-vs-agent-runtime.md)). "Pronto" = executável encontrado e `probe` ok; texto auxiliar: "autenticação e quota não verificadas".

### 3.5 Workflows
Lista de presets (sistema · usuário). Editor MVP:
```
Workflow: Meu fluxo (rascunho)                       [Validar] [Salvar versão]
1 ▤ Planejamento   [Claude Code ▾] [modelo padrão ▾]  fallback: + Antigravity
2 ▤ Implementação  [Codex CLI ▾]   permissão: escrita na worktree ⚠
     tentativas máx [3]
3 ▤ Testes         perfil: python -m pytest -q
4 ▤ Revisão        [Antigravity ▾] [gemini-… ▾]   ao rejeitar → 2
+ Adicionar etapa (Documentação · Aprovação humana)
Limites: passos 200 · duração 4 h · orçamento US$ [  ]
✓ Validação: 0 erros · 1 aviso (Antigravity: uso não reportado)
```

### 3.6 Custos
Cards: Gasto API (período) · Equivalente assinatura (não cobrado) · Chamadas sem telemetria · Orçamento restante. Gráfico de série temporal (empilhado por modelo, só `api_metered`), tabela por modelo/papel/projeto, comparação de modelos (custo por tarefa aprovada, taxa de aprovação 1ª tentativa), lista de alertas. Seguir [DESIGN_SYSTEM §6](DESIGN_SYSTEM.md#6-padrões-de-dados).

### 3.7 Configurações
Seções: Geral (tema, idioma), Diretórios autorizados, Comandos de teste (allowlist), Execução (tentativas, timeouts), Backend (porta atual, logs, reiniciar), Privacidade (redação), Sobre (versões). Alterações sensíveis pedem confirmação e são auditadas.

### 3.8 Inicialização e erro do backend
Splash com etapas (iniciando backend → banco → worker → pronto); falha mostra mensagem, últimas linhas de log e "Copiar diagnóstico".

## 4. Fluxos principais
1. **Primeiro uso**: onboarding → escolher raiz autorizada → detectar CLIs → (opcional) chave OpenRouter → criar/registrar projeto.
2. **Executar**: projeto → solicitação → "Iniciar" → escolher workflow → revisar resumo (bindings, permissões, orçamento) → confirmar.
3. **Retomar**: run interrompido → "Inspecionar" (diff atual vs checkpoint) → escolher ação → aprovar.
4. **Revisão humana**: run pronto → checklist + diff + testes → marcar decisão (registro em `approvals`; integração Git continua manual).
