# SMART-MEGA V6 — RAG + Excel 3059

## Escopo
Integração de ingestão histórica Excel e recuperação RAG auditável sobre o histórico canônico da Mega-Sena até o concurso 3059.

## Arquitetura real
`Mega-Sena.xlsx` é a fonte histórica canônica. `smart_rag_excel.py` valida a fonte, impõe `as_of_contest`, converte cada concurso em evidência com ID e proveniência, e usa `ScientificEvidenceRAG` para recuperação. O índice persistido desta baseline é `runtime/rag_excel/mega_sena_3059.jsonl`.

## Autoridade e segurança
O componente RAG é apoio de aprendizado/recuperação. Não possui autoridade para alterar pesos preditivos, freeze, geração, signal state ou learning ledger. O estado pós-resultado permanece em hold até comando explícito do operador para o próximo ciclo.

## Operação
Fonte atual: 3059 concursos, 1..3059. Último resultado: 01, 02, 07, 18, 33, 35 em 17/09/2026. Próximo alvo operacional em hold: 3060.

## Persistência e recuperação
O índice e o Excel são arquivos persistentes com SHA-256. A baseline anterior de 3058 está preservada em `SMART_STATE_ARCHIVE/RAG_EXCEL_INGEST_3059_20260919_145104/`. Restore e rollback foram testados em ambiente isolado.

## Limitações
Treinamento RAG não constitui evidência de vantagem preditiva. Nenhuma recalibração automática de pesos foi autorizada. A missão científica global do SMART-MEGA permanece separada desta selagem de escopo.

## Controles não aplicáveis
Não há banco relacional, multitenancy, serviço HTTP próprio, sessão de usuário, fila, migration, rate limit de API própria ou criptografia de transporte própria neste escopo local de arquivos/CLI; esses controles são NOT_APPLICABLE.
