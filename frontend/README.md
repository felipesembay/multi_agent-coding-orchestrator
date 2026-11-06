# Agent Control Center

Plataforma local para organizar projetos e requisitos, com observabilidade das execuções reais do Multi-Agent Coding Orchestrator.

**Projetos e solicitações implementados:** cadastro e edição de projetos, associação de repositórios Git existentes, criação confirmada de diretório/repositório e solicitações em linguagem natural persistidas no SQLite. A página inicial agora é **Projetos**; o dashboard anterior continua em `/overview`.

**Execution Manager implementado:** cada solicitação existente tem uma ação “Iniciar execução”, com confirmação e preflight. A API persiste o vínculo projeto–solicitação–run e um worker independente supervisiona o LangGraph real. Aprovação de planos e revisão humana persistida de diffs continuam como entregas futuras. O CLI permanece disponível. Consulte [o guia do Execution Manager](../docs/execution-manager.md).

## Executar

No diretório raiz, ative o ambiente Python e autorize uma pasta de projetos ao iniciar a API:

```bash
source .venv/bin/activate
export ORCH_ALLOWED_ROOTS="$HOME/projects"
export ORCH_TEST_COMMAND="python -m pytest -q"
# Defina ORCH_PLANNER/ORCH_IMPLEMENTER e modelos conforme seu ambiente.
python -m uvicorn orchestrator.api:app --host 127.0.0.1 --port 8765
```

Para cadastrar um repositório existente em outro lugar, autorize o próprio repositório ou sua pasta pai. No Linux, múltiplas raízes são separadas por `:`. Essa autorização é configuração do processo, não pode ser ampliada pelo navegador. Sem `ORCH_ALLOWED_ROOTS`, a aplicação permite consultar projetos já cadastrados, mas bloqueia novos cadastros e execuções e mostra instruções de configuração. Crie a pasta autorizada no servidor se ela ainda não existir.

Para executar solicitações, inicie o worker em outro terminal, também com o ambiente virtual ativo e os mesmos `ORCH_DB`, `ORCH_ALLOWED_ROOTS`, providers e política de testes:

```bash
# Neste terminal também, a partir da raiz do repositório:
source .venv/bin/activate
export ORCH_ALLOWED_ROOTS="$HOME/projects"
export ORCH_TEST_COMMAND="python -m pytest -q"
# Repita ORCH_DB, providers, modelos e política de testes caso os tenha personalizado.
python -m orchestrator.worker
```

Não é uma thread temporária da API. O worker atende a fila persistida; iniciá-lo pode executar jobs já confirmados. Sem worker online, o preflight bloqueia novas execuções e informa como iniciá-lo. Para apenas cadastrar projetos, o worker não é necessário.

Em um terceiro terminal:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Abra `http://127.0.0.1:5173`. **Reinicie a API existente após atualizar o código:** o processo antigo não passa a oferecer os novos endpoints automaticamente. O Vite atualiza a interface durante o desenvolvimento.

O proxy `/api` aponta para `127.0.0.1:8765`. Para outra porta da API, configure `ORCH_API_TARGET=http://127.0.0.1:18765` ao iniciar o Vite. A API deve usar o mesmo `ORCH_DB` do CLI; esse banco também guarda projetos e solicitações.

As origens permitidas por padrão são `http://127.0.0.1:5173`, `http://localhost:5173`, `http://127.0.0.1:8765` e `http://localhost:8765`. Se alterar a porta do frontend, defina a origem exata em `ORCH_ALLOWED_ORIGINS` ao iniciar a API; múltiplas origens usam vírgulas. Não há CORS liberado para sites externos. Use um único processo da API nesta entrega: o token de proteção das escritas é mantido na memória desse processo e renovado no reinício.

O proxy é de desenvolvimento. `vite preview` e hospedagens de `dist/` precisam de um reverse proxy local para `/api` e fallback de rotas para `index.html`. Não publique esta API sem autenticação.

O `export` vale para o terminal atual e os processos iniciados por ele. Um worker iniciado em outro terminal não herda as variáveis exportadas no terminal da API. Se uma execução falhar com erro de diretório no worker, encerre o worker antigo, configure as mesmas variáveis nesse terminal e inicie-o novamente. O run que já falhou permanece no histórico; uma nova tentativa exige nova confirmação em “Iniciar execução”. Não recrie projeto ou solicitação.

## Projetos e solicitações

1. Abra **Projetos → Novo projeto**.
2. Escolha registrar um repositório existente ou criar um projeto novo.
3. Informe nome, descrição, objetivos e caminho absoluto dentro de uma raiz autorizada.
4. Clique em **Revisar projeto**. Essa etapa valida e persiste a prévia; não cria arquivos.
5. Revise as operações, marque a confirmação e conclua o cadastro.
6. No workspace do projeto, escreva um título e requisitos em linguagem natural e clique em **Salvar solicitação**. Para requisitos já registrados, reutilize a solicitação existente.
7. Clique em **Iniciar execução**, confira os agentes, modelos e testes configurados, marque a autorização e confirme.
8. Acompanhe o run na página de execução. O estado é atualizado a cada três segundos enquanto estiver na fila ou em andamento; eventos e resultados sobrevivem à recarga.

