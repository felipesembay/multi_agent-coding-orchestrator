# TASK 07 — Segurança e governança

## 1. Identificador e título
`V2-T07` — Segurança local e governança de agentes. Subtarefas `V2-SEC-001..008`.

## 2. Objetivo
Reduzir riscos de múltiplos agentes executando ferramentas e alterando arquivos, com controles por mecanismo ([ADR-0009](../architecture/DECISIONS/ADR-0009-seguranca-local.md)).

## 3. Estado atual comprovado
| Controle | Estado |
|---|---|
| Worktree por run | ✓ (não é sandbox) |
| Allowlist de diretórios | ✓ `ORCH_ALLOWED_ROOTS`, sem symlink/oculto/`..` |
| Allowlist de comando de testes | ✓ argv exato, sem shell |
| Host/Origin/CSRF | SEC-001 implementada: todas as rotas, token em leituras/escritas; bootstrap local /session e liveness /health sem token |
| Permissões por papel | Parcial — Codex `read-only`; Claude `acceptEdits` também no Planner; shell do Implementer proibido só por prompt |
| Ambiente dos subprocessos | SEC-002 implementada: allowlists exatas por runner/adapter/tests/git; credenciais ambientais não herdadas por padrão |
| Git endurecido | SEC-006 implementada em core/projects/locks: hooks/fsmonitor/conversores desligados, formas não interativas fixas, filtros executáveis recusados |
| Auditoria | ✓ `platform_audit` para catálogo e lifecycle |
| Merge/push/deploy | ✓ inexistentes |
| Rede | ✗ sem política |
| Isolamento de SO | ✗ |

## 4. Requisitos funcionais
- RF1 Todas as rotas exigem loopback + Host válido + token.
- RF2 Matriz de permissões por papel aplicada em `argv` (§6).
- RF3 Ambiente por allowlist para runner, agentes e comando de testes.
- RF4 Aprovação humana para: retomada, override de orçamento, ativar `workspace_write` com execução de comandos (Codex), e qualquer ação futura classificada como sensível.
- RF5 Log de auditoria para todas as decisões humanas e mudanças de config/credenciais (sem valores).
- RF6 Conteúdo de agente/repositório tratado como não confiável (prompt injection): delimitado, nunca interpretado como instrução do orquestrador, saídas sempre validadas por schema.

## 5. Requisitos não funcionais
- RNF1 Nenhum controle depende só de prompt.
- RNF2 Testes de regressão para cada controle (argv, env, rotas).
- RNF3 Falha fechada: configuração inválida → recusar execução.

## 6. Arquitetura proposta

### 6.1 Matriz de permissões
| Papel | Ler repo | Escrever worktree | Executar comandos | Rede | Mecanismo |
|---|---|---|---|---|---|
| planner | ✓ | ✗ | ✗ | provider apenas | Claude `--permission-mode plan`; agy `--mode plan`; Codex `--sandbox read-only` |
| implementer | ✓ | ✓ | ✗ (padrão) / ✓ (opt-in Q5) | provider apenas | Claude `acceptEdits` + `--disallowedTools Bash`; agy `accept-edits`; Codex `workspace-write` |
| reviewer | ✓ | ✗ | ✗ | provider apenas | modos read-only |
| tests (orquestrador) | ✓ | ✓ | só argv allowlist | herdada (futuro: bloqueada) | `run_command` com env allowlist |
| model_provider (API) | só contexto enviado | ✗ | ✗ | HTTPS para o provider | nunca recebe caminho |
Flags exatas a confirmar por teste com cada versão de CLI.

### 6.2 HTTP
Middleware único para todas as rotas: loopback, Host em allowlist (`127.0.0.1:<porta>`, `localhost:<porta>`), Origin (navegador dev ou origem Tauri), token (`Authorization: Bearer` ou `X-Orchestrator-CSRF`), limite de corpo, cabeçalhos `no-store`/`nosniff`. `/health` pode ficar sem token mas com Host check. `/settings` deixa de expor caminho absoluto do banco ou passa a exigir token.

### Implementação de SEC-001 (2026-11-17)

`protect_routes` aplica a política a todas as requisições, incluindo docs, openapi e rotas inexistentes; não há allowlist de prefixos protegidos. Exige peer IP loopback (não confia em X-Forwarded-For no middleware), exatamente um Host local bem formado (localhost/127.0.0.1/[::1], porta opcional válida), e rejeita Origin fora da allowlist, Origin duplicado ou Sec-Fetch-Site cross-site. Respostas normais e rejeições recebem no-store/nosniff/CORP same-origin. Corpos são limitados a 150 kB por bytes reais, incluindo chunked/GET; Content-Length não autoriza corpo maior.

