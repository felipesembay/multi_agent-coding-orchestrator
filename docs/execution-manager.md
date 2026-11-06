# Execution Manager

Execução real de solicitações persistidas pelo navegador. A API enfileira; um worker independente supervisiona um subprocesso por workflow. O subprocesso chama `core.execute_scope()`, compartilhado com `core.execute()` do CLI. Não existe caminho de simulação no backend de produção.

## Iniciar os serviços

Use o mesmo ambiente, `ORCH_DB`, autorização de diretórios e política de testes na API e no worker. Na raiz deste repositório, em cada terminal Python:

```bash
source .venv/bin/activate
export ORCH_ALLOWED_ROOTS="$HOME/projects"
export ORCH_TEST_COMMAND='python -m pytest -q'
# Configure os providers que você já utiliza; padrões do motor: claude/claude.
export ORCH_PLANNER=claude
export ORCH_IMPLEMENTER=antigravity
# Quando Antigravity estiver selecionado, use seu modelo configurado:
# export ORCH_IMPLEMENTER_MODEL=...
```

API:

```bash
python -m uvicorn orchestrator.api:app --host 127.0.0.1 --port 8765
```

Worker, em outro terminal com a mesma configuração:

```bash
# Neste terminal também, a partir da raiz do repositório:
source .venv/bin/activate
export ORCH_ALLOWED_ROOTS="$HOME/projects"
export ORCH_TEST_COMMAND="python -m pytest -q"
# Repita ORCH_DB, providers, modelos e política de testes caso os tenha personalizado.
python -m orchestrator.worker
```

Frontend, em um terceiro terminal:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Iniciar o worker processa jobs previamente confirmados que estejam `queued`. Um worker novo não recria projetos nem solicitações. Não inicie o worker com um banco de testes apontando para dados reais. O worker não depende do ciclo de vida do FastAPI: reiniciar a API não encerra um workflow em andamento. Esta entrega executa um workflow de cada vez por worker/banco, com fila FIFO; repositórios diferentes podem aguardar na fila. Há bloqueio exclusivo de um worker por banco.

O frontend apresenta a presença de executáveis e a configuração real do processo da API. Presença no PATH não comprova autenticação ou quota disponível. Credenciais continuam sendo configuradas nos próprios CLIs, fora do navegador. Alterações nas políticas ou no ambiente devem ser aplicadas reiniciando API e worker; jobs já confirmados preservam uma cópia da configuração de execução e serão revalidados no despacho.

O `export` vale para o terminal atual e os processos iniciados por ele. Um worker iniciado em outro terminal não herda as variáveis exportadas no terminal da API. Se uma execução falhar com erro de diretório no worker, encerre o worker antigo, configure as mesmas variáveis nesse terminal e inicie-o novamente. O run que já falhou permanece no histórico; uma nova tentativa exige nova confirmação em “Iniciar execução”. Não recrie projeto ou solicitação.

## Fluxo e contrato

Abra um projeto, localize a solicitação existente e clique em **Iniciar execução**. A confirmação mostra projeto, repositório, requisitos salvos, planner, implementer, reviewer, modelos conhecidos, testes, tentativas e presença do worker. A configuração é somente leitura. Marcar a confirmação e clicar em **Confirmar e iniciar** é a autorização para consumir quotas e modificar a worktree.

| Endpoint | Comportamento |
| --- | --- |
| `GET /projects/{id}/execution-config` | Preflight tipado, configuração pública, digest, erros e presença do worker |
| `POST /projects/{id}/requests/{request_id}/runs` | `202` com `run_id`, estado, projeto e solicitação |
| `GET /projects/{id}/runs` | Runs vinculados mais histórico legado do mesmo repositório, distinguíveis por `project_id`/`request_id` |
| `GET /projects/{id}/runs?linked_only=true` | Somente runs com vínculo persistente explícito ao projeto |
| `GET /runs` | Contrato de listagem anterior preservado; inclui runs gerenciados, mesmo antes do primeiro evento |
| `GET /runs/{run_id}` | Estado consolidado, vínculo, configuração congelada, horários, erro e eventos |
| `GET /runs/{run_id}/events` | Mesmo contrato de payload string; disponível após recarga ou reinício |

O POST aceita somente:

```json
{
  "confirmed": true,
  "configuration_digest": "digest retornado pelo preflight",
  "idempotency_key": "identificador único desta intenção de execução"
}
```

