# SMART-MEGA — ingestão de resultado em uma execução

Ingestão de **dados** não é lançamento de versão de **código**. Não executar
novamente a regressão integral de construção, nem reinstalar dependências,
a cada concurso. A fonte autenticada e a cadeia de evidências permanecem obrigatórias.

Em um checkout isolado e autenticado da branch canônica, registrar o lote local
com proveniência verificada (CAIXA transcrita não é CAIXA API autenticada):

    python smart_fast_result_ingest.py --target NUM --payload-file SMART_RESULT_BATCH_NUM.json
    python smart_fast_result_ingest.py --target NUM --payload-file SMART_RESULT_BATCH_NUM.json --apply

A primeira execução não altera arquivos. A segunda faz, no mesmo processo:
validar lote e concurso; se necessário registrar/encerrar o último ciclo
congelado usando o operador existente; aplicar `catch-up` sequencial;
comprovar HOLD no concurso seguinte, sem congelar novo cartão ou ajustar pesos.

Quando o mesmo resultado já foi ingerido, o comando verifica hashes e responde
ALREADY_INGESTED sem escrever. Se faltar resultado anterior, houver erro de
integridade ou falta de autorização, falhar explicitamente em vez de refazer
instalações, escolher outro PC, executar Actions ou iniciar novos ensaios.

Para publicar: usar uma única branch operacional e uma PR autenticada com o lote
e todos os artefatos de auditoria. Nunca executar push diretamente na main
protegida. Se a autenticação de push falhar, reportar PUBLICATION_AUTH_BLOCKED
imediatamente, preservando o estado local e os recibos. Não fragmentar bundles
manualmente enquanto houver conector Git autenticado disponível.

Testes por sorteio: validar resultado, duplicidade, hashes, cadeia temporal,
recuperação e leitura de histórico. Homologação integral é exigida para alterações
materiais de código, não para a simples adição de uma linha de resultado.

Prova científica de 6/6 e aprendizagem prospectiva não são concedidas por uma
ingestão de resultado conhecido.