**Exceções explícitas de bootstrap:** GET/HEAD `/health` não exige token, mas conserva todas as verificações locais. GET/HEAD `/session` também dispensa token para que o navegador possa obter CSRF; conserva Host/peer/origem e não libera CORS. Devolve apenas csrf_token, nunca o bearer nativo. Não é login multiusuário nem barreira contra outro processo do mesmo usuário do SO.

Todas as outras rotas exigem `X-Orchestrator-CSRF` válido ou `Authorization: Bearer` válido. Comparação é constante, entradas não ASCII/duplicadas são rejeitadas; Authorization inválida não degrada para CSRF válido. Escritas CSRF exigem Origin autorizado, e escritas em ambos os modos exigem JSON. Bearer válido permite cliente nativo sem Origin, sem ignorar origem inválida quando presente. Tokens não são aceitos via query/cookie e não são registrados em SQLite/eventos.

CSRF_TOKEN e API_TOKEN são valores aleatórios independentes por processo; app.state.api_token pode ser fornecido em memória pela integração nativa confiável, sem persistência ou variável de ambiente nova. Integração supervisor/Tauri fica em DESK-002/004. Usar um processo de API nesta etapa; não compartilhar/rotacionar tokens entre workers HTTP independentes. A rota /settings agora exige autenticação antes de mostrar a configuração permitida, inclusive caminho do banco.

O frontend web usa sessionToken por operação, sem localStorage/sessionStorage ou cache de credenciais; leituras passam o token e signal de cancelamento, escritas obtêm token fresco e não são repetidas automaticamente em erro. Um reinício entre bootstrap e operação pode resultar em 403; a próxima operação faz novo bootstrap, sem replay oculto. API clients existentes devem fazer o mesmo handshake e manter Origin autorizado nas escritas CSRF. Contratos JSON e digest de execução permanecem compatíveis.

Validação: matriz Host/origem/peer e token em todas as rotas, bearer separado do bootstrap, rotação, corpo e headers; regressões existentes autenticadas; vitest e E2E em API/worker/Vite temporários com todas as chamadas de agente mockadas. SEC-002/003/004/006 permanecem tarefas separadas; esta entrega não muda ambiente/permissões de agentes ou Git.

### 6.3 Subprocessos
- `safe_env(adapter)` = `{PATH, HOME, USER, LANG, LC_*, TERM, TMPDIR, XDG_*}` + variáveis declaradas no manifesto do adapter (ex.: config do CLI). Chaves de API só para o adapter que as exige, lidas do keyring.
- Git endurecido também nos comandos `git` executados por `core.run_command` (`worktree add`, `diff`, `status`): `-c core.hooksPath=/dev/null`, `-c core.fsmonitor=false`, `GIT_CONFIG_NOSYSTEM=1`, como já faz `projects.git`. A hipótese foi confirmada com controle positivo no Git 2.43.0; SEC-006 agora bloqueia o hook no prepare. Ver implementação e limites abaixo.
- Timeouts por grupo de processos (já em parte no worker).

### Implementação de SEC-002 (2026-11-17)

`policy/env.py` seleciona nomes exatos de variáveis, sem glob de LC_*/XDG_*. A base preserva PATH, HOME/USER/LOGNAME, idioma/locales conhecidos, terminal/shell, temporários, VIRTUAL_ENV, diretórios XDG conhecidos e caminhos de certificados TLS. Não inclui variáveis arbitrárias do worker, PYTHONPATH/PYTHONHOME ou chaves de API. O controle é por nome; autorizar um nome também autoriza seu conteúdo, portanto valores sensíveis não devem ser disfarçados em variáveis permitidas. Arquivos acessíveis via HOME continuam acessíveis ao mesmo usuário: isso não é isolamento do SO.

Escopos separados:
- `runner`: base, ORCH_DB/ORCH_ALLOWED_ROOTS/ORCH_ALLOWED_TEST_COMMANDS, configuração canônica da allowlist e entradas explicitamente necessárias aos escopos descendentes; Worker adiciona worker_id e marcador de despacho gerados.
- Adapter canônico (`claude_code`, `codex_cli`, `antigravity` ou plugin): base, nomes declarados no CapabilityManifest.environment_variables e extensões autorizadas só para esse adapter. Claude declara CLAUDE_CONFIG_DIR e Codex CODEX_HOME; agy usa HOME/XDG, sem inventar nomes não verificados.
- `tests` e `git`: base e extensões apenas do respectivo escopo. Não recebem config dirs dos outros adapters, banco ou worker_id.

