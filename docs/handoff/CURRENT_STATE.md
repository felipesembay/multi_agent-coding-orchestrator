# Estado atual

Atualizado: 2026-11-17 · Por: Codex (V2-CORE-004)

## Repositório
- Branch: `dev`, criada pelo operador. Baseline: `f8e6949`; extração dos runtimes: `87a034f` (CORE-001); metadados: `56e44d2` (CORE-002); registry: `6737c2f` (CORE-003).
- Operador autorizou implementação e commits em `dev` após testes; sem merge/push/deploy/main/master.
- WIP anterior (tema, exclusão lógica, migração v3) preservado, revisado e incluído no baseline.
- CORE-004 testada e aprovada por `review_core004`, registrada nesta sessão no commit `V2-CORE-004: freeze role bindings and preserve legacy snapshots`; consulte `git log -1` para hash final. Nenhum WIP externo identificado.

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
- Flags/prompts/defaults inalterados. Claude continua acceptEdits e Codex read-only; segurança permanece nas tarefas SEC. Usage_records ficam em OBS-001; segurança de roles e workflows segue nas tarefas próprias.

## Testes desta sessão
| Comando | Resultado |
|---|---|
| `ORCH_DB=<tmp> python -m pytest -q -p no:cacheprovider` | Baseline 154 passed; final 179 passed, 1 warning LangGraph |
| `python -m pytest -q -p no:cacheprovider tests/providers tests/test_planner_fallback.py` | 69 focados (bindings/caracterização/metadata/fallback), repetidos pela revisão independente |
| `npm --prefix frontend test` | 33 passed (6 arquivos), no baseline; frontend não alterado nesta tarefa |
| `npm --prefix frontend run build` / `run lint` | sucesso |
| `python scripts/check_docs.py` / `git diff --check` | sucesso |
| E2E / CLIs de agentes reais | não executados |

Suíte completa Python executada fora do sandbox com autorização automática para sockets locais e subprocessos mockados. Sem quota real.

## Próximas etapas e pendências
- Próxima recomendada: SEC-001 proteger todas as rotas; alternativas SEC-002/006, uma por vez. Núcleo CORE-001..004 concluído.
- F0-002 continua blocked: Q2–Q12 e revisão humana dos ADRs pendentes. Não bloqueia SEC-001/002/006; SEC-003 exige validação real autorizada. Não assumir decisões nem iniciar spikes reais sem autorização.

## Ambiente observado
Python 3.9.7 (.venv), LangGraph 0.6.11, Node 22.18.0. Sem dependências novas; Pydantic usa Optional compatível com Python 3.9. Versões de CLIs seguem apenas a auditoria anterior, sem nova verificação ou execução.
