# ADR-0004 — ModelProvider (API) vs AgentRuntime (CLI)

- **Status:** proposto · **Data:** 2026-11-17 · **Tarefas:** V2-CORE-*, V2-PROV-*

## Contexto
Claude Code, Codex CLI e Antigravity são agentes completos: têm loop de ferramentas próprio, leem e editam arquivos, possuem sandbox/permissões e autenticação próprios. Um modelo via OpenRouter é apenas geração de texto/ferramentas sem acesso ao repositório. Tratá-los como equivalentes causaria workflows que "implementam" sem editar nada ou, pior, exigiriam dar ao orquestrador um executor de ferramentas inseguro.

## Decisão
Duas interfaces distintas em `orchestrator/providers/base.py`:

- `AgentRuntime` — executa uma tarefa num diretório de trabalho com política de permissões; retorna texto final, artefatos e uso.
- `ModelProvider` — gera texto/JSON a partir de mensagens; o orquestrador fornece todo o contexto (diff, arquivos, plano). Não toca o sistema de arquivos.

Ambas publicam um `CapabilityManifest`. Papéis declaram capacidades exigidas; o validador de workflow rejeita combinações incompatíveis. No MVP, `ModelProvider` só pode ocupar papéis **somente leitura** (planejamento, revisão, documentação proposta como texto). Um "tool runtime" do orquestrador que permita a um `ModelProvider` editar arquivos fica para fase futura com ADR próprio.

Registro: built-ins + entry points Python (`orchestrator.providers`), sem alterar o núcleo para adicionar um provider.

## Alternativas rejeitadas
| Alternativa | Motivo |
|---|---|
| Interface única `LLMProvider` | Esconde diferença crítica de segurança e capacidades |
| LangChain chat models como abstração | Cobre APIs, não CLIs; dependência grande |
| Plugins carregados de diretório arbitrário | Execução de código não confiável; entry points exigem instalação explícita |

## Consequências
OpenRouter entra como `ModelProvider` simples. Ollama idem. Futuro ACP (`agy acp`) pode virar transporte alternativo de `AgentRuntime` (hipótese, não verificado).
