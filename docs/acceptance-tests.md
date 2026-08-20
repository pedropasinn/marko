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
- [ ] casos dourados de TWR com transferências e múltiplas moedas;
- [ ] confirmação de broker duplicada é idempotente;
- [ ] impostos brasileiros por instrumento e prazo.
