# SMART-MEGA V6 — F01/F10: Executor Externo Governado

## Decisão arquitetural

A `main` mudou a autoridade para
`SMART_GITHUB_CANONICAL_EXTERNAL_EXECUTION_NO_ACTIONS_20261021`.
GitHub continua repositório canônico, mas GitHub Actions está proibido.
F01 permanecia baseado exclusivamente em `.github/workflows`, cujos
arquivos foram aposentados. Isso resultava em zero roots e nove arquivos
produtivos obrigatórios inalcançáveis, inclusive na própria `main`.

O root estático governado passa a ser o CLI **existente**
`smart_github_operator.py`, que possui
`STATIC_EXECUTION_DEPENDENCIES = ("smart_operator.py",)`, ponto `__main__`
e consumidor `smart_operator.py`. A árvore de imports e dependências
estáticas valida a continuidade do pipeline sem criar rota alternativa.

F01 só aceita esse root quando o verificador canônico de política aprova
os documentos vigentes, confirma GitHub Actions proibido e uso de
executores externos autorizado, e o arquivo de CLI é regular, não um
symlink, parseável, com entrada `__main__` e dependência declarada.

F10 valida esse root e sua origem, exige zero workflow roots, proíbe
alegações de execução dinâmica a partir de mera alcançabilidade estática
e preserva todos os controles anteriores de fontes aposentadas,
autoridades materiais, sentido dos imports, integração e aliases.

## Limites de autoridade

- Root **não** é recibo de execução de um operador produtivo.
- Executores LMCP/SentinelX podem rodar testes isolados quando autorizados;
  seus comprovantes de execução são independentes do grafo F01.
- O inventário F08 é atualizado para incluir os nove antigos entrypoints
  de diagnósticos/validações que deixam de ser rotulados como produção
  após a remoção dos workflows. Atributos preditivos desses itens
  permanecem sem autoridade material.
- Nunca reativa workflow de Actions, modelo de vídeo, fonte CAIXA,
  freeze ou escrita em `main`.

## Provas e próxima certificação

- Comparativo pré-correção: F01 `FAIL` na `main` atual e no candidato,
  zero roots, nove módulos obrigatórios inalcançáveis.
- Correção: F01 `PASS`, F10 `PASS`, 96 componentes produtivos
  estaticamente alcançáveis, zero obrigatórios inalcançáveis,
  um root de CLI governado e zero workflow roots.
- SentinelX `wmcp-cloud-01`: 24 testes `pytest` de F01/F05/F08/F10
  e casos de negação/forjamento de raiz governada aprovados.
- Os snapshots F01, F05 e F10 são regenerados na branch e vinculados
  aos novos hashes de fonte. A validação integral e a certificação
  persistente ainda dependem de runner isolado com as dependências
  completas em `requirements.lock.txt`; isto não concede certificação
  de release nem promove código a `main`.
- Pedido de instalação governada: `capreq_48e74ef106de4e43860c6e82919a689d`.
  A operação administrativa direta de instalação reportou
  `admin_operation_not_allowed`. Não contornar a negativa.
