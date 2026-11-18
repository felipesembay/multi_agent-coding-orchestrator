# ADR-0002 — Tauri 2 como shell desktop

- **Status:** proposto (depende do spike V2-F0-004) · **Data:** 2026-11-17 · **Tarefas:** V2-DESK-*, V2-DIST-*

## Contexto
O usuário quer app desktop, prioridade Ubuntu, futuro Windows/macOS, sem abrir navegador nem terminais. O frontend React/Vite já existe. `cargo`/`rustc` estão instalados; Tauri CLI não.

## Decisão
Usar Tauri 2 com o frontend React existente e o backend Python como sidecar. Ordem de bundles decidida pelo operador em 2026-11-18 (Q6): Ubuntu e .deb primeiro, com dependências declaradas; AppImage depois. Assinatura de pacotes permanece indefinida; decisão sobre Tauri ainda depende do spike e revisão deste ADR.

## Comparação
| Critério | Tauri 2 | Electron | PyWebView | Wails | Qt (PySide6) |
|---|---|---|---|---|---|
| Tamanho do bundle | Pequeno (webview do SO) | Grande (Chromium) | Pequeno | Pequeno | Médio/grande |
| RAM | Baixa | Alta | Baixa | Baixa | Média |
| Consistência de renderização Linux | **Risco**: WebKitGTK | Alta (Chromium) | WebKitGTK | WebKitGTK | Qt WebEngine (Chromium) |
| Reuso do React atual | Total | Total | Total | Total | Parcial (WebEngine) |
| Sidecar e ciclo de vida | API nativa de sidecar | `child_process` | Python é o host | Go host | Python é o host |
| Segurança (capabilities, CSP) | Forte, allowlist | Exige hardening manual | Fraca | Média | Média |
| Bundles Linux | AppImage, .deb, .rpm | AppImage, .deb, snap… | Manual | Manual | Manual |
| Auto-update | Plugin oficial | electron-updater | Não | Não | Não |

## Alternativas rejeitadas
- **Electron:** maior maturidade e Chromium consistente, mas ~100 MB+ e alta RAM; reconsiderar **se** o spike revelar falhas graves de WebKitGTK (fallback documentado).
- **PyWebView:** simplifica o empacotamento (Python é o host), mas sem tray/updater/capabilities maduros.
- **Wails/Qt:** adicionam linguagem ou reescrevem UI sem ganho claro.

## Consequências
Rust entra no repositório (pequeno). Testes e2e desktop dependem de WebKitWebDriver (tauri-driver) no Linux. Empacotar Python é o maior risco.

## Validação (spike V2-F0-004)
Janela Tauri carregando o build do frontend atual no Ubuntu; sidecar Python iniciado e encerrado; React Flow e terminal renderizando a 60 fps em WebKitGTK; .deb instalado e executável em Ubuntu limpo, conforme prioridade Q6; validação de AppImage na etapa posterior.