GIT_CONFIG_NOSYSTEM=1 e GIT_CONFIG_GLOBAL=/dev/null são gerados, nunca herdados livremente. ORCH_DISPATCH_TOKEN é uma exceção de supervisão: propaga-se do ambiente confiável do runner para identificar descendentes quando o líder morreu; não é credencial de API e não pode ser substituído por InvocationRequest.env. Removê-lo quebraria a recuperação segura de grupos órfãos. SEC-002 não altera argv/permissões; hooks e configuração local de Git são tratados pela implementação SEC-006 abaixo.

Extensões são configuração confiável do processo, por exemplo `ORCH_ENV_ALLOWLIST='{"tests":["TEST_FIXTURE_DIR"],"claude_code":["HTTPS_PROXY"]}'`. Usar IDs canônicos, nomes individuais, sem valores no JSON; o valor da variável selecionada vem do processo no spawn. Proxy só deve ser autorizado ao processo que precisa dele. Declarações recusam glob, nomes de credenciais como KEY/TOKEN/SECRET/PASSWORD/CREDENTIALS, controles ORCH_/GIT_, LD_/DYLD_ e PYTHONPATH/PYTHONHOME/PYTHONSTARTUP/PYTHONINSPECT; configuração inválida falha antes do subprocesso, com mensagem estática sem conteúdo. Chaves de provedores via API ficam no keyring/ModelProvider de SEC-005/PROV-001, não nesta configuração.

Nomes internos runner/tests/git são reservados: não podem ser IDs de adapters/entry points nem entrar no contexto de adapter. CommandRuntime confere provider==manifest.adapter no construtor e antes da chamada. Runtime filtra mesmo com runner injetado; core.run_command revalida a política na fronteira de subprocess.run e resolve o executável pelo PATH efetivo. InvocationRequest.env explícito é um mapa substituto filtrado, sem mesclar o restante do ambiente; controles Git/supervisão seguros são regenerados. Helpers projects.git/repository_lock.identity também usam a política.

Quando não vazia, a política canônica de **nomes** é salva em managed_runs.config.environment_allowlist e coberta pelo digest de confirmação; a forma/digest padrão antigos continuam iguais quando a extensão está ausente. Valores nunca entram nessa chave. Worker.environment e execution_runner reaplicam o snapshot, ignorando alterações posteriores do mapa do worker; valores permitidos são resolvidos no processo que inicia o filho, não persistidos. Snapshots antigos sem o campo usam extensões vazias, sem herdar novas concessões; snapshots de tipo inválido não viram defaults silenciosamente. A política de execução legada CLI vem do ambiente do próprio processo, enquanto snapshots gerenciados são congelados.

Evidências: /proc/environ de agente Python fake e runner real, workflow com Worker.spawn/handshake/cleanup de produção e agentes mockados, segregação por escopo, valores ausentes do banco, digest/stale confirmation, e recuperação real do descendente filtrado após matar somente seu runner de teste. Nenhum CLI real/quota. O harness E2E reutiliza Worker.environment em vez de herdar os.environ integralmente.

### Implementação de SEC-006 (2026-11-18)

`policy/git.py` centraliza o Git direto de core.run_command, projects.git e repository_lock.identity. As chamadas recebem --no-pager e opções -c fixas para desabilitar hooks, fsmonitor, assinatura, recursão/summary de submódulos, manutenção automática e checkout paralelo; ambiente já filtrado por SEC-002 mantém config global/sistema desligada. FD de lock/diretório continua herdado, e consulta de configuração + comando usam o mesmo orçamento de timeout.

O wrapper aceita somente as formas completas e não interativas usadas pelo orquestrador: init sem templates; add com separador --; commit com mensagem -m; status simples/porcelain/short; rev-parse para identidade/HEAD; worktree add --no-checkout -b agent/run-<12hex> <target absoluto> HEAD; reset --hard HEAD; diff da HEAD/árvore com opções inertes. Aliases, opções globais de caller, abreviações, editores e conversores explícitos não são aceitos. Status/diff ignoram submódulos; diff força --no-ext-diff/--no-textconv. Não é uma API genérica de Git, não habilita merge/push/deploy.

Antes de operações em repositórios existentes, uma consulta read-only `git config --includes --null --get-regexp` verifica clean/smudge/process da configuração efetiva (incluindo includes/branch). Comandos de filtro não vazios e configuração não verificável são recusados antes de tocar arquivos/index. Valores/stderr dessa consulta não são expostos em mensagens de erro. **Compatibilidade:** repositórios com filtros executáveis locais, inclusive LFS configurado localmente, não são suportados por esse caminho automático; não existe override silencioso. A consulta não remove/edita config do repositório.

