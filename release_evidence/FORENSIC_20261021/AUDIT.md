# SMART-MEGA V6 — auditoria forense de 21/10/2026

Repositório: `andrebarros78/SMART-MEGA`. Autoridade produtiva: GitHub `main`.
Baseline inspecionada: `c83d15996cef4f85ad80eab9de7c0afdbdf83de0`.
Candidata final de código: `b04f4e75fd1bab1ed77c3b039172203dc0f65a3f`.
Candidata anterior com preservação de bytes: `1c56aa72b9bebddef6f374a19b26e6cd1e20cbfe`.
Conciliação com a integração da PR #70 em `main`: `eb08c4de9cd4034e12a1b83d5b4b133460492ba5`.
PR de correção: [#71](https://github.com/andrebarros78/SMART-MEGA/pull/71).

GitHub Actions não foi utilizado. O LMCP/Linux foi um executor temporário e isolado, sem autoridade concorrente ao GitHub. Os arquivos do roadmap anexado foram confrontados com a política vigente; hostname e caminho Windows históricos não foram tratados como exigência operacional.

## Achados e correções

| Prioridade | Falha observada | Correção e prova |
|---|---|---|
| P0 | Uma pasta contendo `pytest-` recebia identidade `PASS`, ciclo `FROZEN` sintético e lock fictício em um processo Python comum. Também dispensava reconciliação e o hash esperado para sobrescrever um epoch. | A aplicação agora rejeita essa autorização. Somente fixtures do pytest instalam um adaptador limitado à árvore temporária real. Testes em novos processos verificam a negativa, inclusive com variável de ambiente forjada. Estados sintéticos persistidos também são recusados. |
| P0 | JUnit declarava testes aprovados sem conter casos; falhas, erros e ignorados podiam ser escondidos por contadores falsos. | Contagem dos casos e resultados reais, conferência dos agregados de cada suíte, suporte a suítes aninhadas e recusa de promoção inconsistente. Integridade global reutiliza o mesmo leitor. |
| P0 | `conftest.py` e testes de `tests/` não integravam a impressão digital do código. | Ambos passam a integrar os dois verificadores. Caminhos relativos completos evitam colisão entre testes homônimos; o vínculo com os blobs Git recusa alteração posterior. |
| P1 | Cópias locais isoladas eram consideradas autoridade concorrente e bloqueavam um checkout Git válido. | A raiz do checkout e o Git top-level continuam obrigatórios. Cópias físicas são registradas como observação, sem autoridade canônica. A baseline apresentou 48 falhas nesse ambiente, predominantemente por esse bloqueio. |
| P0 | O renovador exigia GitHub Actions, apesar da proibição expressa vigente. | Incorporado o contrato externo da PR #70, revisão `30bd108`, com SHA, origem, identificação da execução e aprovação explícita. Recibos legados são recusados. Aprovação por ambiente e hashes não são assinatura criptográfica de um executor independente. |
| P0 | A renovação podia reaproveitar cobertura histórica sem vincular o relatório ao fonte medido. | Antes de escrever qualquer autoridade, o renovador exige inventário completo, arquivos dentro da raiz e `source_sha256` correspondente em cada fonte coberto. Relatório antigo ou sem vínculo é recusado. A cobertura foi medida novamente para esta auditoria. |
| P1 | Clones novos convertiam as terminações de linha de quatro fontes, alterando os hashes brutos F01/F05/F10 embora o checkout estivesse limpo. | Reproduzidas três falhas em clones novos. Regras explícitas em `.gitattributes` preservam os bytes versionados desses quatro arquivos. Os quatro clones finais foram confrontados com todos os arquivos rastreados da preparação, sem divergência de bytes. |
| P0 | Mesmo vinculada ao fonte correto, uma cobertura incompleta podia passar pela pré-verificação e permitir escritas antes de falhar em uma etapa posterior. | A pré-verificação agora aplica a regra vigente de linhas e ramos completos antes de qualquer escrita. Quatro casos negativos reproduziram a falha e passaram após a correção, verificando a preservação de todos os arquivos. |

As fixtures antigas de JUnit foram corrigidas para conter casos e resultados correspondentes. Não foram alteradas para aceitar provas inválidas.

A divergência de cobertura foi confirmada por análise do fonte atual com o parser da versão instalada de `coverage`: o relatório antigo atribuía 265 instruções ao operador, enquanto o fonte atual contém 1.129. As contagens também divergiam em integridade global (242/246), pipeline de portfólio (57/89) e orquestração (239/271). Nenhum desses registros antigos vinculava o hash do fonte medido. Essas contagens estáticas não substituem a nova medição de execução.

## Não regressão científica e vínculos

Os vínculos F01, F05, F07, F10 e F12 foram reconstruídos pelos geradores existentes. A primeira candidata integral revelou cinco falhas em F07/F12; elas foram reproduzidas e corrigidas.

F12 agora reconhece exclusivamente as substituições exatas dos guardas operacionais, por comparação em memória. A reversão precisa reconstruir os hashes científicos F11 originais. O código revertido não é executado; alterações de parâmetros, seletor, predição ou guardas diferentes continuam reprovadas. Os hashes de referência F11 não foram substituídos.

Resultados, planilha oficial, previsões congeladas e pesos não foram regenerados. O anexo histórico de resultados não substituiu a base canônica. Não houve cartão retrospectivo nem operação de aposta.

## Execuções

| Revisão | Execução observada |
|---|---|
| `c83d159` | 1.412 aprovados, 48 falhas, 0 erros; 8 subtestes aprovados. Duração: 650,88 s. |
| `00a9cfc` | 1.499 aprovados, 5 falhas, 0 erros; 8 subtestes aprovados. Duração: 908,19 s. Falhas: vínculos F07/F12. |
| `ba8c004` | Quatro lotes instrumentados completos: 1.510 aprovados, 3 falhas F01/F05/F10 por terminações de linha, 0 erros; 8 subtestes aprovados. Não é uma regressão aprovada. |
| `1c56aa7` | 1.513 aprovados, 0 falhas, 0 erros, 0 ignorados; 8 subtestes aprovados. Quatro lotes completos com saídas zero; duração de cada lote: 459,32 s / 479,50 s / 478,80 s / 469,73 s. |
| `eb08c4d` | 100 aprovados e 1 falha: o teste de vínculo recusou corretamente o JUnit recebido de `main`, com 1.482 declarados e 1.474 casos reais. |
| `b04f4e7` | 1.517 aprovados, 0 falhas, 0 erros, 0 ignorados; 8 subtestes aprovados. Quatro lotes com 337 / 292 / 433 / 455 casos, saídas zero e inventário exato. Durações: 352,91 s / 380,92 s / 372,76 s / 365,79 s. Fontes estáveis e árvores Git limpas após os testes. |

Uma tentativa anterior de instrumentação integral foi interrompida e não gravou JUnit nem dados de cobertura. Seus pontos de progresso não foram usados como evidência de aprovação ou cobertura. Todos os 1.513 casos coletados foram redistribuídos por módulos inteiros em quatro clones isolados; cada execução completa possui seu próprio código de saída, JUnit, log e recibo. A comparação do inventário coletado com os casos reais impede que a divisão esconda testes omitidos.

A PR #70 foi integrada em `main` como `702f210` durante a auditoria. A conciliação `eb08c4d` preservou os sete registros de autoridade recebidos de `main`, verificando seus hashes Git, e manteve a política equivalente de `.gitattributes` com as quatro exceções novas. Esses registros não foram apresentados como certificação das correções desta auditoria. O código e os testes têm a mesma impressão digital de `1c56aa7`.

O JUnit bruto do pytest contabilizou oito subtestes aprovados nos agregados sem emitir oito elementos `testcase` adicionais. Os relatórios brutos foram preservados. Para formar o agregado da auditoria, foi conferido que cada partição terminou com saída zero, que cada caso real estava aprovado e que os conjuntos de casos eram disjuntos e correspondiam exatamente ao inventário coletado. Somente então os contadores das suítes do agregado foram recalculados a partir dos casos reais. Não foram inventados casos ou removidas falhas. O leitor estrito continua recusando contadores inconsistentes, inclusive em JUnit bruto emitido por essa versão do pytest.

Os registros de autoridade recebidos de `main` foram arquivados antes da correção do vínculo de regressão. O JUnit canônico e seu vínculo de identidade foram atualizados com a execução integral efetivamente comprovada. Isso não renova a certificação global de construção, que continua exigindo cobertura integral e todas as demais verificações.

Após a última atualização dos vínculos, os leitores da aplicação confirmaram `PASS` para os 1.517 casos reais, o vínculo da identidade canônica e o vínculo do código ao commit testado `b04f4e7`. A impressão digital dos 358 arquivos de código e configuração é `975f375cbdf366fa32cc34b4da8c1daf780b07e7ec31b832c5d9669374fa01b0`.

Reproduções negativas: 12 falhas no teste de autorização antes da correção; 5 falhas no teste de JUnit; 2 falhas no leitor global; 5 falhas no vínculo dos fontes de teste; teste de portabilidade reprovado antes da correção. O contrato de cobertura foi reprovado antes de implementado e aprovado depois.

Retestes direcionados observados: 92 aprovados na família inicial; 24 na família de vínculo de código; 34 na rodada final dos primeiros achados; 45 na família de certificação/cobertura; 30 em F07/F11/F12/cobertura. As execuções integrais são apresentadas separadamente dos testes focados.

## Segurança e dependências

As 75 versões do lock foram confrontadas com o ambiente real, sem divergências. `pip check`: `No broken requirements found`.

A varredura examinou 2.013 arquivos de texto e separou 201 binários. Sete regras procuraram tokens GitHub, AWS, OpenAI, Groq, Google, chaves privadas e credenciais em URLs. Nenhum candidato ficou pendente. A única ocorrência foi a credencial fictícia do teste de rejeição de URLs; a exceção ficou limitada ao arquivo e ao hash exato do exemplo. Valores não foram expostos. Isso não constitui auditoria de todas as famílias de segredos nem consulta a uma base de vulnerabilidades de dependências.

A varredura integral corresponde a `ba8c004`. Na candidata final `b04f4e7`, foram examinados os 13 arquivos rastreados alterados desde aquela revisão, sem candidato pendente, vinculando o hash do relatório integral anterior e confirmando o checkout limpo. Uma repetição integral atingiu o limite de 30 segundos e não foi contabilizada como prova aprovada.

## Limitações e critério de aprovação

O GitHub retornou `protected=false` para `main`. A consulta de rulesets retornou HTTP 403 e exigência de GitHub Pro ou repositório público. O repositório não teve a privacidade alterada e nenhum plano pago foi contratado.

Uma suíte aprovada não comprova cobertura integral, prontidão operacional nem vantagem estatística. A instrumentação de execução registrou 5.420 de 5.829 linhas executáveis e 2.229 de 2.470 ramos nos 23 módulos exigidos: 92,17% na métrica combinada do `coverage`, com 409 linhas e 241 ramos sem registro de execução. Doze dos 23 módulos atingiram 100% combinado; o operador registrou 73,80% e o red team contínuo 52,40%. Não foram adicionadas exclusões para melhorar a porcentagem.

Os dados medidos vieram dos quatro lotes completos de `ba8c004`, que ainda tinham as três falhas de portabilidade; seus códigos de saída constam no recibo de cobertura. A união utilizou os dados reais de linhas e arcos, remapeou somente as raízes dos clones e verificou o hash normalizado de todos os 23 fontes. A correção posterior de `.gitattributes` não alterou a lógica nem a impressão digital desses fontes. A instrumentação cobre os processos pytest instrumentados; processos filhos não instrumentados não são presumidos cobertos. Essa medição não demonstra os 100% exigidos pelo gate vigente.

A pré-verificação em `eb08c4d` recusou a cobertura antiga com `ValueError: current source-bound coverage required: smart_bounded_online_learning.py`. Os sete registros de autoridade permaneceram byte a byte iguais após a recusa. Não houve renovação de `CONSTRUCTION_PROVEN` baseada nesses relatórios. A cobertura integral vigente e uma nova certificação operacional permanecem pendentes; o código corrigido recusa a promoção com a prova antiga.

Um replay isolado da cobertura realmente medida, com os 23 hashes de fonte corretos, foi recusado antes de qualquer escrita por `incomplete line/branch coverage: smart_sequential_prospective_proof.py`. O verificador de certificação também recusou o certificado anterior com `SMART product certification is stale for current code`. Os critérios de 100% de cobertura e de certificação atual foram preservados.

O estado científico continua `UNPROVEN_PROSPECTIVE_6_OF_6`. O histórico F11/P06 não foi reinterpretado como superioridade prospectiva. Não se declara `MISSION_PROVEN` ou 6/6 a partir da aprovação do código.

No conjunto histórico de avaliação de P06, o Brier médio do candidato é `0,09001357670052432`, contra `0,08999999999999989` da distribuição uniforme; a diferença observada é `+0,000013576700524431384`. O registro preservado reprova sua promoção preditiva. Não se atribui ganho estatístico às correções desta auditoria.

## Evidência

`RAW_EVIDENCE.tar.gz` preserva JUnit e logs brutos, relatórios de cobertura, dados de linhas e arcos, inventários, planos de divisão, provas negativas, recibos e os registros recebidos da `main`. `EVIDENCE.json` registra o SHA-256 do pacote, o hash de cada arquivo descompactado, a revisão correspondente e os estados terminais reais dos comandos. `EXECUTION.json` e `COVERAGE_SUMMARY.json` apresentam os resultados principais sem exigir descompactação.

O pacote mantém os relatórios brutos inconsistentes e as execuções reprovadas. Somente os agregados explicitamente descritos acima têm contadores recalculados após conferência do inventário e dos resultados reais. Nenhum PASS histórico, teste interrompido ou subteste não representado foi usado para criar casos fictícios.
