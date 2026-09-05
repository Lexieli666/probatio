## probatio

**cases**

| case | verdict | assertions | cost | latency ms | snapshot |
| --- | --- | --- | --- | --- | --- |
| g-cc-001 | pass | 2/2 | n/a | 1098 | unchanged |
| g-cc-002 | pass | 2/2 | n/a | 1243 | unchanged |
| g-cc-017 | pass | 2/2 | n/a | 1394 | unchanged |
| g-ge-001 | pass | 2/2 | n/a | 1108 | unchanged |
| g-ge-002 | pass | 2/2 | n/a | 1039 | unchanged |
| g-ge-024 | pass | 2/2 | n/a | 1650 | unchanged |
| g-gh-001 | pass | 2/2 | n/a | 2009 | unchanged |
| g-gh-002 | pass | 2/2 | n/a | 1462 | unchanged |
| g-gh-017 | pass | 2/2 | n/a | 1096 | unchanged |
| g-md-017 | pass | 3/3 | n/a | 1840 | unchanged |
| g-md-018 | pass | 3/3 | n/a | 1434 | unchanged |
| g-md-021 | pass | 3/3 | n/a | 1224 | unchanged |
| g-su-001 | pass | 3/3 | n/a | 1011 | unchanged |
| g-su-002 | pass | 3/3 | n/a | 1019 | unchanged |
| g-su-003 | pass | 3/3 | n/a | 902 | unchanged |
| g-cc-001 | pass | 2/2 | n/a | 3583 | unchanged |
| g-cc-002 | pass | 2/2 | n/a | 3726 | unchanged |
| g-cc-017 | pass | 2/2 | n/a | 3116 | unchanged |
| g-ge-001 | pass | 2/2 | n/a | 7369 | unchanged |
| g-ge-002 | pass | 2/2 | n/a | 4296 | unchanged |
| g-ge-024 | pass | 2/2 | n/a | 4186 | unchanged |
| g-gh-001 | pass | 2/2 | n/a | 3708 | unchanged |
| g-gh-002 | pass | 2/2 | n/a | 3129 | unchanged |
| g-gh-017 | pass | 2/2 | n/a | 3394 | unchanged |
| g-md-017 | pass | 3/3 | n/a | 5832 | unchanged |
| g-md-018 | FAIL | 2/3 | n/a | 6655 | unchanged |
| g-md-021 | FAIL | 2/3 | n/a | 4853 | unchanged |
| g-su-001 | FAIL | 2/3 | n/a | 2967 | unchanged |
| g-su-002 | FAIL | 2/3 | n/a | 3169 | unchanged |
| g-su-003 | FAIL | 2/3 | n/a | 2864 | unchanged |

- stability: not measured (no case ran more than once; --runs was 1)
- cost: unknown (no priced calls; 15 case(s) unpriced)
- cost is a lower bound: no price for g-cc-001, g-cc-002, g-cc-017, g-ge-001, g-ge-002, g-ge-024, g-gh-001, g-gh-002, g-gh-017, g-md-017, g-md-018, g-md-021, g-su-001, g-su-002, g-su-003

**warnings (15)**

- g-cc-001: cost ceiling for g-cc-001 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-cc-002: cost ceiling for g-cc-002 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-cc-017: cost ceiling for g-cc-017 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-ge-001: cost ceiling for g-ge-001 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-ge-002: cost ceiling for g-ge-002 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-ge-024: cost ceiling for g-ge-024 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-gh-001: cost ceiling for g-gh-001 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-gh-002: cost ceiling for g-gh-002 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-gh-017: cost ceiling for g-gh-017 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-md-017: cost ceiling for g-md-017 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-md-018: cost ceiling for g-md-018 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-md-021: cost ceiling for g-md-021 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-su-001: cost ceiling for g-su-001 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-su-002: cost ceiling for g-su-002 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-su-003: cost ceiling for g-su-003 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
