# Continuidade do Conductor no Antigravity

Atualizado em 2026-11-19. A fotografia inicial abaixo é histórica; prevalecem BACKLOG/CURRENT_STATE. SEC-003 está em review por validação real pendente; PROV-001 concluída e revisada nesta sessão. Próxima sequência: RES-002, SEC-007, OBS-003. Entrega de origem: V2-WF-010 concluída e aprovada em revisão independente. Commit local em dev com título `V2-WF-010: execute safe frozen fallback chains`; confira o hash em git log.

Este documento permite continuar sem o histórico da conversa. O operador solicitou a transferência porque as quotas de GPT/Claude estão se esgotando. Usar o Antigravity como ambiente de desenvolvimento **não** autoriza chamadas de agentes reais nos testes do produto.

## 1. Comece por aqui

1. Leia [IMPLEMENTATION_PLAN](../planning/IMPLEMENTATION_PLAN.md), [CURRENT_STATE](CURRENT_STATE.md), [NEXT_STEPS](NEXT_STEPS.md) e o [protocolo AGENT_HANDOFF](AGENT_HANDOFF.md).
2. Confira `git branch --show-current`, `git status --short` e `git log --oneline -5`. Trabalhe em **dev**. Preserve alterações que encontrar; não descarte WIP nem mude para main/master.
3. Rode o baseline abaixo e confira os resultados em CURRENT_STATE. Se houver divergência, registre antes de alterar código.
4. Escolha **uma** tarefa do [BACKLOG](../planning/BACKLOG.md), confira suas dependências e marque `doing (Antigravity)`. Leia apenas sua especificação e os ADRs relacionados. Não carregar toda a documentação evita desperdício de contexto.
5. Atualize CURRENT_STATE e SESSION_LOG a cada marco. Antes de `done`, obtenha revisão independente de outro agente ou humano e registre testes/evidência. Se não houver quota para outro agente, deixe `review` e entregue o diff ao operador.

BACKLOG é a fonte de status; CURRENT_STATE contém as evidências atuais. Não considere toda a v2 implementada porque existe uma especificação.

## 2. O que é o projeto

Aplicação local para cadastrar projetos/repositórios Git, escrever solicitações e executar um workflow de agentes. Backend Python/FastAPI + worker separado + SQLite; frontend React/TypeScript/Vite. LangGraph organiza etapas e retornos limitados de revisão. Cada run usa uma worktree Git própria.

O destino é um aplicativo desktop **Conductor** (nome provisório), com Tauri 2 e backend Python como sidecar. Hoje a interface é web local; desktop, empacotamento, retomada gerenciada e contabilidade completa ainda são entregas futuras. Evoluir a v1, preservar seus contratos e testes.

Há duas abstrações distintas: `AgentRuntime` para agentes CLI que podem trabalhar no repositório e `ModelProvider` para geração via API, sem editar arquivos. Não transformar OpenRouter em executor de shell/arquivos.

## 3. Mapa de código

| Área | Entrada principal |
|---|---|
| API e proteção local | `orchestrator/api.py`, `project_api.py`, `workflow_api.py`, `policy/` |
| Projetos, banco e migrações | `orchestrator/projects.py`, `project_store.py` |
| Preflight, digest e fila | `orchestrator/execution_manager.py` |
| Worker e despacho | `orchestrator/worker.py`, `execution_runner.py` |
| Caminho legado | `orchestrator/core.py` e `providers/bindings.py` |
| Providers | `orchestrator/providers/{base,errors,registry}.py`, `runtimes/` |
| Workflow estrito | `orchestrator/workflows/{schema,validation,compiler,nodes,snapshot,execution,store,presets}.py` |
| Confirmação por run | `frontend/src/features/StartExecution.tsx` |
| Editor de definições | `frontend/src/features/Workflows.tsx`, `WorkflowEditor.tsx`, `lib/workflow-editor.ts` |
| Testes | `tests/`, `tests/workflows/`, `frontend/src/test/`, `frontend/e2e/` |
| Verificação documental | `scripts/check_docs.py` |

## 4. O que já existe