Um projeto novo cria somente o diretório final, um repositório Git sem hooks herdados, um `README.md` e um commit inicial local. A confirmação inclui expressamente essas operações. O commit torna o repositório compatível com a exigência de `HEAD` do motor existente. Repositórios registrados não têm seus arquivos, alterações locais ou commits modificados; repositórios sem commit podem ser registrados, mas precisarão de um `HEAD` antes de executar o motor.

A criação exige que o diretório pai já exista e nunca sobrescreve um diretório existente. O fluxo usa descritores de diretório sem seguir symlinks e atualmente é destinado a Linux com `/proc`. Se o Git falhar depois de criar arquivos, a aplicação registra a falha e preserva o diretório para inspeção manual; não apaga arquivos automaticamente.

Projetos podem ser editados, arquivados e reativados. Arquivamento preserva o histórico e bloqueia novas solicitações. As solicitações ficam persistidas e reaparecem após reiniciar a API. Nenhum Markdown de escopo precisa ser escrito pelo usuário.

O histórico do workspace inclui runs com vínculo explícito à solicitação e, separadamente identificados, eventos legados do mesmo caminho canônico do repositório. Eventos antigos não recebem associação fictícia a solicitações. O endpoint aceita `linked_only=true` para retornar somente runs vinculados.

## Persistência e proteção das operações

`orchestrator/project_store.py` aplica migrações aditivas versionadas no banco de `ORCH_DB`: `repositories`, `projects`, `project_requests`, `project_previews`, `platform_audit` e `platform_migrations`. A tabela `events` e o protocolo do CLI são preservados. As relações usam chaves estrangeiras; criação e confirmação repetidas do mesmo token retornam o mesmo projeto, incluindo chamadas concorrentes.

Os endpoints de projetos exigem cliente de rede local e Host loopback. Escritas também exigem Origin autorizado, JSON, corpo de até 150 kB e token CSRF obtido em `/session`. A prévia dura dez minutos, fica vinculada aos dados revisados e os caminhos são revalidados na confirmação. Travessia por `..`, diretórios ocultos e symlinks no caminho do projeto são rejeitados. O diretório Git compartilhado de um repositório também precisa estar dentro da autorização.

A allowlist impede operações do navegador em diretórios não autorizados. Ela e o token CSRF não são isolamento contra processos maliciosos rodando como o mesmo usuário do sistema; worktrees também não são uma sandbox. A execução de agentes exige confirmação específica e configuração válida; o navegador não envia providers, comandos de testes ou caminhos de worktree. O perfil de testes é validado no servidor. O Git é chamado com argumentos fixos, hooks e assinatura desabilitados e sem herdar variáveis `GIT_*` do processo.

| Endpoint novo | Operação |
| --- | --- |
| `GET /session` | Token em memória para proteção das escritas locais |
| `GET /project-policy` | Raízes autorizadas e disponibilidade do Git |
| `GET /projects` | Projetos e quantidade de solicitações |
| `POST /projects/preview` | Validação e prévia persistida; nenhum arquivo criado |
| `POST /projects` | Confirmação por token e cadastro/criação real |
| `GET /projects/{id}` | Dados do projeto |
| `PATCH /projects/{id}` | Editar nome, descrição, objetivos e estado |
| `GET/POST /projects/{id}/requests` | Consultar e registrar solicitações |
| `GET /projects/{id}/runs` | Runs vinculados e histórico legado do mesmo repositório |

## Telas

- **Projetos:** página inicial com busca, cadastro, edição, arquivamento e workspace de requisitos.
- **Overview:** totais globais, distribuição de estados, duração média medida, execuções e atividade recentes.
- **Executions:** busca por Run ID, filtros, ordenação por última atividade e paginação.
- **Execution Details:** rota persistente, projeto e solicitação, estado do worker, erros, configuração congelada, timeline, plano, tentativas, agentes e QA.
- **Agent Monitor:** eventos por papel, providers/modelos históricos quando registrados e últimas implementações.
- **Tests & Reviews:** resultados, findings, sugestões e saída dos testes preservada no SQLite.
- **Settings:** configuração atual permitida e versões dos componentes, sem leitura genérica do ambiente.

O polling global pode ser ajustado entre 5, 10 e 30 segundos ou manual e é salvo no navegador. TanStack Query compartilha o cache, cancela requisições obsoletas e evita sobreposição das consultas da mesma chave.

## Contrato e semântica

| Endpoint | Comportamento |
| --- | --- |
| `GET /health` | Saúde da API e acesso ao banco |
| `GET /runs` | Array retrocompatível, com campos adicionais de resumo; padrão de até 50 execuções |
| `GET /runs?paginated=true` | `{items,total,limit,offset}`; aceita `search`, `status`, `order=asc\|desc`, `limit=1..100`, `offset` |
| `GET /runs/{run_id}` | Resumo consolidado e histórico; 404 se inexistente |
| `GET /runs/{run_id}/events` | Array original com payload string e campo `id` adicional |
| `GET /overview` | Contagens de todas as execuções, amostra da média e oito eventos recentes |
| `GET /settings` | Lista explícita de configurações permitidas e versões |

