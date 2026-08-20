# Contribuindo

O Marko é desenvolvido em público para que decisões, experimentos, falhas e mudanças arquiteturais possam ser acompanhados.

## Antes de propor código

1. abra ou localize uma issue;
2. descreva o problema, evidência e critério de aceite;
3. identifique o contexto: accounting, data, research, decision ou documentation;
4. não inclua credenciais, extratos, posições reais ou dados pessoais;
5. não apresente resultados como recomendação financeira.

Specs executáveis permanecem em `.scratch/<feature>/`. Issues do GitHub são a superfície pública de acompanhamento.

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

A licença pública ainda não foi definida. O repositório público permite acompanhar e discutir o desenvolvimento, mas não concede implicitamente permissão de uso, modificação ou redistribuição. Issues e sugestões são bem-vindas; PRs de código serão avaliados junto com a futura decisão de licença.
