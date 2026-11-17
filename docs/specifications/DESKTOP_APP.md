# TASK 01 — Aplicação desktop e identidade visual

## 1. Identificador e título
`V2-T01` — Desktop Tauri 2 + design system. Subtarefas `V2-DESK-001..010`, `V2-DIST-001..003`.

## 2. Objetivo
Transformar o orquestrador em app desktop (Ubuntu primeiro; Windows/macOS depois) que inicia e encerra o backend sozinho, com UI própria, escura por padrão, inspirada conceitualmente em ferramentas modernas de desenvolvimento assistido (ORCA como referência de experiência, **sem reproduzir marca, ícones, layout ou textos**).

## 3. Estado atual comprovado
Três processos manuais (API, worker, Vite) com `source .env`; frontend React completo para web com tema claro/escuro (WIP), polling; nenhum código desktop; Tauri CLI ausente, Rust disponível. Dependência de Linux (`/proc`, `fcntl`) no worker.

## 4. Requisitos funcionais
- RF1 Abrir o app inicia supervisor → API + worker; UI mostra progresso de inicialização e diagnóstico em falha.
- RF2 Sem navegador nem terminal para o usuário.
- RF3 Fechar o app com run ativo segue política (Q4).
- RF4 Configuração (raízes autorizadas, comando de testes, providers) editável na UI e persistida (substitui `.env` para o desktop; env continua válido no modo dev).
- RF5 Telas: sidebar de projetos, dashboard de execução, grafo de agentes, terminal/logs em tempo real, indicadores de status, modelos/providers, workflows, custos, configurações ([UI_UX.md](../design/UI_UX.md)).
- RF6 Logs do backend acessíveis na UI e em arquivo.
- RF7 Distribuição AppImage e .deb.

## 5. Requisitos não funcionais
- RNF1 Inicialização a frio < 5 s até UI interativa (meta, medir no spike).
- RNF2 Bundle AppImage meta < 150 MB (Python empacotado incluso).
- RNF3 Acessibilidade: contraste AA, navegação por teclado, foco visível (já parcialmente presente).
- RNF4 Uma instância por usuário.
- RNF5 CSP restrita; Tauri capabilities mínimas (sem `shell` genérico para o frontend).

## 6. Arquitetura proposta
- **Shell**: Tauri 2 ([ADR-0002](../architecture/DECISIONS/ADR-0002-tauri-2-desktop.md)); `desktop/src-tauri` com plugins `single-instance`, `log`, `shell` (somente sidecar declarado), `updater` (F6).
- **Frontend**: reutilizar `frontend/` (Vite build → `frontendDist`). `lib/api.ts` passa a obter base URL/token via `invoke('backend_info')` quando `window.__TAURI__` existir; modo web mantém `/api`.
- **Backend**: sidecar binário (PyInstaller `--onedir` preferível a `--onefile` por tempo de start; validar) executando `orchestrator.supervisor` ([ADR-0003](../architecture/DECISIONS/ADR-0003-ciclo-de-vida-do-backend.md)).
- **Configuração**: nova tabela/arquivo `settings` (JSON em `~/.config/multi-agent-orchestrator/settings.json`, sem segredos) lido pelo supervisor e convertido no ambiente de API/worker — mantém o código atual baseado em env.
- **Portas**: efêmera; Origin do WebView adicionada à allowlist por configuração do supervisor.
- **Falhas**: crash da API → supervisor reinicia com backoff (máx. 3) e notifica UI; crash do worker → reinicia; worker já reconcilia órfãos.
- **Logs**: JSON lines por processo, rotação por tamanho, endpoint `/logs/stream` (SSE) para o terminal.

### Distribuição
| Formato | Uso | Observação |
|---|---|---|
| AppImage | Portátil, qualquer distro | Requer FUSE em algumas distros; testar Ubuntu 22.04/24.04 |
| .deb | Instalação Ubuntu/Debian | Declarar `libwebkit2gtk-4.1`, `git` |
| .rpm / Flatpak | Futuro | Flatpak complica acesso a CLIs do host e ao `$HOME` — avaliar |
| Snap | Não recomendado | Confinamento dificulta executar CLIs externos |
| Windows/macOS | Futuro | Worker depende de `/proc`/`fcntl` → requer camada de abstração de processos (ADR futuro) |

## 7. Componentes afetados
`frontend/src/lib/api.ts`, `Layout.tsx`, `local_security.py`, novo `supervisor.py`, CI.

## 8. Arquivos previstos
`desktop/src-tauri/{Cargo.toml,tauri.conf.json,src/main.rs,capabilities/default.json}`, `desktop/sidecar/orchestrator.spec`, `orchestrator/supervisor.py`, `orchestrator/settings_store.py`, `.github/workflows/desktop.yml`.

## 9. Dependências
`V2-F0-004` (spike), `V2-SEC-001` (todas as rotas protegidas), `V2-RES-006` (SSE) para terminal, `V2-F0-005` (Python alvo para empacotar).

## 10. Riscos
| Risco | Mitigação |
|---|---|
| WebKitGTK com bugs/performance (React Flow, xterm.js) | Spike; fallback Electron documentado |
| Empacotar Python + LangGraph | Spike com PyInstaller; alternativa: venv embarcado + python-build-standalone |
| CLIs dos agentes fora do PATH do app (lançado pelo menu, sem `.bashrc`) | Supervisor resolve PATH do login shell uma vez, ou configuração explícita de caminhos dos CLIs na UI |
| Fechar app mata run longo | Q4; tray |
| AppImage sem FUSE | Documentar `--appimage-extract-and-run`; oferecer .deb |

## 11. Critérios de aceite verificáveis
- CA1 Em Ubuntu 24.04 limpo (VM), instalar .deb e abrir o app inicia backend; `ss -ltnp` mostra porta só em 127.0.0.1.
- CA2 Fechar o app sem run ativo deixa zero processos do orquestrador (`pgrep`).
- CA3 Matar a API pelo PID → UI mostra reconexão e volta em < 10 s.
- CA4 Requisição à API sem token → 401/403.
- CA5 Todas as telas de RF5 navegáveis por teclado; contraste AA verificado por ferramenta.

## 12. Testes necessários
Unitários do supervisor (porta, token, reinício), vitest para `api.ts` dual-mode, e2e web existentes, e2e desktop via tauri-driver (avaliar viabilidade), smoke de pacote em CI (instalar .deb em container e iniciar headless com xvfb).

## 13. Complexidade
DESK-001: M · 002: M · 003: L · 004: S · 005: M · 006: M · 007: M · 008: M · 009: M · 010: M · DIST-001: L · 002: S · 003: L.

## 14. Prioridade
P1 (DESK-001..006 — MVP) · P2 (007..010, DIST-001) · P3 (DIST-003, Windows/macOS).

## 15. Perfil recomendado
Rust/Tauri + React (shell e frontend); Python para supervisor; designer/frontend para design system.
