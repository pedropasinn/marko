# Auditoria dos upstreams

Snapshot reproduzível: [`upstreams.lock.json`](../../upstreams.lock.json). Os clones ficam em `/home/pedro/repo/marko-references`; nenhum deles é dependência implícita do produto.

| Projeto | Papel no Marko | Decisão |
|---|---|---|
| skfolio | construção e validação de portfólios | adapter quantitativo principal |
| Riskfolio-Lib | modelos e restrições avançados | laboratório e oráculo |
| PyPortfolioOpt | baselines legíveis e independentes | oráculo e adapter secundário |
| cvxportfolio | política multi-período, custos e execução | referência de arquitetura e oráculo |
| vectorbt | bancada de backtests em escala | pesquisa isolada |
| QuantStats | métricas e relatórios | oráculo; métricas essenciais próprias |
| OpenBB | contrato de provedores | referência; conectores brasileiros próprios |
| Qlib | registro experimental, rolling e ML | referência futura, não dependência do MVP |
| Ghostfolio | UX de patrimônio e importação | referência visual e de fluxos |
| Wealthfolio | ledger, drift, cenários e permissões de agente | principal referência de produto |
| Portfolio Performance | contabilidade, performance e explicabilidade | principal oráculo contábil |

## Conclusões vinculantes

1. O domínio financeiro do Marko não importa tipos de bibliotecas quantitativas.
2. Entradas e saídas externas atravessam adapters com esquemas versionados.
3. Valores monetários usam decimal exato; matrizes e retornos usam ponto flutuante somente no laboratório.
4. Toda decisão preserva dados, código, ambiente, solver, política, universo e diagnóstico.
5. Licenças copyleft ou restritivas não autorizam incorporação de código.
6. Modelos só avançam depois de contabilidade, dados temporais e validação.

As evidências específicas estão em [`upstreams/`](upstreams/).
