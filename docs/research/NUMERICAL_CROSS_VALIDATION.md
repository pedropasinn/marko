# Validação cruzada numérica

Dataset: quatro ativos, 504 observações diárias, seed `20260820`, SHA-256 `efd7a9679b27ef7171e0b3a64c459abb03df24fd9123661faebf137998e8d7b4`. Bounds `[0,1]`, soma dos pesos igual a um, covariância histórica diária e objetivo minimum variance.

| Motor | CDI | IPCA | BR Equity | Global Equity | Vol. diária |
|---|---:|---:|---:|---:|---:|
| skfolio | 99,1154% | 0,4672% | 0,2334% | 0,1840% | 0,049079% |
| Riskfolio | 99,1863% | 0,3491% | 0,2635% | 0,2011% | 0,049075% |
| PyPortfolioOpt | 98,2024% | 1,1211% | 0,3443% | 0,3322% | 0,049182% |

A distância L1 é 0,2362 p.p. entre skfolio e Riskfolio e 1,8258 p.p. entre skfolio e PyPortfolioOpt. A amostra é deliberadamente mal condicionada pela volatilidade muito baixa do CDI; diferenças pequenas na formulação e tolerância produzem pesos visíveis, embora a volatilidade objetivo mude pouco.

Conclusão operacional: não comparar apenas pesos. O gate deve verificar feasibility, valor da função objetivo, sensibilidade a tolerância/solver e estabilidade em perturbações. O artefato completo está em [`minvar-cross-validation.json`](../../research/spikes/minvar-cross-validation.json).

## Falha de compatibilidade descoberta

O `HRPOpt` do PyPortfolioOpt 1.6.0 acessa `scipy.cluster.hierarchy._LINKAGE_METHODS`, removido no SciPy 1.18. O spike HRP usa skfolio; o PyPortfolioOpt só volta a ser oráculo desse modelo após pin compatível ou correção upstream.
