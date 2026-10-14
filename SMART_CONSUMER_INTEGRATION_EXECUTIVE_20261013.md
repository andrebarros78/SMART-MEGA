# SMART-MEGA V6 — Integração do consumidor de cartões

Atualizado em 14/10/2026. Repositório canônico: `andrebarros78/SMART-MEGA`. A homologação científica permanece independente do fechamento desta integração.

## Alteração e contrato

O operador verifica o consumo antes de devolver uma geração nova ou uma repetição por cache. O módulo `smart_consumer_integration.py` consome a prova completa da geração e bloqueia o retorno quando a cadeia não é verificável. A prova é gravada atomicamente em `runtime/card_consumption/`, fora do epoch congelado.

O consumidor reexecuta a leitura e qualificação do histórico, os 12 sinais, os pesos do challenger, os escores dos dois modelos, os handoffs tipados, o cronograma oficial, a otimização auxiliar e o seletor de cartão único. A influência de cada sinal é registrada por ablação dos escores. Os pesos do challenger continuam em shadow; não foram promovidos por instalação de dependência ou por resultado retrospectivo.

## Evidência atual

- Fonte testada: `ae3fd694d173418642bdaaccab3f941e84724414`.
- Regressão completa: 1.224 testes aprovados, zero falhas, erros, testes omitidos ou duplicados. Os quatro lotes têm a mesma fonte e impressão digital antes/depois; todos os casos conferem exatamente com a coleção.
- JUnit agregado: `release_evidence/CARD_CONSUMER_20261014/FULL_REGRESSION.xml`, SHA-256 `215e6af1533bded55ebac843960211c75aea910d684732233327b66ca806c7d7`.
- Executor real: `wmcp-cloud-01`, execução consolidada `09bac026-aeab-4061-99f3-12178b955e95`. Não foi atribuído um run do GitHub Actions.
- Módulo de consumo: 150/150 linhas e 16/16 ramificações cobertas. Novo bloqueio no operador: 100% das suas linhas e ramificações. Esta medição é restrita às superfícies alteradas.
- Persistência e repetição verificadas; recibo corrompido recuperado, adulterações e provas malformadas rejeitadas.
- Ablação da seleção: retirar `ewma250`, `freq1000` ou `freq_global` altera o cartão recalculado. A influência medida não prova aumento de acertos.
- 75 versões do lock conferem com o ambiente; `pip check` aprovado. Varredura do conteúdo rastreado sem candidatos de segredo pendentes.

## Consumo e limites

| Capacidade | Consumo comprovado |
| --- | --- |
| 9 agentes determinísticos | Validações nativas e handoffs vinculados aos gates de geração |
| 37 aliases de skills | Sondas de metodologia com proprietário e permissões; 4 referências sem execução |
| Pandas / OpenPyXL | Leitura e validação do histórico causal |
| River | Métricas ADWIN congeladas consumidas pelo cálculo dos pesos do challenger |
| OR-Tools | Otimização real do portfólio auxiliar com escores congelados do champion |
| Pydantic | Revalidação e consumo dos handoffs operacionais |
| pypdf | Releitura do cronograma oficial arquivado |
| 21 fontes externas | Quarentena preservada; nenhuma execução direta foi autorizada |
| LLM externo | Nenhum provedor configurado ou chamado; nenhuma autoridade preditiva presumida |

## Preservação

Os 14 arquivos preditivos protegidos pelo sucessor F12 permanecem preservados. Dos 486 componentes existentes, 484 mantêm os hashes; as alterações são `smart_operator.py` e seu teste de recuperação. Foram acrescentados o módulo de consumo e seu teste. Os registros F11/F12 não foram reescritos.

O concurso 3070 conserva **10, 11, 27, 38, 43, 53**. Seus 17 artefatos permanecem idênticos aos blobs canônicos. As regras de checkout foram corrigidas para preservar esses bytes e dois arquivos arquivados em recuperações limpas.

## Autoridades e publicação

A renovação via executor federado devolveu `CONSTRUCTION_PROVEN`, governança PASS, integridade global PASS e startup do operador OK, vinculados à fonte e ao JUnit acima. As provas e os resultados operacionais estão em `release_evidence/CARD_CONSUMER_20261014/`.

A integração foi publicada em main e recuperada em checkout limpo da revisão 6bc7e4852d4469f0a4a3be0b1c45c175ebd8a1a8. A recuperação conferiu autoridades, hashes, repetição operacional e prova do consumidor sem mutação dos artefatos congelados. O escopo de engenharia desta integração está comprovado; a revisão final inclui o registro dessa recuperação. A homologação científica continua `MISSION_ACTIVE / UNPROVEN`: não foi demonstrada superioridade prospectiva nem 6/6 científico. Nenhum ganho foi inventado e nenhum peso novo foi promovido.
