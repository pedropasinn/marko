# Segurança

Não publique tokens, credenciais de corretora, extratos, posições reais ou dados pessoais em issues, discussões, commits ou fixtures.

A classificação dos artefatos e os caminhos locais permitidos estão em [`docs/data-classification.md`](docs/data-classification.md). `.gitignore` é uma última barreira, não autorização para copiar dados privados ao workspace público.

O Marko não executa ordens reais. Qualquer mudança que introduza escrita externa, conexão com broker ou movimentação financeira precisa de threat model, autorização humana explícita, idempotência e reconciliação.

Falhas que possam expor credenciais ou alterar registros contábeis devem ser reportadas por um canal privado ao mantenedor, não por issue pública.
