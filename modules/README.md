# SMART-MEGA V6 - Modulos M01 a M21

Codigo executavel permanece em ../. Cada arquivo pertence a um modulo semantico.
Nao ha copia nem movimentacao de codigo de producao; os vinculos usam SHA-256 e AST.

| Modulo | Responsabilidade | Arquivos | Dependencias |
|---|---|---:|---:|
| M01 | Identidade, caminhos e integridade de fonte | 10 | 3 |
| M02 | Contratos, estados e governanca | 7 | 5 |
| M03 | Coleta e conciliacao de resultados oficiais | 9 | 7 |
| M04 | Captacao, qualidade e integridade de dados | 11 | 3 |
| M05 | Sinais, relevancia e atribuicao | 9 | 5 |
| M06 | Pesos, calibracao e metagovernanca | 8 | 4 |
| M07 | Contexto e causalidade | 2 | 8 |
| M08 | Motor matematico e cartografia | 6 | 0 |
| M09 | Cartoes, selecao e portfolio | 8 | 3 |
| M10 | Aprendizado e fine tuning | 7 | 10 |
| M11 | Laboratorio, challengers e falsificacao | 15 | 10 |
| M12 | Protocolo prospectivo e congelamento | 7 | 4 |
| M13 | Operador local e ciclo operacional | 16 | 10 |
| M14 | Execucao terminal | 25 | 12 |
| M15 | Operador e autoridade GitHub | 3 | 5 |
| M16 | Agentes, skills e SDKs | 7 | 3 |
| M17 | Integracao e entrega | 7 | 13 |
| M18 | Auditoria, regressao e evidencia tecnica | 15 | 12 |
| M19 | Recuperacao, transacoes e seguranca operacional | 13 | 9 |
| M20 | Metricas, analise pos-resultado e relatorios | 4 | 2 |
| M21 | Ferramentas historicas e suporte | 5 | 9 |

## Contrato de integracao
- Registro: semantic_registry.json com HEAD, fontes, hashes, simbolos e dependencias.
- Contrato: ../contracts/SEMANTIC_MODULES_CONTRACT.json.
- Descritores por modulo: M01/module.json a M21/module.json.
- Validar somente leitura: python modules/semantic_modules.py validate
- Consultar codigo: python modules/semantic_modules.py which smart_operator.py
- Testar: python -m unittest discover -s modules/tests -v
- Analise estatica nao comprova imports dinamicos nem vantagem preditiva.
- Registro integrante do GitHub, com independencia de caminhos locais.
