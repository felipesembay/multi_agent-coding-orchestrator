# Questões em aberto (decisão humana)

Responda editando a coluna **Decisão** com data. Agentes não devem assumir resposta para itens marcados como bloqueantes.

| ID | Questão | Contexto / recomendação | Bloqueia | Decisão |
|---|---|---|---|---|
| Q1 | Commitar o WIP atual (tema, exclusão lógica, migração v3) antes da v2? | Testes passam com o WIP. Recomendação: commitar em branch e mesclar após revisão | V2-F0-001 → tudo | 2026-11-17: operador autorizou novos commits em `dev`, após testes; preservar WIP e estabelecer baseline em `dev`, sem merge/push para main/master. |
| Q2 | Trocar o padrão para Claude → Codex → Antigravity já na F2? | Hoje é Claude/Claude/Codex. Recomendação: `default-v2` vira padrão na UI; CLI mantém `legacy-v1` até nova versão; nota de migração no README | WF-004 | — |
| Q3 | Atualizar Python 3.9 → 3.11 ou 3.12? | 3.9 está fora de suporte; libs de checkpoint/empacotamento podem exigir ≥3.10. Recomendação: 3.12 | F0-005, RES-002, DESK-003 | — |
| Q4 | Ao fechar o app com run ativo: interromper, perguntar ou continuar em background (tray)? | Recomendação: perguntar, com opção "continuar em segundo plano" | DESK-002 | — |
| Q5 | Aceitar Codex com `--sandbox workspace-write` (pode executar comandos na worktree) como executor padrão? | Necessário para o preset A. Alternativa: Codex sem execução se o CLI permitir (a verificar) | WF-005 | — |
| Q6 | Prioridade de distribuição: AppImage, .deb ou ambos? Assinatura de pacotes? | Recomendação: .deb primeiro (deps declaradas), AppImage depois | DIST-001 | — |
| Q7 | Licença do repositório | README registra ausência de `LICENSE` | Distribuição pública | — |
| Q8 | Orçamento padrão: só alerta ou bloqueio? Valor padrão? | Recomendação: alerta por padrão, bloqueio opt-in | OBS-005 | — |
| Q9 | Como reportar uso de CLIs sob assinatura (Claude Max, ChatGPT, Google)? | Recomendação: contador separado + "equivalente estimado, não cobrado" | OBS-002, OBS-007 | — |
| Q10 | Autorizar consumo de quota real para spikes (telemetria e validação do Planner read-only)? | Poucos prompts triviais em diretório temporário | F0-003, SEC-003 | — |
| Q11 | Commits automáticos na worktree após cada tarefa aprovada (facilita diff/retomada)? | Altera histórico da branch `agent/<run>`, nunca o repositório de origem | RES-001 | — |
| Q12 | Nome e identidade visual definitivos (nome de trabalho "Conductor")? | Verificar conflito de marca antes de publicar | DESK-005, DIST-001 | — |