prepare registra uma worktree com --no-checkout, depois valida a configuração efetiva nessa nova branch e só então executa reset --hard HEAD para preenchê-la. Isso impede que includeIf.onbranch habilite filtro no momento do checkout. Se a configuração só se tornar insegura após registro da branch, a worktree vazia e a branch são preservadas para inspeção manual; não há remoção/limpeza automática ou execução de agentes. O repositório de origem e seu config permanecem preservados.

Controles positivos em repositórios temporários comprovaram post-checkout/fsmonitor/diff/textconv e filtros executáveis no Git 2.43.0; regressões verificam ausência de sentinelas, conteúdo/branch/worktree/locks preservados, includes condicionais e bypasses por --check/negações de opções. A proteção vale para Git chamado diretamente pelo orquestrador: código gerado/testes ou ferramentas nativas de agentes que executem Git por conta própria não passam por esse wrapper. Não há isolamento contra mutação concorrente maliciosa de config pelo mesmo usuário do SO; SEC-008 permanece separada.

Referências primárias: [hooks/post-checkout](https://git-scm.com/docs/githooks.html), [worktree sem checkout](https://git-scm.com/docs/git-worktree), [diff e conversores](https://git-scm.com/docs/git-diff), [atributos/filtros](https://git-scm.com/docs/gitattributes.html), [config/includes](https://git-scm.com/docs/git-config). Evidência local nos testes prevalece para a versão instalada.

### 6.4 Prompt injection
Envelopar conteúdo de repositório/diff/saída de agente em blocos delimitados com aviso; schema estrito nas respostas; reviewer nunca recebe instrução para executar comandos; nenhum campo de saída de agente vira argumento de comando (como hoje com `"No shell commands in JSON"` — manter e reforçar por validação).

### 6.5 Rede
Fase futura: executar comando de testes e runtimes em namespace sem rede (bubblewrap/`unshare`) quando disponível; Codex `workspace-write` normalmente bloqueia rede no sandbox (hipótese — verificar).

### 6.6 Auditoria
Estender `platform_audit` com: `workflow.created`, `provider.configured`, `credential.set/removed` (sem valor), `approval.decided`, `budget.override`, `run.resumed`.

## 7. Componentes afetados
`local_security.py`, `api.py`, `core.py` (`run_command`, `prepare`), `worker.py` (`spawn`), adapters, `projects.py`.

## 8. Arquivos previstos
`orchestrator/policy/{roles,env}.py`, `orchestrator/local_security.py` (alterado), `tests/security/test_{routes_protected,env_allowlist,role_argv,secret_leak,git_hooks}.py`.

## 9. Dependências
`V2-CORE-001` para SEC-004; `V2-DESK-004` depende de SEC-001.

## 10. Riscos
| Risco | Mitigação |
|---|---|
| CLIs precisam de variáveis não previstas | Allowlist extensível por manifesto + mensagem de erro |
| `plan` mode do Claude impede saída esperada do planner | Validar com fake e com 1 execução real autorizada |
| Hooks do repositório alvo executam em `git worktree add` | Confirmado e mitigado em SEC-006, com controle positivo e regressão do prepare |
| Mesmo usuário do SO = sem fronteira real | Documentar; isolamento de SO em fase futura (SEC-008) |

## 11. Critérios de aceite verificáveis
- CA1 `GET /runs` com `Host: evil.example` → 403 (teste).
- CA2 Variável `SENTINEL_SECRET` no ambiente do worker não aparece em `/proc/<pid>/environ` do agente fake (teste).
- CA3 Para cada papel/adapter, teste de `argv` confirma a flag de permissão esperada.
- CA4 Repositório alvo com hook `post-checkout` malicioso não o executa em `prepare` (teste).
- CA5 Nenhum segredo-sentinela aparece no SQLite após execução mockada com OpenRouter.

## 12. Testes necessários
Os de CA1–CA5 + regressão dos testes de segurança existentes.

## 13. Complexidade
SEC-001: S · SEC-002: S · SEC-003: S · SEC-004: M · SEC-005: M · SEC-006: S · SEC-007: S · SEC-008: XL.

## 14. Prioridade
P0: SEC-001, 002, 003, 006 · P1: SEC-004, 005, 007 · P3: SEC-008.

## 15. Perfil recomendado
Engenheiro de segurança/back-end; revisão humana obrigatória para SEC-003 e SEC-004 (mudam comportamento).
