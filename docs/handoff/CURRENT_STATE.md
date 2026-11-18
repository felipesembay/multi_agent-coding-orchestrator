# Estado atual

Atualizado: 2026-11-17 · Por: Codex (V2-SEC-002)

## Repositório
- Branch: `dev`, criada pelo operador. Baseline: `f8e6949`; extração dos runtimes: `87a034f` (CORE-001); metadados: `56e44d2` (CORE-002); registry: `6737c2f` (CORE-003).
- Operador autorizou implementação e commits testados em `dev`; sem merge/deploy/main/master. Push anterior autorizado explicitamente até `db12642` está em origin/dev; nenhum novo push inferido nesta sessão.
- WIP anterior (tema, exclusão lógica, migração v3) preservado, revisado e incluído no baseline.
- CORE-004 em `db12642`, já enviado a origin/dev por autorização específica. SEC-001 em `8d94e7d`. SEC-002 testada/revisada por `review_sec002`, registrada nesta sessão no commit `V2-SEC-002: isolate subprocess environments by scope`; consulte `git log -1` para hash final. Nenhum WIP externo identificado.

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
- **V2-CORE-004 done:** RoleBinding/AgentBindings tipados/imutáveis, fonte env legada separada, validação registry/capacidades/permissões e dispatch por binding. Reviewer configurável internamente via runtime registrado apropriado. Defaults Claude/Claude/Codex e fallback exato legados preservados.
- execute_scope congela bindings no State e evento started; resume CLI restaura quando presentes. Worker lê snapshot gerenciado sem env atual e passa bindings diretamente, sem reescrever env dos agentes. Sem migração; config padrão/digest antigos preservados. Config explícita interna inclui bindings e confere consistência com projeção plana.
- Snapshots antigos reproduzem truthiness do runner para modelos nulos/vazios; ambiente direto preserva strings vazias. Modelos agy nulos explícitos viram default determinístico. Modelos para adapters legados Claude/Codex que não encaminham escolha são rejeitados.
- Novos executores exigem verified=true; somente editores Claude/Antigravity e planner Claude nas combinações legadas preservam exceções necessárias. Reviewer/planners novos read_only; não habilita novas flags/papéis ou ModelProviders. Regras de workflow em WF-001 continuam separadas.
- Invocação medida compartilhada com plugins; retorno inválido gera invalid_output e erro estático sem expor payload/cadeia no traceback.
- **V2-SEC-001 done:** middleware global Host único/estrito, peer IP loopback, origem, token CSRF/bearer, limite real de corpo 150 kB e cabeçalhos de segurança em sucessos/rejeições, inclusive docs/rotas inexistentes.
- GET/HEAD /session é bootstrap local e /health liveness sem token; ambos mantêm Host/peer/origem. Todos os demais requests exigem CSRF ou bearer independente; inválido/não ASCII/duplicado negado. Bearer não exposto por session; override nativo apenas em app.state.api_token/memória, sem credenciais persistidas.
- Escritas CSRF exigem Origin autorizado; bearer nativo sem Origin é aceito mas não ignora origem inválida. JSON para escritas. Settings agora exige token. Sem CORS externo.
- Frontend busca token por operação, também leituras, sem cache/localStorage/sessionStorage/replay de escrita; signal propagado. Sessão nova após reinício obtida na próxima operação, sem repetir mutações silenciosamente. Clientes API/tests/e2e adaptados para autenticação real, não para bypass de proteção.
- **V2-SEC-002 done:** allowlist exata em policy/env.py para runner/adapter/tests/git. LC/XDG conhecidos explicitamente; sem herdar variáveis arbitrárias/API keys/PYTHONPATH. Manifesto declara config paths Claude/Codex; agy só HOME/XDG sem variáveis inventadas.
- ORCH_ENV_ALLOWLIST: extensões explícitas por escopo/nomes, sem glob, credenciais comuns, loaders/controles reservados. Nomes não vazios canônicos no snapshot/digest; valores só no processo, sem persistência nesse campo. Defaults/digest antigos preservados; runner aplica snapshot congelado e recusa tipos inválidos.
- Worker.environment filtra o runner e o harness E2E reutiliza essa função. Runtime filtra mesmo com runner injetado, core revalida e busca pelo PATH efetivo; Git helpers também filtrados, sem antecipar hooks de SEC-006.
- ORCH_DISPATCH_TOKEN confiável permanece nos descendentes para recuperação segura; env explícito não o substitui. Demais controles de DB/worker não passam aos agentes/testes. GIT_CONFIG_NOSYSTEM/GLOBAL seguros gerados. Identidade provider==manifest.adapter e IDs internos reservados evitam escalar escopos por colisão.
- Testes examinam /proc/environ de agente/runner Python fake, supervisor de produção com agentes mockados, isolamento de extensões, snapshot sem valores e cleanup real de descendente após morte do líder. Variáveis extras autorizam seu conteúdo; isso não isola arquivos/credenciais acessíveis pelo mesmo usuário do SO.
- Flags/prompts/defaults de agentes inalterados. Claude continua acceptEdits e Codex read-only; permissões por papel e hooks do Git permanecem nas outras tarefas SEC. Usage_records ficam em OBS-001; segurança de roles e workflows segue nas tarefas próprias.

## Testes desta sessão
| Comando | Resultado |
|---|---|
| `ORCH_DB=<tmp> python -m pytest -q -p no:cacheprovider` | Baseline 273 passed; final 301 passed, 1 warning LangGraph |
| Testes de ambiente/worker/contratos | 25 novos de ambiente + 3 de snapshot/supervisão; revisão independente repetiu 93 Python focados |
| `npm --prefix frontend test` | 38 passed (7 arquivos) no baseline; frontend inalterado |
| `npm --prefix frontend run build` / `run lint` | sucesso |
| `python scripts/check_docs.py` / `git diff --check` | sucesso |
| E2E QA temporário | 9 passed / 2 skipped (opt-ins de criação/exclusão em outras raízes); fluxo supervisionado mockado incluído |
| CLIs de agentes reais | não executados |

Suíte Python e E2E executadas fora do sandbox com autorização automática para sockets locais/processos. API/worker/Vite dedicados encerrados; banco e repositórios QA temporários, sem usar dados reais. Sem quota real.

## Próximas etapas e pendências
- Próxima recomendada: SEC-006 Git seguro; depois WF-001 ou outras tarefas liberadas. CORE-001..004 e SEC-001/002 concluídas.
- F0-002 continua blocked: Q2–Q12 e revisão humana dos ADRs pendentes. Não bloqueia SEC-006; SEC-003 exige validação real autorizada. Não assumir decisões nem iniciar spikes reais sem autorização.

## Ambiente observado
Python 3.9.7 (.venv), LangGraph 0.6.11, Node 22.18.0. Sem dependências novas; Pydantic usa Optional compatível com Python 3.9. Versões de CLIs seguem apenas a auditoria anterior, sem nova verificação ou execução.
