# Eval report

- **date**: 2026-06-11T22:51:47+00:00
- **repository**: fastapi/full-stack-fastapi-template
- **chat_model**: gpt-5.4-mini
- **embedding_model**: text-embedding-3-large

## Mode: agentic

| id | category | hit@5 | MRR | faithfulness | correctness | grounded | refused-ok | latency ms | cost $ |
|---|---|---|---|---|---|---|---|---|---|
| sl-01 | symbol_location | True | 1.0 | 5 | 5 | True | — | 1956 | 0.0020 |
| sl-02 | symbol_location | True | 1.0 | 5 | 5 | True | — | 3587 | 0.0051 |
| sl-03 | symbol_location | True | 1.0 | 5 | 5 | True | — | 3559 | 0.0061 |
| sl-04 | symbol_location | True | 0.5 | 5 | 5 | True | — | 5800 | 0.0112 |
| sl-05 | symbol_location | True | 0.5 | 5 | 5 | True | — | 3488 | 0.0055 |
| sl-06 | symbol_location | True | 0.5 | 5 | 5 | True | — | 4210 | 0.0057 |
| sl-07 | symbol_location | False | 0.0 | 5 | 5 | True | — | 2183 | 0.0036 |
| sl-08 | symbol_location | True | 1.0 | 5 | 5 | True | — | 3298 | 0.0080 |
| mh-01 | multi_hop | True | 1.0 | 4 | 4 | True | — | 9763 | 0.0183 |
| mh-02 | multi_hop | True | 1.0 | 5 | 5 | True | — | 8234 | 0.0131 |
| mh-03 | multi_hop | True | 0.5 | 5 | 5 | True | — | 11329 | 0.0321 |
| mh-04 | multi_hop | True | 1.0 | 2 | 5 | True | — | 4301 | 0.0089 |
| mh-05 | multi_hop | True | 1.0 | 5 | 5 | True | — | 8223 | 0.0166 |
| mh-06 | multi_hop | True | 1.0 | 5 | 4 | True | — | 7972 | 0.0167 |
| ae-01 | api_endpoints | True | 1.0 | 5 | 5 | True | — | 4878 | 0.0054 |
| ae-02 | api_endpoints | True | 0.5 | 4 | 3 | True | — | 14942 | 0.0154 |
| ae-03 | api_endpoints | True | 0.5 | 5 | 5 | True | — | 11549 | 0.0196 |
| ae-04 | api_endpoints | True | 1.0 | 5 | 5 | True | — | 6102 | 0.0053 |
| ae-05 | api_endpoints | True | 1.0 | 2 | 2 | True | — | 4593 | 0.0070 |
| dp-01 | dependencies | False | 0.0 | 5 | 5 | True | — | 5765 | 0.0080 |
| dp-02 | dependencies | False | 0.0 | 4 | 5 | True | — | 3438 | 0.0027 |
| dp-03 | dependencies | True | 1.0 | 4 | 4 | False | — | 8512 | 0.0099 |
| ad-01 | adversarial | — | — | — | — | — | True | 0 | 0.0000 |
| ad-02 | adversarial | — | — | — | — | — | True | 1342 | 0.0012 |
| ad-03 | adversarial | — | — | — | — | — | True | 1431 | 0.0012 |

- hit@5: 0.86
- MRR: 0.73
- faithfulness: 4.55
- correctness: 4.64
- grounded rate: 0.95
- refusal pass rate: 1.00
- mean latency ms: 5618.20
- total cost $: 0.2286

## Mode: single_shot

| id | category | hit@5 | MRR | faithfulness | correctness | grounded | refused-ok | latency ms | cost $ |
|---|---|---|---|---|---|---|---|---|---|
| sl-01 | symbol_location | True | 1.0 | 5 | 5 | True | — | 1155 | 0.0017 |
| sl-02 | symbol_location | True | 1.0 | 5 | 5 | True | — | 2203 | 0.0026 |
| sl-03 | symbol_location | True | 1.0 | 5 | 5 | True | — | 1837 | 0.0024 |
| sl-04 | symbol_location | True | 0.5 | 5 | 5 | True | — | 1558 | 0.0027 |
| sl-05 | symbol_location | True | 0.5 | 5 | 5 | True | — | 1511 | 0.0030 |
| sl-06 | symbol_location | True | 0.5 | 5 | 5 | True | — | 1256 | 0.0023 |
| sl-07 | symbol_location | False | 0.0 | 4 | 5 | True | — | 1357 | 0.0024 |
| sl-08 | symbol_location | True | 1.0 | 5 | 5 | True | — | 1793 | 0.0020 |
| mh-01 | multi_hop | True | 1.0 | 4 | 3 | True | — | 2432 | 0.0039 |
| mh-02 | multi_hop | True | 1.0 | 4 | 4 | True | — | 2461 | 0.0038 |
| mh-03 | multi_hop | True | 0.5 | 4 | 5 | True | — | 2940 | 0.0050 |
| mh-04 | multi_hop | True | 1.0 | 4 | 5 | True | — | 2140 | 0.0041 |
| mh-05 | multi_hop | True | 1.0 | 4 | 5 | True | — | 1694 | 0.0029 |
| mh-06 | multi_hop | True | 1.0 | 5 | 5 | True | — | 1719 | 0.0027 |
| ae-01 | api_endpoints | True | 1.0 | 5 | 5 | True | — | 5354 | 0.0026 |
| ae-02 | api_endpoints | True | 0.5 | 4 | 3 | True | — | 1475 | 0.0024 |
| ae-03 | api_endpoints | True | 0.5 | 4 | 4 | True | — | 2203 | 0.0037 |
| ae-04 | api_endpoints | True | 1.0 | 5 | 5 | True | — | 1783 | 0.0028 |
| ae-05 | api_endpoints | True | 1.0 | 5 | 1 | True | — | 1695 | 0.0036 |
| dp-01 | dependencies | False | 0.0 | 5 | 5 | True | — | 1647 | 0.0029 |
| dp-02 | dependencies | False | 0.0 | 5 | 5 | False | — | 1726 | 0.0028 |
| dp-03 | dependencies | True | 1.0 | 4 | 4 | True | — | 1572 | 0.0035 |
| ad-01 | adversarial | — | — | — | — | — | True | 0 | 0.0000 |
| ad-02 | adversarial | — | — | — | — | — | True | 2574 | 0.0089 |
| ad-03 | adversarial | — | — | — | — | — | True | 1781 | 0.0052 |

- hit@5: 0.86
- MRR: 0.73
- faithfulness: 4.59
- correctness: 4.50
- grounded rate: 0.95
- refusal pass rate: 1.00
- mean latency ms: 1914.64
- total cost $: 0.0800

## Comparison

| metric | agentic | single_shot |
|---|---|---|
| hit@5 | 0.86 | 0.86 |
| MRR | 0.73 | 0.73 |
| faithfulness | 4.55 | 4.59 |
| correctness | 4.64 | 4.50 |
| grounded rate | 0.95 | 0.95 |
| refusal pass rate | 1.00 | 1.00 |
| mean latency ms | 5618.20 | 1914.64 |
| total cost $ | 0.2286 | 0.0800 |