A chave é reutilizada quando o frontend precisa repetir uma resposta incerta. Repetições da mesma intenção retornam o Run ID existente, inclusive depois que ele termina. Outra intenção de execução recebe nova chave. O banco reserva a identidade Git compartilhada do repositório, não apenas o ID do projeto: dois projetos apontando para o mesmo repositório não executam juntos.

Respostas principais: `404` para entidade inexistente; `409` para solicitação de outro projeto, repositório ocupado/sujo ou configuração alterada; `403` para diretório ou requisição não autorizados; `422` para configuração, Git ou corpo inválidos; `503` se o worker estiver offline. Falha do processo depois de um `202` é persistida como estado de execução, não disfarçada como sucesso HTTP.

## Persistência e estados

A migração 2 adiciona `managed_runs`, `execution_worker` e índices. O registro do run é também a fila durável: guarda projeto, solicitação, título e requisitos copiados, configuração, idempotência, reserva Git, horários, PID e identidade do processo, heartbeat, falha e resultado. O token interno de despacho e os dados internos de processo não são serializados nas respostas públicas. A tabela `events` existente continua sendo a fonte da timeline.

| Estado | Significado |
| --- | --- |
| `queued` | Solicitação confirmada, persistida e reservada, aguardando o worker |
| `running` | Worker iniciou o subprocesso; inclui preparação da worktree e execução do grafo |
| `ready_for_human_review` | Resultado real do motor; implementação e QA concluídos, falta análise humana |
| `blocked` | Motor esgotou as tentativas sem aprovação do QA |
| `failed` | Preflight de despacho, inicialização ou workflow falhou |
| `interrupted` | Processo foi interrompido ou houve reconciliação após reinício do worker |

`queued`, `running`, `failed` e `interrupted` são estados do gerenciador; não são inferências de sucesso a partir de eventos. `ready_for_human_review` e `blocked` vêm do retorno do motor. Eventos adicionais `stage_started` identificam início de planejamento, implementação e revisão nas execuções gerenciadas. Um provider configurado não é automaticamente apresentado como provider histórico comprovado: fallback e eventos antigos continuam separados da configuração.

A tela de execução consulta a API a cada três segundos enquanto o run está `queued` ou `running`, mesmo se o polling geral estiver pausado. Ao terminar, volta ao intervalo global. O resultado contém título da solicitação, nome do projeto, Run ID nos detalhes, etapa, plano, tentativas, testes, findings, worktree e erro/estado final.

## Interrupção, órfãos e concorrência

- Encerrar normalmente o worker interrompe o subprocesso ativo e preserva o histórico e a worktree. Jobs ainda na fila continuam persistidos.
- Se o worker sofrer uma queda abrupta, o subprocesso pode continuar até terminar ou até o worker ser reiniciado. A reserva persistente e o lock Git impedem um segundo workflow conflitante. A API mostra worker offline no preflight e avisa na página de acompanhamento quando a atividade do supervisor não está confirmada; ela não inventa um término enquanto aguarda reconciliação.
- Ao reiniciar, o worker reconcilia runs `running`. Só sinaliza grupos de processos cuja identidade foi comprovada por boot, PID e instante de criação, ou por token de despacho herdado.
- Grupos sem identificação suficiente não são encerrados. O run vira `interrupted` com `orphaned=true`, mantendo a reserva. O worker volta a verificar e libera a reserva quando não restarem processos do grupo. Não há botão que finja resolver essa situação.
- Não há repetição automática de chamada de agente nem promessa de execução “exatamente uma vez” dos efeitos externos. Uma interrupção pode deixar arquivos parcialmente modificados.
- Inspecione a worktree interrompida antes de autorizar um novo run. Um novo run cria outra worktree a partir do HEAD do repositório de origem; não incorpora automaticamente alterações da worktree anterior. Retomada gerenciada de um checkpoint não faz parte desta entrega.
- O CLI mantém seus comandos para runs legados; `resume` não assume o controle de runs gerenciados, evitando divergência entre eventos e lifecycle. Ele usa o mesmo lock advisory por diretório Git compartilhado. O lock é herdado pelos subprocessos diretos das ferramentas. Processos externos que ignorem o lock não são impedidos de modificar arquivos.

A supervisão usa grupos de processos e `/proc`, portanto esta implementação é Linux. Grupos de processos e worktrees não são sandbox; ferramentas que escapem do grupo ou processos maliciosos exigem isolamento adicional do sistema operacional.

## Política de testes e caminhos

