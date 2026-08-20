# Registro de riscos dos upstreams

| Risco | Impacto | Controle |
|---|---|---|
| drift de API | resultados deixam de reproduzir | commits fixados e testes de contrato |
| conflito de `cvxpy` | ambientes insolúveis | ambientes de spike separados |
| solver retorna `optimal_inaccurate` | carteira viola IPS | registry, tolerâncias e pós-validação |
| ajuste sobre o backtest | modelo falso campeão | holdout temporal, purge, embargo e deflated metrics |
| licença contaminante | distribuição inviável | adapters/processos isolados e ADR jurídica |
| dados revisados ou futuros | look-ahead | quatro tempos e data vintage |
| retorno silenciosamente diferente | decisão incorreta | cross-validation com dois motores |
| projeto muito amplo | dependência operacional excessiva | extrair contratos mínimos, não plataformas inteiras |
| precisão monetária inadequada | ledger irreconciliável | `Decimal`, moeda explícita e invariantes |
| agente grava sem autorização | perda de controle | read/simulate/draft/approve/record |
| PyPortfolioOpt HRP usa `scipy.cluster.hierarchy._LINKAGE_METHODS` | quebra com SciPy 1.18 | fixar versão no oráculo e manter teste de compatibilidade |
