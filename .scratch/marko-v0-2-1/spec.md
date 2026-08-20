# Marko v0.2.1 — Integrity Hardening

## Objetivo

Fechar ambiguidades contábeis, de privacidade, dados, pesquisa e decisão antes de criar contratos persistentes.

## Escopo

- fronteira público/privado e classificação de dados;
- activity matrix, transferências pareadas e reversões canônicas;
- lotes fiscais reversíveis e consultáveis por `as_of`;
- valuation completo/incompleto com proveniência de preço e FX;
- identidade SIDRA multidimensional e hash do payload bruto;
- candidato pós-validado obrigatório no caminho de decisão;
- walk-forward com drift, step positivo e stress PSD;
- caixa explícito, termos de juros estruturados, CLI e CI em camadas;
- ADRs, status, changelog, roadmap e handoff alinhados.

## Fora de escopo

- PostgreSQL, Parquet, schemas ou migrações;
- broker write adapter;
- habilitação de capital real;
- novos modelos avançados.

## Invariantes de aceite

1. nenhum dado pessoal real é necessário no checkout público;
2. nenhum campo monetário aceito é ignorado;
3. reversão divergente é rejeitada;
4. quantidade e base retornam ao estado anterior após reversão;
5. valuation parcial nunca é retornado como NLV completo;
6. observações com mesmo período e dimensões distintas coexistem;
7. candidato bruto não compõe `DecisionPacket`;
8. pesos projetados, inclusive caixa, somam um;
9. `step <= 0`, matriz de stress inválida e patrimônio zero falham explicitamente;
10. Ruff, MyPy strict, testes e cobertura mínima de 80% passam.

## Verificação

```bash
uv sync --group dev --frozen
uv run ruff check .
uv run mypy
uv run pytest --cov=marko --cov-report=term-missing --cov-fail-under=80
uv sync --group dev --extra research --frozen
uv run --extra research pytest -m optional
```
