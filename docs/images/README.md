# Capturas do frontend

Estas imagens documentam o frontend existente. Foram capturadas com Chrome/Playwright, sem geração de imagens por IA ou alteração visual dos componentes.

| Arquivo | Conteúdo | Viewport |
| --- | --- | --- |
| `execution-timeline.png` | Identificação, resultado, worktree e início da timeline de uma execução | 1440 × 1000 |
| `projects.png` | Página inicial de projetos | 1440 × 1000 |
| `project-workspace.png` | Projeto, objetivos e solicitação persistida | 1440 × 1000 |
| `tests-reviews.png` | Revisão expandida e saída registrada dos testes | 1440 × 1000 |
| `overview.png` | Métricas, estados e execuções recentes | 1440 × 1000 |
| `mobile-workspace.png` | Workspace em tela mobile | 390 × 844 |

A fonte foi uma cópia temporária do SQLite, criada com backup a partir de uma conexão de leitura. Os caminhos `/home/felipe` foram substituídos por `/home/developer` somente na cópia. A captura preserva os estados e resultados registrados; não executa novamente a solicitação.

Para produzir novas capturas, utilize uma cópia do banco com os dados privados revisados, uma API em porta separada e o proxy local do Vite apontando para ela. Não inicie worker, não confirme execuções e não use o banco normal como ambiente de geração de imagens. Nesta captura, as requisições feitas pela página foram limitadas a GET/HEAD.

Imagens são registros estáticos da interface no momento da captura; contagens e horários não são valores fixos do produto. O README principal explica os fluxos e as limitações atuais.
