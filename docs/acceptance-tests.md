# Testes de aceitação

## Núcleo 0.1

- somar/subtrair BRL preserva centavos; moedas diferentes falham;
- duas activities com o mesmo ID falham sem alterar o ledger;
- compra reduz caixa por bruto + taxas + impostos e aumenta posição;
- venda reduz posição e aumenta caixa líquido;
- depósito, retirada, rendimento, dividendo, taxa e imposto fecham exatamente;
- leitura do ledger é ordenada de modo estável;
- instrumento exige identidade, moeda e precisão válidas;
- passivo calcula valor devido, funding ratio e shortfall na mesma moeda;
- IPS e Universe são versionados e temporalmente válidos;
- constraints rejeitam limites incoerentes;
- observação rejeita viagem temporal.

## Próximos gates

- [x] golden cases XIRR contra Portfolio Performance;
- [x] minimum variance cruzado entre três motores com objetivo e feasibility;
- [x] splits temporais preservam purge e embargo;
- [x] DecisionPacket sem `NO_ACTION` é inválido;
- [x] cash-flow rebalancing prefere aporte quando respeita o IPS;
- [x] liquidez mínima pode bloquear um draft sem ocultá-lo;
- [x] reversões restauram caixa, posição, quantidade e base por `as_of`;
- [x] transferências exigem pares consistentes e reversão das duas pernas;
- [x] campos monetários sem efeito são rejeitados;
- [x] valuation incompleto falha fechado e lista evidências ausentes;
- [x] observações SIDRA multidimensionais coexistem no mesmo período;
- [x] `step <= 0`, candidato incompatível e stress inválido são rejeitados;
- [x] pesos projetados incluem caixa explícito e somam um;
- [x] CLI cobre configuração válida e arquivo ausente;
- [x] codecs versionados fazem round trip das quatro verdades;
- [x] backup adulterado falha e restore repetido é idempotente;
- [x] Parquet preserva observações e hash do conteúdo;
- [x] PostgreSQL detecta conflito e bloqueia UPDATE/DELETE;
- [x] scheduler shadow é determinístico e reconciliação rejeita evidência futura;
- [x] casos dourados de TWR com transferências e múltiplas moedas;
- [ ] confirmação de broker duplicada é idempotente;
- [ ] impostos brasileiros por instrumento e prazo.
