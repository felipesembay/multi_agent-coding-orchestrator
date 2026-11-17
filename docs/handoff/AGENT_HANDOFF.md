# Protocolo obrigatório de handoff entre agentes

Aplica-se a qualquer agente (Claude, Codex, Antigravity, outro) ou humano que trabalhe neste repositório. Objetivo: o próximo agente continua **sem acesso à conversa anterior**.

## 1. Início de sessão (checklist)

1. Ler [IMPLEMENTATION_PLAN.md](../planning/IMPLEMENTATION_PLAN.md), [CURRENT_STATE.md](CURRENT_STATE.md) e [NEXT_STEPS.md](NEXT_STEPS.md).
2. Rodar `git status --short` e `git log --oneline -5`; comparar com CURRENT_STATE. Divergência → registrar no SESSION_LOG antes de agir.
3. Rodar a verificação de baseline (comandos em NEXT_STEPS). Testes vermelhos no início → registrar, não "consertar" silenciosamente fora do escopo.
4. Escolher **uma** tarefa do [BACKLOG](../planning/BACKLOG.md) cujas dependências estejam `done`. Marcar `doing` com seu identificador de agente.
5. Ler apenas a especificação e os ADRs dessa tarefa.

## 2. Durante a sessão — checkpoints de documentação

Atualize CURRENT_STATE e SESSION_LOG **a cada marco**, não só no fim (o contexto ou a quota podem acabar a qualquer momento):

| Marco | Atualização mínima |
|---|---|
| Testes novos escritos (vermelhos) | SESSION_LOG: arquivos de teste e intenção |
| Testes verdes | CURRENT_STATE: tarefa, arquivos, resultado do teste |
| Decisão arquitetural | ADR novo ou atualização do ADR existente |
| Bloqueio | BACKLOG `blocked` + motivo em NEXT_STEPS |
| Antes de qualquer operação longa ou arriscada | CURRENT_STATE com estado atual |

Commits pequenos e frequentes (quando autorizados pelo operador) também são checkpoints. Mensagem de commit inclui o ID da tarefa.

## 3. Fim de sessão (obrigatório)

Preencher uma entrada em [SESSION_LOG.md](SESSION_LOG.md) com o [template](templates/SESSION_HANDOFF_TEMPLATE.md) e atualizar:

- **CURRENT_STATE.md**: o que existe agora (fatos), testes e resultados, WIP não commitado.
- **NEXT_STEPS.md**: próxima tarefa recomendada, critérios de aceite, comandos.
- **BACKLOG.md**: status de cada tarefa tocada, com evidência para `done`.

Conteúdo obrigatório da entrada:
1. O que foi planejado.
2. O que foi implementado (com IDs).
3. Arquivos modificados (`git diff --stat`).
4. Testes executados e resultados (comando + contagem).
5. Decisões arquiteturais (link ADR).
6. Problemas encontrados.
7. Pendências.
8. Próxima tarefa recomendada.
9. Critérios de aceite da próxima tarefa.
10. Comandos necessários para continuar.

## 4. Regras

- Não declarar `done` sem evidência verificável.
- Não reescrever o histórico do SESSION_LOG; apenas acrescentar.
- Fatos, hipóteses e recomendações rotulados (`[FATO]`, `[HIPÓTESE]`, `[RECOMENDAÇÃO]`) quando houver dúvida.
- Não registrar segredos, caminhos pessoais sensíveis ou saídas brutas de agentes nos documentos.
- Se uma decisão humana pendente ([OPEN_QUESTIONS](../planning/OPEN_QUESTIONS.md)) bloquear a tarefa, parar e registrar — não presumir.
- Revisão: a tarefa implementada por um agente deve ser revisada por outro agente ou humano antes de `done` (status `review` no intervalo).

## 5. IDs

`V2-<ÁREA>-<NNN>`; áreas: `F0`, `CORE`, `PROV`, `WF`, `OBS`, `RES`, `DESK`, `DIST`, `SEC`, `DOC`. IDs nunca são reutilizados; tarefas abandonadas ficam `dropped`. Novas tarefas recebem o próximo número livre da área.

## 6. Automação planejada

- `V2-DOC-001`: `scripts/check_docs.py` valida links, IDs citados existentes no BACKLOG e data de CURRENT_STATE ≥ último commit que tocou código.
- `V2-DOC-002`: para runs do produto, handoff gerado deterministicamente a partir de eventos e ledger (não depende de tokens).
