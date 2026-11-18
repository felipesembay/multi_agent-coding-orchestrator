# Estado atual

Atualizado: 2026-11-17 · Por: Codex (V2-CORE-003)

## Repositório
- Branch: `dev`, criada pelo operador. Baseline: `f8e6949`; extração dos runtimes: `87a034f` (CORE-001); metadados: `56e44d2` (CORE-002).
- Operador autorizou implementação e commits em `dev` após testes; sem merge/push/deploy/main/master.
- WIP anterior (tema, exclusão lógica, migração v3) preservado, revisado e incluído no baseline.
- CORE-003 testada e aprovada por `review_core003`, registrada nesta sessão no commit `V2-CORE-003: add opt-in provider registry and catalog`; consulte `git log -1` para hash final. Nenhum WIP externo identificado.

## Implementado
- v1 preservada, conforme [CURRENT_STATE_AUDIT.md](../architecture/CURRENT_STATE_AUDIT.md), mais tema/exclusão/migração v3 do baseline.
- **V2-DOC-001 done:** verificador de links/âncoras/referências, IDs do backlog e data do handoff, sem rede.
- **V2-F0-001 done:** baseline `f8e6949` testado/revisado em dev.
- **V2-CORE-001 done:** adapters Claude/Codex/Antigravity com runner injetado e fachadas compatíveis.
- **V2-CORE-002 done:** `UsageReport`, `InvocationResult` completo, `AgentCall`, duração monotônica, códigos de erro normalizados e um evento `agent_call` por tentativa real de runtime associada ao run (inclusive falha/fallback).
- Eventos incluem provider, papel, modelo solicitado (ou null para CLI default desconhecido), duração, call_id, uso e código de erro; excluem prompt/output/ambiente/cwd/mensagens de erro e usage.raw.
- Uso sempre `unavailable`, tokens/custo nulos, billing `unknown`. Sem parsers não há modelo reportado/session_id/structured. Exceções e fallback legados preservados. Falha no observer durante erro preserva exceção original e emite warning sem conteúdo; após sucesso, falha de persistência é propagada.
- Contexto por run/papel resetado em finally; implementer recebe state e reviewer usa contexto. Fachadas continuam retornando texto, com assinaturas e patch points preservados. Standalone sem run retorna metadados sem evento órfão; mock integral da fachada não gera chamada artificial.
- Dashboard conserva etapa/status/tentativas/resultados ao receber agent_call; last_event continua sendo atividade. Frontend preserva o payload como evento adicional.
- **V2-CORE-003 done:** registry, Capability/CapabilityManifest/ProbeResult, manifestos nos três runtimes, probe passivo e GET /providers sob proteção Host/peer/Origin local. Não usa subprocessos/keyring no probe; presença de executável não atesta autenticação/quota; versão e credenciais nulas.
- Registry permite runner/observer nos built-ins e factories de plugins sem argumentos, só com nomes explicitamente habilitados. Sem opt-in nem descobre plugins; duplicatas/colisões rejeitadas e falhas isoladas por códigos estáticos sem caminhos/mensagens brutas. Listagem valida/copía manifest/probe; plugins de modelos e runtimes separados por kind.
- provider_configs não existe até WF-002; API padrão só built-ins, HTTP não habilita plugins. Built-ins verified=false, billing unknown, usage_source none; capacidades atuais, sem declarar telemetria/saída estruturada/papéis futuros.
- Flags/prompts/seleção inalterados. Claude continua acceptEdits e Codex read-only; segurança permanece nas tarefas SEC. Bindings ficam em CORE-004 e usage_records em OBS-001.

## Testes desta sessão
| Comando | Resultado |
|---|---|
| `ORCH_DB=<tmp> python -m pytest -q -p no:cacheprovider` | Baseline 130 passed; final 154 passed, 1 warning LangGraph |
| `python -m pytest -q -p no:cacheprovider tests/providers tests/test_planner_fallback.py` | Incluídos no conjunto completo; revisão independente repetiu 52 de registry/contratos/caracterização/API |
| `npm --prefix frontend test` | 33 passed (6 arquivos), no baseline; frontend não alterado nesta tarefa |
| `npm --prefix frontend run build` / `run lint` | sucesso |
| `python scripts/check_docs.py` / `git diff --check` | sucesso |
| E2E / CLIs de agentes reais | não executados |

Suíte completa Python executada fora do sandbox com autorização automática para sockets locais e subprocessos mockados. Sem quota real.

## Próximas etapas e pendências
- Próxima tarefa: CORE-004 bindings por papel/runtime/modelo e configuração legada, preservando snapshot/digest e defaults.
- F0-002 continua blocked: Q2–Q12 e revisão humana dos ADRs pendentes. Não bloqueia CORE-004. Não assumir decisões nem iniciar spikes reais sem autorização.

## Ambiente observado
Python 3.9.7 (.venv), LangGraph 0.6.11, Node 22.18.0. Sem dependências novas; Pydantic usa Optional compatível com Python 3.9. Versões de CLIs seguem apenas a auditoria anterior, sem nova verificação ou execução.