- Auditoria/plano, baseline preservado e verificador de documentação.
- CORE-001..004: interfaces/adapters, resultados estruturados, metadados `agent_call`, registry/manifestos e bindings por papel com snapshots.
- SEC-001/002/006: proteção global Host/loopback/origem/token; ambiente de subprocessos por allowlist; Git protegido contra hooks/configurações executáveis não suportadas.
- WF-001..004/007..009: schema e validação; migração aditiva v4; compilador; presets; snapshots/digests por run; API/seleção de providers/modelos na confirmação; editor em lista, cópias e versões imutáveis.
- WF-010: cadeia ordenada por condição normalizada e contrato explícito de retry seguro; IDs/uso por chamada no event store, limites cumulativos e congelamento de todos os alternativos. Conferir aprovação/evidências finais em CURRENT_STATE.
- DIST-004: imagem CI Python fixada em Ubuntu22.04. A falha remota era no setup de Python3.9 em Ubuntu26.04, antes dos testes. A correção ainda depende de push/run autorizado para comprovação no Actions.

**Limites reais:** manifestos dos CLIs ainda não autorizam o novo trio completo em produção. A UI só oferece preset executável quando suas capacidades/permissões forem verificadas. Presets A/C podem ser clonados como rascunhos; B depende de OpenRouter. CLI continua legado. Telemetria real/parsers não foram verificados; uso ausente é `unavailable`, nunca zero. `usage_record` de WF-010 é evento persistido; tabela `usage_records`/migração5 e gravação universal de OBS-001 continuam pendentes.

## 5. Invariantes a preservar

- HTTP valida e enfileira; nunca executa agentes dentro da requisição. Worker é processo separado.
- Configuração, versão, bindings e todos os fallbacks ficam congelados no snapshot/digest confirmado. Despacho não relê registros mutáveis de provider.
- Definição de workflow contém estrutura/políticas; provider/modelo são escolhas separadas por etapa/run. Salvar no editor não inicia agentes.
- Alterar seleção invalida consentimento/preflight. Preservar idempotência, eventos/endpoints legados e tratamento de órfãos.
- Permissões vêm das flags verificadas dos CLIs. Prompt não é sandbox. Não promover `verified`, `code_edit` ou capacidades apenas para liberar uma tela.
- Fallback não repete operação ambígua: `InvocationFailure(..., safe_to_retry=True)` é atestado de adapter confiável de que não houve efeitos. Texto contendo “quota” não basta. CLIs sem esse atestado falham sem retry no caminho estrito. Resultado com `error_code` não é sucesso.
- Cada tentativa de fallback consome limite de passos e, em implementação, limite de tentativas; prazo é absoluto. Falha de persistência impede novo retry.
- Uso/custo mantém fonte e modo de cobrança; não misturar API com assinatura, não inventar preços/tokens. `raw` é omitido dos eventos atuais.
- Chaves nunca em texto puro no SQLite/logs/eventos. Não alterar credenciais. Keyring ainda precisa de SEC-005.
- Aprovação automática do reviewer não é aprovação humana. Gates/budgets sem integração não podem executar por aprovação inventada.
- Sem merge, push, deploy ou alterações em main/master. Commits locais em dev após testes/revisão foram autorizados. Push anterior não é autorização permanente para novos pushes.

## 6. Decisões do operador

Fonte completa: [OPEN_QUESTIONS](../planning/OPEN_QUESTIONS.md).

| Questão | Decisão |
|---|---|
| Q2/Q5 | Padrão desejado Claude → Codex → Antigravity, configurável por etapa. Codex workspace-write aceito; verificar alternativa sem execução se CLI permitir |
| Q3 | Migrar para Python3.12; compatibilidade/checkpoint ainda precisa ser implementada e testada |
| Q4 | Ao fechar com run ativo, perguntar e oferecer continuar em segundo plano |
| Q6 | Ubuntu primeiro, .deb com dependências declaradas; AppImage depois |
| Q7 | Licença explicitamente adiada; não criar LICENSE escolhendo pelo operador |
| Q8/Q9 | Orçamento alerta por padrão, bloqueio opt-in; assinatura separada, equivalente estimado não cobrado |
| Q10 | Somente spikes específicos autorizados, com poucos prompts triviais em temporário. Testes automatizados sempre usam mocks; considerar quotas atuais antes de qualquer validação real |
| Q11 | Futuro commit por tarefa aprovada na worktree/branch agent/run; não na origem, sem merge/push/deploy |
| Q12 | Conductor provisório; identidade pode mudar |

