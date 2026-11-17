# ADR-0006 — Contabilidade de uso honesta

- **Status:** proposto · **Data:** 2026-11-17 · **Tarefas:** V2-OBS-*

## Contexto
Nenhum token é capturado hoje. CLIs com assinatura (Claude Code, Codex, Antigravity) podem reportar custo "equivalente" que não é cobrado; APIs cobram por token; alguns provedores não reportam nada.

## Decisão
Cada chamada gera um `usage_record` com:
- `token_source`: `provider_reported` | `cli_reported` | `estimated` | `unavailable`;
- `billing_mode`: `api_metered` | `subscription_quota` | `local` | `unknown`;
- `reported_cost_usd` (o que o provedor/CLI informou) separado de `estimated_cost_usd` (catálogo × tokens).
A UI nunca soma categorias diferentes sem rótulo; custo de assinatura é exibido como "equivalente estimado, não cobrado".
Catálogo de preços versionado com origem e data; preço nunca embutido em código.

## Alternativas rejeitadas
| Alternativa | Motivo |
|---|---|
| Um único campo `cost` | Mistura estimativa com cobrança |
| Estimar tudo com tokenizer local | Impreciso entre modelos; só como último recurso e rotulado |

## Consequências
Parsers de telemetria por adapter dependem do spike V2-F0-003.
