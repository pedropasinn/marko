# Contribuindo

O Marko é desenvolvido em público para que decisões, experimentos, falhas e mudanças arquiteturais possam ser acompanhados.

## Antes de contribuir

1. abra ou localize uma issue;
2. descreva o problema, evidência e critério de aceite;
3. identifique o contexto: accounting, data, research, decision ou documentation;
4. não inclua credenciais, extratos, posições reais ou dados pessoais;
5. não apresente resultados como recomendação financeira.

Specs executáveis permanecem em `.scratch/<feature>/`. Issues do GitHub são a superfície pública de acompanhamento.

Enquanto a licença e a política de titularidade não forem definidas, contribuições externas ficam limitadas a issues, discussions, reprodução de bugs e sugestões textuais. PRs externos de código não serão aceitos.

## Ambiente

```bash
uv sync --group dev
uv run pytest --cov=marko --cov-report=term-missing
uv run ruff check .
uv run mypy
```

Todo PR precisa preservar:

- eventos contábeis imutáveis;
- dinheiro decimal;
- dados ponto-no-tempo;
- reprodução de ModelRun;
- `NO_ACTION` em toda decisão;
- separação entre draft, aprovação, execução e reconciliação;
- isolamento de dependências e licenças incompatíveis.

## Licença

A licença pública ainda não foi definida. O repositório pode ser visualizado, clonado e bifurcado conforme os termos do GitHub, mas não concede uma licença ampla de uso, modificação ou redistribuição fora dessas condições.