F0-002 continua parcial por revisão formal dos ADRs. Questões respondidas não devem voltar a bloquear suas tarefas específicas. Não aceitar todos os ADRs em nome do operador.

## 7. Tarefas sugeridas para o Antigravity

Execute uma por vez, verificando o status atual no BACKLOG antes de iniciar:

| Ordem sugerida | Tarefa | Entrega e cuidado |
|---|---|---|
| 1 | V2-RES-002 | Checkpointer SQLite com DB separado/thread_id=run_id; não liberar retomada gerenciada sem RES-003/004 |
| 2 | V2-SEC-007 | Auditoria estendida sem valores sensíveis, testes positivos/negativos |
| 3 | V2-OBS-003 | Catálogo manual/import versionado; alterações de preço não mudam custo histórico |

F0-005, DIST-002, SEC-004/005, WF-005/006, OBS-001, RES-001 e PROV-001 foram implementadas. SEC-003 continua review até evidência real ou dispensa explícita; sem consumo de quota nesta sessão. Consulte BACKLOG para status corrente, não use a lista histórica de WF-010 como fila de trabalho.

OpenRouter básico agora executa plan/review com chave consultada no keyring em call time; sem cwd/env/tools no ModelProvider. Referência e modelo explícito ficam congelados no snapshot. Uso reportado é persistido inclusive em resposta inválida; timeout/5xx não autorizam retry cego. Catálogo/preços avançados e UI de chave permanecem tarefas futuras. Somente a sessão do runner recebe D-Bus para Secret Service.

## 8. Verificação sem gastar quota

```bash
source .venv/bin/activate
ORCH_DB="$(mktemp -d)/events.db" python -m pytest -q -p no:cacheprovider
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run lint
python scripts/check_docs.py
git diff --check
```

Validação final WF-010: **561 pytest/54 Vitest**, build/lint/docs verdes, **11 E2E/2 opt-ins skipped** em QA temporário encerrado. Revisão independente aprovada. Backlog nesta entrega: **19 concluídas de63;44 restantes (43 todo,1 blocked)**. Use BACKLOG/CURRENT_STATE para atualizações e versões efetivas; ambiente de origem ainda usa Python3.9.7, migração3.12 pendente. Um aviso de depreciação LangGraph já existia. Falha de TestClient por restrição de sockets deve ser distinguida de teste vermelho; não enfraquecer autenticação para contornar sandbox.

E2E requer API/worker/Vite de QA com DB/repos temporários e agentes substituídos por `tests/fixtures/managed_server.py`. Os testes de escrita de workflows exigem `EXECUTION_E2E_MOCKED=1` e raízes `/tmp/orchestrator-execution-qa.*`; outros opt-ins têm guardas próprios. Não apontar a suíte para o banco normal. Encerrar os serviços temporários ao final. Não presumir que scripts auxiliares em `/tmp` estarão presentes em outra máquina.

## 9. Prompt para colar no Antigravity

> Continue o Conductor neste repositório na branch dev. Leia docs/handoff/ANTIGRAVITY_HANDOFF.md e siga AGENTS.md, IMPLEMENTATION_PLAN e AGENT_HANDOFF. Confira status/log e baseline antes de editar. Escolha uma tarefa liberada do BACKLOG na ordem sugerida; informe o ID escolhido. Faça a implementação completa com testes mockados, revisão independente e handoff por marco. Não chame agentes reais, não consuma quota, não altere credenciais e não faça push/merge/deploy. Preserve WIP, contratos legados, snapshots, permissões e contabilidade honesta. Se uma evidência real ou decisão humana ainda for necessária, deixe a tarefa em review/blocked conforme o protocolo e entregue o ponto exato ao operador. Não marque done apenas porque o código compila.
