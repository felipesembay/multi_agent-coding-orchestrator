# Multi-Agent Coding Orchestrator

Local multi-agent coding orchestrator powered by LangGraph, Claude Code, Antigravity CLI and Codex CLI. Claude handles planning, Antigravity handles implementation, and Codex performs independent code review. Includes automated testing, SQLite auditing and Claude-to-Antigravity fallback.

## Instalação

Requirements: Python 3.9+ (tested locally), Git, and authenticated `claude`, `agy`, and `codex` CLIs available in PATH. Compatibility with future CLI versions is not guaranteed.

```bash
cd multi-agent-orchestrator
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Teste real em um repositório de exemplo

```bash
mkdir -p ~/agent-demo && cd ~/agent-demo
git init
git config user.name "Local Agent"
git config user.email "local@example.invalid"
echo '# Demo' > README.md
git add README.md && git commit -m init
cd ~/multi-agent-orchestrator
source .venv/bin/activate
export ORCH_TEST_COMMAND='python -m pytest -q'
python -m orchestrator.cli run --repo ~/agent-demo --scope examples/SCOPE.md
```

Se o projeto alvo não possuir pytest, configure `ORCH_TEST_COMMAND` com o comando de testes adequado. Sem esse comando, QA não aprova tarefas. O orquestrador não instala dependências automaticamente. No primeiro teste, prefira um projeto descartável e pequeno.

Consultar eventos:

```bash
python -m orchestrator.cli events
uvicorn orchestrator.api:app --host 127.0.0.1 --port 8765
# http://127.0.0.1:8765/docs
```

## Segurança e limitações

- Claude Code pode pedir aprovação de ferramentas e escrita: **não usamos** `--dangerously-skip-permissions`. Execução 100% sem supervisão depende das permissões seguras configuradas por você.
- Codex executa com `--sandbox read-only`. Seu Linux apresentou aviso sobre namespaces do bubblewrap; confirme o funcionamento do sandbox antes de ampliar permissões.
- Não use este MVP com repositórios contendo segredos ou dados sensíveis. Os CLIs enviam conteúdo ao respectivo provedor segundo suas políticas.
- Os agentes recebem instruções para não executar ações destrutivas, mas prompts não são uma barreira de segurança. Execute com usuário sem privilégios, preferencialmente em contêiner/VM isolada e sem credenciais de produção.
- Worktrees e branches ficam no disco; o sistema não os remove automaticamente. Nunca compartilhe o endpoint FastAPI na rede: ele não possui autenticação.
- O CLI registra eventos SQLite, mas não implementa retomada após interrupção, aprovação de PR, dashboard web completo, execução paralela nem controle rígido de custos. São etapas posteriores.
- O Codex retorna revisões via texto; os testes automatizados configurados pelo operador são a condição mínima de aprovação. Ainda é necessária revisão humana.
- Antigravity CLI is integrated for implementation and planner fallback when Claude reaches a recognized usage limit.

## Configuração

| Variável | Padrão | Uso |
|---|---|---|
| `ORCH_DB` | `~/.local/state/multi-agent-orchestrator/events.db` | Banco de eventos |
| `ORCH_WORKTREES` | pasta irmã do repositório | Diretório das worktrees |
| `ORCH_TEST_COMMAND` | vazio | Comando de testes obrigatório para aprovação |
| `MAX_ATTEMPTS` | `3` | Tentativas por tarefa |
| `AGENT_TIMEOUT` | `900` | Timeout dos agentes (s) |
| `TEST_TIMEOUT` | `300` | Timeout dos testes (s) |

## Próximos incrementos

Checkpoint persistente LangGraph; validação de schema com Pydantic; allowlist de comandos; execução em contêiner sem rede; dashboard React; suporte a tarefas paralelas; aprovação humana no PR.

## Agent Configuration

```bash
export ORCH_PLANNER=claude
export ORCH_IMPLEMENTER=antigravity
export ORCH_PLANNER_MODEL=gemini-4-argon-medium
export ORCH_IMPLEMENTER_MODEL=gemini-4-argon-medium
export ORCH_TEST_COMMAND="python -m pytest -q"
```

## Validated Integration Test

A complete local run successfully executed the planning, implementation, testing, and review workflow.

- Final status: `ready_for_human_review`
- Implementation attempts: 1
- Generated calculator tests: 6 passed
- Independent code review: approved
- Orchestrator unit tests: 14 passed
- Process exit code: 0
