# Invariantes

## Contabilidade

- dinheiro tem moeda e precisão explícitas;
- eventos são imutáveis, idempotentes e append-only;
- caixa e posições derivam dos eventos, nunca de campos editáveis;
- taxas e impostos não desaparecem dentro do valor bruto;
- ordenação para mesmo instante é determinística;
- toda correção referencia o fato corrigido e preserva a história;
- toda reversão reproduz o payload do evento original e inverte seu efeito canônico;
- nenhum campo monetário aceito pode ser descartado por um projetor;
- valuation incompleto nunca se apresenta como patrimônio líquido total;
- snapshot informa o último evento incluído.

## Dados

- `effective_at <= observed_at <= available_at <= ingested_at`, salvo exceção documentada;
- backtest lê somente informações disponíveis no instante simulado;
- revisão gera nova observação/vintage;
- identidade lógica inclui período e dimensões canônicas;
- vintage preserva hash do payload bruto;
- unidade, moeda, timezone, fonte e transformação são obrigatórios.

## Pesquisa

- ModelRun fixa commit, ambiente, dataset, IPS, universo, parâmetros, seed e solver;
- pesos devem ser finitos, somar dentro da tolerância e respeitar constraints;
- somente candidatos pós-validados chegam à decisão;
- status do solver sozinho não prova feasibility;
- comparação usa convenções e annualização iguais;
- seleção usa resultado fora da amostra e penaliza instabilidade/turnover.

## Decisão

- `NO_ACTION` é alternativa obrigatória;
- caixa é entidade explícita e pesos projetados somam um;
- agente pode ler, simular e elaborar draft sem autoridade de registro;
- aprovação humana é explícita, atribuível e expira;
- execução só é concluída após confirmação e reconciliação;
- explicação referencia evidências e versões usadas.
