# Microsoft Qlib

## Ficha

- Origem: `https://github.com/microsoft/qlib.git`; `main`; `79633dd9506ea689e5400dea0197717b5b3d74b7`; versão dinâmica.
- Linguagens/dependências: Python/Cython; MLflow, LightGBM, PyTorch, Redis, MongoDB, CVXPY, Jupyter e outras opcionais.
- Licença: MIT; permite dependência, modificação e produto com aviso.
- Arquitetura/APIs: providers de calendar/instrument/feature/PIT/expression/dataset; handlers/processors; workflow, experiment/recorder, tasks rolling/online; models, backtest, exchange e executors.
- Testes: unitários, integração e workflows de exemplo; estágio declarado de desenvolvimento alpha.

## Cobertura

Pipelines de features e datasets, modelos supervisionados/adaptativos, ensembles, experiment registry via MLflow, geração de tarefas rolling, online manager, backtesting, estratégias e execução. Há suporte a dados PIT, mas suas convenções não substituem os quatro tempos e vintages do Marko. RD-Agent é integração adjacente, não núcleo necessário.

## Avaliação

- Fortes: ciclo completo de pesquisa ML e separação offline/online.
- Fracos: dependências pesadas, pressupostos de equity alpha e complexidade prematura.
- Duplicações: backtest com vectorbt; registry parcialmente reproduzível com solução menor.
- Único: workflow ML/rolling integrado.
- Classificação: **D — ARCHITECTURAL REFERENCE ONLY** até o Marko ML; componentes pontuais poderão virar **B** depois.
