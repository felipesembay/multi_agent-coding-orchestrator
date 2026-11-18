# TASK 02 — Arquitetura extensível de provedores de IA

## 1. Identificador e título
`V2-T02` — Sistema de provedores (AgentRuntime + ModelProvider). Subtarefas: `V2-CORE-001..004`, `V2-PROV-001..003`, `V2-SEC-004/005`.

## 2. Objetivo
Adicionar provedores e modelos sem alterar o núcleo; declarar capacidades; distinguir modelos via API de agentes de programação via CLI ([ADR-0004](../architecture/DECISIONS/ADR-0004-model-provider-vs-agent-runtime.md)).

## 3. Estado atual comprovado
Ver [auditoria §4](../architecture/CURRENT_STATE_AUDIT.md#4-adapters-de-agentes): três funções em `core.py`, seleção por env, reviewer fixo Codex, fallback ad hoc, nenhum metadado de uso, nenhum cadastro de modelos ou credenciais.

## 4. Requisitos funcionais
- RF1 Registry lista adapters disponíveis (built-in e entry points) com manifesto e status de disponibilidade (executável encontrado, versão, credencial presente — **sem** afirmar quota).
- RF2 Cada adapter declara capacidades (tabela §6.2).
- RF3 Usuário cadastra `provider_configs` (ex.: "OpenRouter pessoal", "Claude Code local") e escolhe modelo por identificador.
- RF4 Invocação uniforme retorna `InvocationResult` com texto, JSON estruturado opcional, `UsageReport`, duração, código de erro normalizado.
- RF5 Erros normalizados: `rate_limited`, `quota_exhausted`, `auth_failed`, `timeout`, `invalid_output`, `permission_denied`, `unavailable`, `unknown` — base para fallbacks.
- RF6 OpenRouter: cadastro de API key (keyring), listagem de modelos, metadados de contexto/preço, parâmetros suportados, rate limits, monitoramento de uso.
- RF7 Permissões por papel convertidas em flags de cada CLI.

## 5. Requisitos não funcionais
- RNF1 Nenhum adapter grava segredo em evento/log; teste com segredo-sentinela.
- RNF2 Adicionar provider = novo pacote/módulo + entry point, zero mudança em `core`/`workflows`.
- RNF3 Testes sem rede e sem CLIs reais (fakes de subprocesso e HTTP).
- RNF4 Timeouts e cancelamento por processo (grupo) respeitados.

## 6. Arquitetura proposta

### 6.1 Contratos (`orchestrator/providers/base.py`)
```python
class Capability(str, Enum):
    TEXT = 'text'; STRUCTURED_OUTPUT = 'structured_output'; PLANNING = 'planning'
    CODE_EDIT = 'code_edit'; CODE_EXEC = 'code_exec'; TOOL_CALLING = 'tool_calling'
    REVIEW = 'review'; STREAMING = 'streaming'; REPO_CONTEXT = 'repo_context'
    USAGE_METRICS = 'usage_metrics'; COST_REPORT = 'cost_report'; SESSION_RESUME = 'session_resume'

class CapabilityManifest(BaseModel):
    adapter: str                      # 'claude_code', 'codex_cli', 'antigravity', 'openrouter'
    kind: Literal['agent_runtime', 'model_provider']
    capabilities: set[Capability]
    permission_modes: list[str]       # ex.: ['read_only', 'workspace_write']
    auth_modes: list[Literal['cli_managed', 'api_key', 'oauth', 'none']]
    billing_mode: Literal['api_metered', 'subscription_quota', 'local', 'unknown']
    usage_source: Literal['provider_reported', 'cli_reported', 'none']
    verified: bool                    # True só após teste/spike documentado

class InvocationRequest(BaseModel):
    role: str; prompt: str; cwd: Path | None; model: str | None
    permission: Literal['read_only', 'workspace_write']
    output_schema: dict | None; timeout_s: int; env: dict[str, str]

class UsageReport(BaseModel):
    input_tokens: int | None; output_tokens: int | None
    cache_read_tokens: int | None; cache_write_tokens: int | None
    reasoning_tokens: int | None; reported_cost_usd: float | None
    source: Literal['provider_reported', 'cli_reported', 'estimated', 'unavailable']
    raw: dict                          # redigido

class InvocationResult(BaseModel):
    text: str; structured: dict | None; usage: UsageReport
    duration_ms: int; model_reported: str | None; session_id: str | None

class AgentRuntime(Protocol):
    manifest: CapabilityManifest
    def probe(self) -> ProbeResult: ...
    def invoke(self, req: InvocationRequest) -> InvocationResult: ...

class ModelProvider(Protocol):
    manifest: CapabilityManifest
    def list_models(self) -> list[ModelInfo]: ...
    def generate(self, req: InvocationRequest, context: list[ContextItem]) -> InvocationResult: ...
```

### Implementação incremental de CORE-002 (2026-11-17)

`InvocationResult` inclui os campos descritos em §6.1 e `error_code` opcional. O `CommandRuntime` mede duração com relógio monotônico e informa um observer opcional por tentativa. Erros são classificados conservadoramente para metadados; a exceção original continua sendo propagada, preservando o fallback legado. Falha ao persistir metadados de uma chamada já falha gera warning sem conteúdo, sem ocultar o erro original; persistência malsucedida após sucesso é propagada.

O core associa as invocações ao run/papel por contexto local, sem mudar assinaturas das fachadas. O evento `agent_call` inclui `call_id`, `provider`, `role`, `model` (solicitado; null = default desconhecido), `model_reported`, `session_id`, `duration_ms`, `usage`, `billing_mode` e `error_code`. Não contém prompt, saída, ambiente, cwd, mensagem bruta de erro ou `usage.raw`. Uma tentativa de fallback gera outro call_id/evento. Chamadas independentes sem run só retornam metadados, sem criar runs órfãos.

Até parsers verificados, todos os built-ins devolvem uso `unavailable` com contagens/custo nulos; modelo reportado, session e saída estruturada ficam nulos. Campo indisponível nunca vira zero. Billing permanece `unknown`, pois a autenticação CLI não foi verificada. O dashboard conserva etapa/status/resultados ao receber metadados; last_event continua registrando a atividade. Persistência de `usage_records` fica em OBS-001; manifests/probe/registry em CORE-003.

### 6.2 Manifestos iniciais (a confirmar)

| Adapter | Kind | Capacidades previstas | Permissões → flags | Uso | Verificado |
|---|---|---|---|---|---|
| `claude_code` | agent_runtime | planning, code_edit, review, structured_output, usage_metrics, cost_report, streaming | read_only → `--permission-mode plan`; workspace_write → `--permission-mode acceptEdits` + `--disallowedTools Bash` | `cli_reported` (hipótese: JSON `usage`, `total_cost_usd`) | não |
| `codex_cli` | agent_runtime | planning, code_edit, code_exec, review, structured_output, usage_metrics | read_only → `--sandbox read-only`; workspace_write → `--sandbox workspace-write` | `cli_reported` (hipótese: JSONL `--json`) | parcial (read-only em uso) |
| `antigravity` | agent_runtime | planning, code_edit, review, structured_output | read_only → `--mode plan`; workspace_write → `--mode accept-edits` (+ `--sandbox`?) | desconhecido | parcial (`--output-format json` em uso) |
| `openrouter` | model_provider | text, structured_output (por modelo), tool_calling (por modelo), streaming, usage_metrics, cost_report | só read_only | `provider_reported` (campo `usage` da resposta; hipótese a verificar) | não |
| `ollama` (F6) | model_provider | text, streaming | só read_only | `provider_reported` local, `billing_mode=local` | não |
| `anthropic_api`, `openai_api`, `gemini_api` (futuro) | model_provider | text, structured_output, tool_calling | só read_only | `provider_reported` | não |

**Regra**: `verified=false` → a UI mostra "não verificado" e o validador emite aviso (não bloqueio) — exceto para `code_edit`, que exige `verified=true`.

### 6.3 Registry
`orchestrator/providers/registry.py` carrega built-ins e `importlib.metadata.entry_points(group='orchestrator.providers')`. Adapters de terceiros só são carregados se habilitados em `provider_configs` (opt-in explícito).

**Implementado em CORE-003 (2026-11-17):** `Capability`, `CapabilityManifest` e `ProbeResult` em base.py; cada runtime publica seu manifesto e um `probe()` passivo que só usa `shutil.which`. O endpoint local `GET /providers` retorna uma lista de `{adapter, source, manifest, probe}`; `probe.executable_found` informa somente presença do executável, nunca prontidão/autenticação/quota. Versão e credenciais são nulas nos built-ins, pois não são verificadas. Nenhum comando `--version`, geração ou acesso ao keyring é disparado ao listar. A rota usa a proteção Host/peer/Origin local já existente e respostas sem cache.

Os manifestos implementados descrevem a superfície **atual**, não todas as capacidades previstas em §6.2: Claude (text/planning/code_edit/repo_context; workspace_write), Codex (text/review/repo_context; read_only), Antigravity (text/planning/code_edit/repo_context; read_only/workspace_write). Todos têm `verified=false`, `billing_mode=unknown`, `usage_source=none` e autenticação declarada `cli_managed`; isso não atesta sessão válida. Telemetria, streaming, saída estruturada validada e novos papéis não são anunciados antecipadamente. A futura validação de workflow continuará exigindo verificação para code_edit; a execução legada permanece inalterada nesta tarefa.

`ProviderRegistry(enabled_entry_points=(), runner=..., observer=...)` registra os built-ins, permite lookup por `get(adapter)` e devolve cópias de manifestos nas listagens. O runner padrão recusa execução; callers que desejam invocar built-ins devem injetar runner/observer. Sem opt-in não há sequer descoberta de entry points. Com opt-in, apenas os nomes habilitados do grupo `orchestrator.providers` são carregados; cada entry point exporta uma factory sem argumentos que retorna um objeto com `manifest`, `probe()` e `invoke()` (agent_runtime) ou `generate()`/`list_models()` (model_provider). A listagem não chama geração/list_models. Plugins são código confiável instalado, não código isolado pelo registry.

Há suporte aos formatos `entry_points().select(group=...)` e dict legado do Python 3.9. Nomes duplicados e colisões com built-ins são rejeitados antes do carregamento; falhas de descoberta/importação/contrato/probe são isoladas e expostas apenas por códigos estáticos, sem mensagens brutas, caminhos de executáveis, ambiente ou segredos. `manifest` é nulo se o plugin habilitado falhar ao carregar ou validar; `probe.error_code` identifica a falha. Um probe inválido não remove o manifesto válido.

A tabela `provider_configs` só chega em WF-002: até essa integração, `get_provider_registry()` da API não habilita terceiros. A configuração de processo pode fornecer um registry explicitamente habilitado pela dependência `get_provider_registry` (usado com fake nos testes); parâmetros HTTP não autorizam plugins. A integração futura deve passar somente adapters de configurações explicitamente enabled, sem carregar instalados por padrão. Nenhuma migração de banco foi antecipada.


### 6.4 Execução segura
- `AgentRuntime` recebe `cwd` = worktree e `permission` derivada da matriz do papel ([SECURITY_GOVERNANCE.md](SECURITY_GOVERNANCE.md) §6).
- `ModelProvider` nunca recebe caminho; o orquestrador monta contexto (diff limitado, arquivos selecionados, plano) com limites de tamanho e marcação de conteúdo não confiável.
- Saída estruturada validada por JSON Schema (usar `--json-schema`/`--output-schema` quando o CLI suportar; validar sempre no orquestrador).

### 6.5 OpenRouter
| Item | Plano |
|---|---|
| API key | Tela Providers → keyring (`service=multi-agent-orchestrator`, `username=openrouter:<config_id>`) |
| Modelos | `GET /api/v1/models` com cache em SQLite (TTL configurável); identificador `vendor/model` |
| Metadados | `context_length`, preços por token, parâmetros suportados → `price_entries` com `source=openrouter_api` |
| Parâmetros | Formulário gerado a partir dos parâmetros suportados declarados; desconhecidos não enviados |
| Rate limit | `429` → `rate_limited` com `Retry-After`; backoff exponencial limitado; contabiliza tentativas |
| Erros | 401 `auth_failed`, 402 `quota_exhausted`, 5xx `unavailable`, JSON inválido `invalid_output` |
| Uso | Gravar `usage` reportado; consulta de saldo/limite da chave como verificação opcional |
Endpoints e campos exatos devem ser confirmados na documentação oficial durante `V2-PROV-001` (não verificados nesta sessão).

## 7. Componentes afetados
`core.py`, `execution_manager.py`, `execution_runner.py`, `api.py`, frontend Settings → Providers.

## 8. Arquivos previstos
`orchestrator/providers/{__init__,base,registry,errors,context}.py`, `orchestrator/providers/runtimes/{claude_code,codex_cli,antigravity}.py`, `orchestrator/providers/models/{openrouter,ollama}.py`, `orchestrator/secrets/store.py`, `tests/providers/test_*`, `frontend/src/features/Providers.tsx`.

## 9. Dependências
Spike `V2-F0-003` (telemetria). Lib `keyring` (V2-SEC-005). `httpx` (já presente) para OpenRouter.

## 10. Riscos
| Risco | Mitigação |
|---|---|
| Formatos de saída dos CLIs mudam entre versões | Registrar versão do CLI no `probe`; parsers tolerantes; testes com fixtures por versão |
| Codex `workspace-write` permite execução de comandos | Aceitação explícita (Q5); rede desabilitada se suportado; ledger |
| Planner Claude em `plan` muda comportamento | Tarefa separada `V2-SEC-003` com validação manual |
| Equivalência ilusória entre "modelo" e "agente" | Validador por capacidade; UI separa as duas listas |

## 11. Critérios de aceite verificáveis
- CA1 Testes de caracterização provam que `argv` gerado pelos novos adapters é **idêntico** ao atual para a configuração legada.
- CA2 `GET /providers` lista adapters com manifesto e `probe` sem expor ambiente ou segredos.
- CA3 Adapter fake registrado via entry point em teste aparece no registry sem alteração de `core`.
- CA4 OpenRouter: chamada mockada grava `usage_record` com `token_source=provider_reported`; chave não aparece em nenhum evento (grep do banco no teste).
- CA5 Workflow que coloca `openrouter` em papel com `code_edit` é rejeitado com mensagem clara.

## 12. Testes necessários
Unitários de adapters com `subprocess` fake; contrato comum (mesma suíte rodando sobre todos os adapters); parsers de telemetria com fixtures capturadas no spike; HTTP mock para OpenRouter (429, 401, 402, 5xx, JSON inválido); teste de não vazamento de segredo.

## 13. Complexidade
CORE-001/002: M · CORE-003: S · CORE-004: M · PROV-001: M · PROV-002: M · PROV-003: S. Premissa: sem rearquitetar o grafo nesta etapa.

## 14. Prioridade
P0 (CORE-001..004), P1 (PROV-001), P2 (PROV-002/003).

## 15. Perfil recomendado
Backend Python sênior com experiência em subprocessos (Codex ou Claude). Revisão por agente diferente do implementador.
