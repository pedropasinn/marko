# Marko

Marko é um gestor quantitativo pessoal orientado a passivos. Ele mantém a verdade contábil, pesquisa alternativas reproduzíveis e prepara decisões explicáveis; não prevê ordens diretamente a partir de texto e não executa capital real sem aprovação humana.

## Linguagem do domínio

- **Activity**: fato financeiro imutável.
- **Ledger**: sequência append-only de activities da qual derivam caixa e posições.
- **Instrument Master**: identidade estável, listagens e moedas dos instrumentos.
- **Liability**: obrigação econômica e seus fluxos futuros.
- **IPS**: política versionada que define objetivos, limites e autoridade.
- **Universe**: conjunto elegível de instrumentos em uma data.
- **Constraint Set**: regras executáveis derivadas do IPS.
- **Observation**: dado com tempos econômico, observado, disponível e ingerido.
- **Data Vintage**: versão reproduzível de um conjunto de observações.
- **Model Run**: execução imutável com dados, código, ambiente, solver e diagnósticos.
- **Decision Packet**: alternativas, custos, riscos, evidências e `NO_ACTION`.

## Três verdades

1. **Accounting Truth**: o que ocorreu e qual é o patrimônio reconciliado.
2. **Research Truth**: o que um experimento reproduzível encontrou.
3. **Decision Truth**: o que foi proposto, autorizado e registrado.

Essas verdades compartilham identificadores e versões, mas nenhuma sobrescreve outra.

## Fronteira

O núcleo contém dinheiro, instrumentos, contas, activities, ledger, passivos, IPS, universos e constraints. Provedores, bancos, brokers, solvers, bibliotecas quantitativas, LLMs e interfaces são adapters externos.

## Invariantes de autoridade

- Pesquisa não altera o ledger.
- Draft não é decisão aprovada.
- Aprovação não prova execução; reconciliação fecha o ciclo.
- Toda decisão inclui a alternativa de não agir.
- Capital real permanece fora do escopo até satisfazer os gates definidos no roadmap.
