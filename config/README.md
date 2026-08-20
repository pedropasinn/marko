# Configuração do caso pessoal

`personal-case.example.toml` contém valores sintéticos e serve somente para demonstração.

O caso real deve ficar em `config/personal-case.local.toml`, `var/private/personal-case.toml` ou outro caminho informado por `MARKO_CASE_PATH`. Esses caminhos não são versionados.

O caso só pode gerar Liability e IPS operacionais quando vencimento, juros/indexação, cobrança antecipada, liquidez mínima, perda máxima, residência fiscal, corretoras e instrumentos forem informados.
