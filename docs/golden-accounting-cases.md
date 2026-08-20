# Casos dourados contábeis

Os resultados abaixo fixam as convenções adotadas pelo Marko. Todos são calculados no escopo total da carteira e em uma moeda de reporte explícita.

## TWR e fluxos externos

O fluxo de cada `PerformancePoint` ocorre imediatamente antes da avaliação final do subperíodo:

```text
V0 = 100
V1 = 160; aporte = 50  -> retorno = 10%
V2 = 200; aporte = 24  -> retorno = 10%
TWR = 1,10 × 1,10 - 1 = 21%
```

Transferência entre contas da própria carteira é fluxo interno: altera a localização, não o patrimônio, e entra no TWR com fluxo externo zero.

## Moeda de reporte e FX

Uma carteira com BRL 550 e USD 100 vale BRL 1.100 a USD/BRL 5,50. Com USD/BRL 6,00, sem fluxo externo, vale BRL 1.150. O TWR em BRL é 4,545455%; a variação cambial faz parte do retorno nessa moeda de reporte.

Um aporte em moeda estrangeira precisa ser convertido pela cotação disponível no instante do fluxo antes de entrar como `external_flow`.

## Corporate actions

O caso fixo começa com 10 PARENT a BRL 100:

1. split 2:1 produz 20 PARENT a BRL 50;
2. spinoff produz 5 CHILD, com PARENT a BRL 45 e CHILD a BRL 20;
3. amortização de BRL 50 reduz CHILD a BRL 10 e deixa BRL 50 em caixa.

O patrimônio permanece BRL 1.000 e o TWR é zero. Split e spinoff não são fluxos externos. Amortização mantida dentro da carteira é retorno de capital em caixa, também não um fluxo externo.

## Taxas, impostos e principal

Taxas e impostos permanecem separados do bruto. Dividendos e juros são renda; amortização é devolução de principal. Reversões invertem cada categoria sem apagar o evento original.
