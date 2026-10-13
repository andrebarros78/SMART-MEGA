# SMART-MEGA V6 — Contrato de execução e integração

## Identidade e autoridade
- Contrato executável: SMART_AGENT_SKILL_EXECUTION_CONTRACT.json (SMART_AGENT_SKILL_EXECUTION_CONTRACT_V1), verificado por SHA-256, sem dependência de LLM.
- Operador smart_operator é a autoridade de ciclo: autorização, preparo, janela temporal, congelamento, adjudicação e histórico.
- Toda execução exige epoch_id, target_contest, cutoff_contest, data_sha256. O alvo é o corte acrescido de um concurso.
- Agentes, skills e consumidor não podem alterar pesos, probabilidades, seleção, promoção ou congelamento.

## Interfaces produtor → consumidor
1. PRE_FREEZE_TOTAL_INTEGRATION.json deve ser PASS e provar 9 executores nativos, 41 capacidades registradas, 37 aliases efetivamente invocados e 4 capacidades em quarentena. Handoffs devem ser consumidos exatamente uma vez.
2. bind_consumer_execution valida contrato estático, hashes, diretório do epoch, fase, ordem dos agentes, ausência de LLM e identidade do ciclo, produzindo recibo com hash.
3. Qualquer falha antes do congelamento impede o início do freeze.
4. Após freeze, POST_FREEZE_TOTAL_INTEGRATION.json deve satisfazer as mesmas regras para autorizar a emissão da prova final. Falha pós-freeze não permite retroagir, repetir ou substituir o cartão.
5. FULL_PROCESS_PROOF.json vincula ambos os recibos ao contrato, ao ciclo, aos hashes das provas e ao cartão congelado.

## Execução e limites
- Nove agentes são executores determinísticos; não constituem por si mesmos agentes LLM autônomos.
- Trinta e sete capacidades executam probes nativos como aliases metodológicos; não há presunção de execução de bibliotecas externas específicas.
- Quatro capacidades são não acionáveis e mantidas em quarentena.
- Handoffs são tipados por Pydantic, com produtor, consumidor, sequência, conteúdo e integridade.
- Provedores LLM externos, execução de código externo e autoridade de pesos ou freeze são rejeitados.
- A calibração possui prazo máximo, progresso atômico, aborta falhas e não aceita autoridade parcial.
- Aprendizado visual é registrado apenas como observação, sem influência numérica não comprovada.

## Fechamento, segurança e regressão
- F05/F10, testes específicos e regressão integral devem corresponder ao HEAD atual, em checkout limpo.
- O código produtivo só pode receber a alteração após recertificação atualizada; prova antiga não é válida.
- O objetivo científico de 6/6 é independente e exige evidência prospectiva.
- Em falha pós-freeze, preservar artifacts/ledger e registrar a deficiência, sem repetir o freeze.
- Ciclos históricos encerrados e seus hashes permanecem imutáveis.