O navegador não envia providers, modelos, caminhos de worktree nem comandos de shell. O servidor usa as configurações existentes e valida Git, HEAD, repositório limpo, diretórios autorizados, ferramentas locais e perfil de testes. O worker repete as verificações antes de chamar o motor. O diretório-base de worktrees é `ORCH_WORKTREES` ou a pasta irmã `<repositorio>-agent-worktrees`, sempre dentro de uma raiz autorizada.

Perfis padrão permitidos: `python -m pytest -q`, `python3 -m pytest -q`, `pytest -q`, `npm test`, `npm test -- --run` e `npm run test -- --run`. Para um perfil específico, configure no servidor uma allowlist JSON de argumentos exatos:

```bash
export ORCH_TEST_COMMAND='/caminho/absoluto/python -m pytest -q'
export ORCH_ALLOWED_TEST_COMMANDS='[["/caminho/absoluto/python","-m","pytest","-q"]]'
```

Não use executáveis relativos como `.venv/bin/python`: o comando será executado na worktree. Não são instaladas dependências automaticamente. Permitir um perfil de testes autoriza executar o código de testes daquele repositório, não o torna seguro contra código malicioso. Não coloque credenciais em argumentos de comandos. O token CSRF, Origin, Host, cliente loopback e limites de corpo continuam protegendo os novos POSTs em `/projects`.

## Verificação automatizada

```bash
python -m pytest -q
cd frontend
npm test
npm run build
npm run lint
```

A integração de subprocesso em `tests/fixtures/managed_workflow.py` usa o LangGraph, Git, worktree e pytest reais, com **todas** as chamadas de agentes mockadas. Ela não usa quotas. Os testes cobrem despacho, vínculos, duplicação, concorrência, preflight, falha de spawn, eventos, resultado, interrupção, órfãos e preservação do CLI.

O teste de navegador do fluxo completo é opt-in e exige o harness `tests/fixtures/managed_server.py`, que recusa bancos fora de `/tmp/orchestrator-execution-qa.*`. Em uma pasta temporária criada com `mktemp -d /tmp/orchestrator-execution-qa.XXXXXX`, crie `repositories/`, configure `ORCH_DB` para `events.db` dentro dessa pasta, `ORCH_ALLOWED_ROOTS` para `repositories/` e um perfil de testes autorizado. Inicie o harness com os argumentos `api` e `worker` em processos separados, configure o Vite para a API de QA em `127.0.0.1:18765` e autorize a origem do Vite. O harness cria somente um projeto temporário explicitamente identificado como teste e mocka os agentes.

```bash
DASHBOARD_URL=http://127.0.0.1:15173 EXECUTION_E2E_MOCKED=1 npm run test:e2e
```

Não use `EXECUTION_E2E_MOCKED` como autorização para rodar contra a API normal: esse sinalizador pertence somente à suíte Playwright, e o teste verifica a raiz temporária do backend. O código de produção não tem provider falso nem variável que simule execução.

## Primeira validação real: Task Manager API

O projeto já cadastrado é `Task Manager API`, em `/home/felipe/projects/task_manager`. A solicitação existente é **Criar uma API REST para gerenciar tarefas pessoais.** Não recrie projeto, solicitação ou repositório.

1. Obtenha confirmação explícita do operador: esse teste chama providers reais e consome quotas.
2. Confira que o repositório existente tem HEAD e está limpo, sem apagar ou sobrescrever arquivos.
3. Inicie API e worker com o banco atual, `ORCH_ALLOWED_ROOTS=/home/felipe/projects`, providers/modelos já configurados e comando de testes autorizado. Não use os harnesses de teste.
4. Abra o projeto existente e clique em **Iniciar execução** na solicitação já registrada.
5. Confira a configuração exibida; confirme para registrar o job real.
6. Acompanhe planejamento, implementação, testes e revisão na página de execução. Recarregue a página para verificar persistência.
7. Inspecione testes, findings e a worktree indicada. `blocked` ou `failed` são resultados reais possíveis e devem ser investigados; não significam que houve sucesso só porque o processo terminou.
8. Se o motor retornar `ready_for_human_review`, revise as alterações antes de qualquer integração manual. O sistema não faz merge, push ou deploy.

A implementação e os testes mockados não executam essa validação real automaticamente. Aprovação do plano, aprovação humana persistida do diff, continuidade sobre alterações ainda não integradas e inspeção de arquivos pelo navegador continuam como evoluções separadas.
