# Instruções para agentes

Antes de qualquer alteração, leia [docs/planning/IMPLEMENTATION_PLAN.md](docs/planning/IMPLEMENTATION_PLAN.md) e siga o protocolo [docs/handoff/AGENT_HANDOFF.md](docs/handoff/AGENT_HANDOFF.md).

Regras essenciais:
- Trabalhe em uma tarefa do [BACKLOG](docs/planning/BACKLOG.md) por vez; atualize status e o handoff a cada marco.
- Não chame agentes reais em testes; não consuma quota sem autorização do operador.
- Não faça merge, push ou deploy; não altere credenciais.
- Não declare tarefa concluída sem evidência (teste/commit).
- Testes: `ORCH_DB="$(mktemp -d)/events.db" python -m pytest -q -p no:cacheprovider` e `npm --prefix frontend test`.
