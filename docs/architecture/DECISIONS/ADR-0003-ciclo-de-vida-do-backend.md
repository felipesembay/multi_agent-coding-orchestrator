# ADR-0003 — Ciclo de vida do backend no desktop

- **Status:** proposto · **Data:** 2026-11-17 · **Tarefas:** V2-DESK-002/003/004

## Contexto
Hoje o operador inicia API, worker e Vite em três terminais com o mesmo `.env`. A API pode reiniciar sem matar o worker; um worker por banco.

## Decisão
1. Tauri inicia **um** sidecar `orchestrator-supervisor` (novo `orchestrator/supervisor.py`).
2. O supervisor escolhe porta efêmera em `127.0.0.1`, gera token de sessão aleatório, inicia API (uvicorn) e worker como **processos filhos separados** (preserva a invariante), grava logs rotativos em `~/.local/state/multi-agent-orchestrator/logs/`, e escreve em stdout uma linha JSON `{"port":…, "token":…, "pid":…}` lida pelo Rust.
3. Rust expõe comando `backend_info` ao frontend; frontend usa `Authorization: Bearer` em todas as chamadas.
4. Health-check com backoff; falha → tela de diagnóstico com logs e botão reiniciar.
5. Fechar janela: se não há run ativo, SIGTERM ao grupo do supervisor (que repassa para API e worker; worker já trata SIGTERM preservando worktree). Se há run ativo: comportamento definido em [OPEN_QUESTIONS](../../planning/OPEN_QUESTIONS.md) Q4 (decisão do operador em 2026-11-18: perguntar, com opção continuar em segundo plano; implementação do tray/supervisor ainda pendente).
6. Instância única do app (plugin single-instance) + flock do worker já existente.

## Alternativas rejeitadas
| Alternativa | Motivo |
|---|---|
| Porta fixa 8765 | Conflito com instalação dev; previsível para outros processos |
| API e worker no mesmo processo | Quebra invariante de reinício independente |
| systemd user service | Útil no futuro para runs longos em background; complexo para MVP |
| Unix socket em vez de TCP | WebView não acessa UDS diretamente; exigiria proxy em Rust — reavaliar para endurecimento |

## Consequências
`local_security.py` precisa aceitar a origem do Tauri (`tauri://localhost` / `http://tauri.localhost`, a verificar) e o token bearer. Modo dev (Vite + 3 processos) continua suportado.
