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
| Ambiente dos agentes | ✗ herda `os.environ` completo (menos `GIT_*`) |
| Git endurecido | ✓ em `projects.git` e `repository_lock.identity` (hooks off, config global off); **não** em `core.run_command` (worktree add, diff, status) |
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
- Git endurecido também nos comandos `git` executados por `core.run_command` (`worktree add`, `diff`, `status`): `-c core.hooksPath=/dev/null`, `-c core.fsmonitor=false`, `GIT_CONFIG_NOSYSTEM=1`, como já faz `projects.git`. [HIPÓTESE a confirmar por teste] o hook `post-checkout` do repositório alvo é executado por `git worktree add`, e hoje `prepare()` não o desabilita. → `V2-SEC-006`.
- Timeouts por grupo de processos (já em parte no worker).

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
| Hooks do repositório alvo executam em `git worktree add` | Verificar e desabilitar hooks no `prepare` (SEC-006) |
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
