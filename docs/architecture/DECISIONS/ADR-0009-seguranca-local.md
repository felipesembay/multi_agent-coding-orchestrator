# ADR-0009 — Segurança local por mecanismo

- **Status:** proposto · **Data:** 2026-11-17 · **Tarefas:** V2-SEC-*

## Contexto
Fatos da auditoria: rotas `/runs*`, `/overview`, `/settings` sem verificação de Host; ambiente completo herdado pelos agentes; Planner Claude com `acceptEdits`; restrição de shell do Implementer só por prompt; testes executam código gerado.

## Decisão
1. Middleware aplica Host/loopback a **todas** as rotas; token obrigatório para todas (bearer no desktop, CSRF no modo navegador).
2. Matriz de permissões por papel (`read`, `write`, `exec`, `network`) aplicada por flags de cada CLI (Claude `--permission-mode`, `--allowedTools/--disallowedTools`; Codex `--sandbox`; agy `--mode`/`--sandbox`) e verificada por teste de `argv`.
3. Ambiente dos subprocessos por allowlist (`PATH`, `HOME`, `LANG`, `TERM`, variáveis exigidas pelo adapter).
4. Ações destrutivas, merge, push, deploy: inexistentes no orquestrador; futuras somente via `approvals`.
5. Isolamento de SO (bubblewrap/containers) para comando de testes e runtimes: fase futura, ADR próprio.

## Consequências
Algumas configurações atuais de usuários podem quebrar (ex.: variáveis exigidas pelos CLIs) → allowlist configurável e mensagens claras.