`finished` usa o **payload.status**, jamais sucesso presumido. `ready_for_human_review` é contado separadamente das execuções concluídas. `blocked` e `error` encerram o intervalo observado; `resumed` retorna o estado para em andamento. A duração média inclui intervalos com início e término registrados, inclusive falhas e revisão humana; não representa tempo de CPU ou tempo ativo do agente. Timestamps SQLite sem fuso são interpretados como UTC e apresentados no fuso do navegador.

Não há heartbeat: “Em andamento” é o último estado observado e pode representar um processo interrompido. Não há duração final para históricos incompletos. Testes da tabela refletem o último resultado disponível; o histórico completo está nos detalhes. Eventos com mesmo timestamp preservam a ordem dos IDs do SQLite.

Payloads passam por parsing seguro e verificações de tipo antes de serem apresentados. Eventos desconhecidos, valores escalares e payloads malformados continuam acessíveis em “Dados originais”. Saídas são texto escapado pelo React, sem HTML de agentes.

## Organização

`orchestrator/projects.py` contém validações e operações de projetos; `project_store.py` cuida da persistência e `local_security.py` protege as rotas novas. `src/features/Projects.tsx` e `ProjectWorkspace.tsx` compõem as novas telas. `src/app` contém roteamento e providers; `src/lib` concentra API, parsing e formatação; `src/types` define contratos. `src/components` contém layout, componentes compartilhados e o botão no padrão shadcn/ui (Radix Slot, CVA e Tailwind). `src/features` agrupa as telas e painéis de execução. O design usa Tailwind CSS v4 e CSS semântico local, sem fontes externas. A distribuição usa uma barra proporcional simples, dispensando Recharts para esta visualização.

## Verificação

```bash
npm run test
npm run build
npm run lint
# Na raiz:
python -m pytest -q
```

Os testes Vitest/Testing Library usam respostas isoladas e cobrem parsing, listagem, seleção, filtros, carregamento, erros, vazios e eventos desconhecidos. A suíte Python usa SQLite temporário e verifica contrato, estados, retomadas, paginação, métricas globais e configurações.

Com API e Vite em execução, os testes Playwright padrão consultam o backend sem gravar dados:

```bash
DASHBOARD_URL=http://127.0.0.1:5173 npm run test:e2e
```

O teste usa Chrome instalado em `/usr/bin/google-chrome`; configure `CHROME_PATH` para outro caminho. Cobre navegação, recarga dos detalhes e telas de projetos em larguras de 390, 768 e 1440 pixels. Capturas locais ficam em `/tmp/orchestrator-*.png`.

O teste de escrita é opt-in (`PROJECTS_E2E_WRITE=1`) e só aceita raízes temporárias cujo caminho comece com `/tmp/orchestrator-projects-qa.`. Use um banco `ORCH_DB` separado, uma pasta `repositories` dentro dessa raiz e a origem correta em `ORCH_ALLOWED_ORIGINS`. Ele cria repositórios e solicitações reais apenas nesse ambiente temporário e verifica criação, confirmação, recarga, edição, arquivamento, reativação e associação de repositório existente. Nunca aponte a API de QA para o banco normal. A suíte Python também usa bancos e repositórios temporários para verificar persistência, concorrência da confirmação, falhas Git e proteções de caminhos e requisições.

## Limites e evolução

A plataforma inicia runs reais com o mesmo grafo e integrações do CLI. Não há aprovação humana do plano/diff nem inspeção de arquivos pelo navegador nesta entrega. Runs interrompidos preservam eventos e worktree para inspeção; não repetem agentes automaticamente. O worker precisa ser iniciado separadamente e é serial por banco. Os detalhes de supervisão, recuperação, concorrência e limites Linux estão no [guia operacional](../docs/execution-manager.md).

O backend consolida o histórico em memória por consulta. Para bancos grandes, o próximo passo é adicionar índices e projeções incrementais de resumo, antes de ampliar o volume e adotar SSE. Providers/modelos históricos não podem ser reconstruídos com segurança a partir das configurações atuais. Uma extensão futura retrocompatível pode acrescentar `provider`, `model`, `task_id` e `duration` aos payloads e registrar o início de cada etapa. Isso também permitirá medir duração por agente e confirmar a etapa ativa.

Na verificação desta entrega, `npm audit --omit=dev` não encontrou vulnerabilidades de produção. O audit completo apontou 10 avisos moderados na cadeia de ferramentas ESLint/TypeScript ESLint, relacionados a `minimatch`; não foi aplicado downgrade ou atualização forçada dessas ferramentas.

O procedimento para a primeira execução real do **Task Manager API**, reutilizando o repositório `/home/felipe/projects/task_manager` e a solicitação já cadastrada, está no [guia de validação](../docs/execution-manager.md#primeira-validação-real-task-manager-api). Esse teste requer confirmação explícita porque consome quotas. Os testes automatizados substituem as chamadas de agentes por mocks.
