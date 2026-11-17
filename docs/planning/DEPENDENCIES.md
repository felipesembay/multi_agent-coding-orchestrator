# Dependências

## 1. Grafo de tarefas (caminho crítico do MVP em destaque)

```mermaid
flowchart LR
    F0_001[F0-001 baseline] --> CORE001[CORE-001 AgentRuntime]
    F0_002[F0-002 ADRs/Q] --> F0_003[F0-003 spike telemetria]
    F0_002 --> F0_004[F0-004 spike Tauri]
    F0_002 --> F0_005[F0-005 Python]
    CORE001 --> CORE002[CORE-002 resultado estruturado]
    CORE001 --> CORE003[CORE-003 registry]
    CORE001 --> SEC003[SEC-003 planner read-only]
    CORE003 --> CORE004[CORE-004 bindings]
    CORE004 --> SEC004[SEC-004 matriz permissões]
    CORE003 --> WF001[WF-001 schema]
    WF001 --> WF002[WF-002 migração 4]
    WF001 --> WF003[WF-003 compilador]
    CORE004 --> WF003
    WF003 --> WF004[WF-004 presets]
    WF002 --> WF007[WF-007 snapshot]
    WF003 --> WF007
    WF007 --> WF008[WF-008 API/UI]
    WF008 --> WF009[WF-009 editor lista]
    SEC004 --> WF005[WF-005 Codex executor]
    CORE004 --> WF006[WF-006 agy reviewer]
    SEC005[SEC-005 keyring] --> PROV001[PROV-001 OpenRouter]
    CORE003 --> PROV001
    CORE002 --> OBS001[OBS-001 usage_records]
    F0_003 --> OBS002[OBS-002 parsers]
    OBS001 --> OBS002
    OBS001 --> OBS008[OBS-008 uso por run]
    WF003 --> RES001[RES-001 ledger]
    F0_005 --> RES002[RES-002 checkpointer]
    WF003 --> RES002
    RES001 --> RES003[RES-003 retomada]
    RES002 --> RES003
    RES004[RES-004 aprovações] --> RES003
    SEC001[SEC-001 rotas] --> DESK002[DESK-002 supervisor]
    F0_004 --> DESK001[DESK-001 Tauri]
    DESK001 --> DESK004[DESK-004 token/origem]
    DESK002 --> DESK004
    DESK002 --> DESK003[DESK-003 sidecar]
    F0_005 --> DESK003
    DESK005[DESK-005 design system] --> DESK006[DESK-006 shell UI]

    classDef crit fill:#253550,stroke:#799ee9,color:#e5e7eb
    class F0_001,CORE001,CORE003,CORE004,WF001,WF003,WF007,WF008 crit
```

Tarefas sem dependência que podem começar em paralelo a qualquer momento após F0-001: `SEC-001`, `SEC-002`, `SEC-006`, `DESK-005`, `DIST-002`, `DOC-001`.

## 2. Dependências externas

| Dependência | Uso | Estado | Risco |
|---|---|---|---|
| Python 3.9 (atual) → 3.11+? | Backend, empacotamento | 3.9.7 instalado, EOL out/2025 | Libs novas podem exigir ≥3.10 (Q3) |
| LangGraph 0.6.11 (`<2` em requirements) | Engine | Instalado | Migração para 1.x pode exigir ajustes |
| `langgraph-checkpoint-sqlite` | Checkpoints | Não instalado | Compatibilidade a verificar |
| `keyring` + libsecret/Secret Service | Credenciais | Não instalado | Sem D-Bus em headless |
| Tauri 2 CLI + `libwebkit2gtk-4.1-dev` | Desktop | Rust presente; Tauri ausente | WebKitGTK |
| PyInstaller (ou alternativa) | Sidecar | Não instalado | Tamanho/tempo de start |
| `@xyflow/react` | Grafo/editor | Não instalado | Performance em WebKitGTK |
| xterm.js (opcional) | Terminal | Não instalado | Pode ser substituído por lista virtualizada |
| Claude Code 2.1.92, Codex 0.166.0, agy 1.5.1 | Runtimes | Instalados | Formatos de saída mudam entre versões |
| OpenRouter API | ModelProvider | — | Rede, rate limits, mudanças de API |
| Ollama | ModelProvider local | Instalado | F6 |

Nenhuma dependência foi instalada nesta sessão.
