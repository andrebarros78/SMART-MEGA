# SMART-MEGA V6 — auditoria e retomada — 05/10/2026

**Construção: CONSTRUCTION_PROVEN; 1.053 testes aprovados; ciclo preditivo integrado PASS; startup OK.** A missão científica continua MISSION_ACTIVE, UNPROVEN / INSUFFICIENT_EVIDENCE. A execução sintética não comprova vantagem prospectiva.

## Ordens reconciliadas e produto

Autoridade e moradia permanente únicas: GitHub `andrebarros78/SMART-MEGA`, branch `main`. Um checkout local serve à execução e seu root é o Git top-level; não existe requisito de residência em `C:\SMART-MEGA` ou de hostname fixo. [Baseline, §11](SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md) registra o objetivo executivo: corrigir profundamente o produto existente e comprovar captação, interpretação, pesos, calibração, aprendizado, robustez e resultado do fluxo. Anexos e planos antigos não substituem o código vivo e as ordens atuais.

Produto Python/CLI experimental: histórico validado → Champion/Challenger → scores congelados → portfólio/seletor → cartão principal de seis dezenas distintas de 1 a 60 → resultado → medição/calibração → aprendizado → previsão seguinte. O processo persiste `runtime/learning_epochs/<epoch>/SMART_<concurso>_PRIMARY_CARD.json`, com run_id e confiança LOW/UNPROVEN; o portfólio é auxiliar.

Stack existente: Python 3.13, NumPy/pandas, River, estatística e OR-Tools; batch, sem servidor HTTP identificado. XLSX/JSON, ledger append-only, CAS/journal/locks e GitHub. SQLite/MLflow é auxiliar. A execução federada no PC Escola foi autorizada em 05/10/2026. Nenhum código/config/segredo de outro projeto foi importado. Foram usadas as skills de engenharia responsável e loop de correção; o ecossistema existente foi executado, sem aquisição externa sem lacuna técnica.

## Defeitos encontrados → correções → evidências

As linhas D01–D16 preservam as correções da rodada anterior. D17–D21 e a fonte `3b3dfb5` correspondem à continuação profunda atual.

| ID / severidade | Causa | Correção | Evidência |
|---|---|---|---|
| D01 bloqueante | wrapper Git rejeitava CRLF histórico como espaço final | `f96aab6`: aceitar CRLF e rejeitar trailing space real | Git bare, push/clone LF/CRLF e rejeição de espaço |
| D02 alto | seletor aceitava pesos/objetivo NaN/inf | `f96aab6`: validação finita | configuração/overflow rejeitados |
| D03 alto | fallback retornava cartão inviável | `f96aab6`: falhar sem cartão inventado | teste de inviabilidade |
| D04 alto | bool/fração aceitos como dezena | `f96aab6`: inteiro estrito | entradas inválidas rejeitadas |
| D05 alto | colisão de chaves normalizadas | `f96aab6`: rejeitar duplicação | caso dedicado |
| D06 médio | limite ímpar do pool não tentado | `f96aab6`: incluir limite exato | caso dedicado |
| D07 médio | subprocessos sem limite | `f96aab6`: Git 60 s / operação 4.800 s | contrato de timeout |
| D08 médio | erro do wrapper sem contrato | `f96aab6`: erro/causa/acao_sugerida | teste e resposta Windows real |
| D09 alto | cartão/resposta sem run_id | PR #21, fonte `6262cdc`: identidade/UTC persistidos | E2E e consumidor; revalidados nesta rodada |
| D10 alto | confiança ausente | PR #21: LOW, UNPROVEN_PROSPECTIVE, calibrated:false, garantia:false | confiança fabricada rejeitada |
| D11 médio | E2Es substituíam etapas essenciais | núcleo real e histórico sintético; agora também processo completo externo | prova integrada abaixo, sem mocks das funções centrais |
| D12 bloqueante operacional | lifecycle/dados parados em 3062 | `47137a4`: recuperação até 3066 sem previsão retrospectiva | workflow 37366096200 SUCCESS; HOLD 3067 preservado |
| D13 bloqueante federado | certificação exigia exclusivamente Actions | `7ac7fb0`: UUID, host e origem reais; ci_run_id nulo | proveniência federada e certificação verificadas |
| D14 bloqueante Windows | comparação literal C:/ versus C:\\ | `6f54d88`: Paths resolvidos | reprodução original e testes Git |
| D15 alto | integridade exigia epoch FROZEN em HOLD válido | `6262cdc`: reconciliar lifecycle mantendo validação do freeze | HOLD válido e entradas adulteradas distinguidos |
| D16 médio documental | continuidade com snapshot/path/números antigos | baseline/continuidade/inventário atualizados | GitHub único e fontes atuais identificadas |
| D17 médio | CLI procedural lançava traceback por manifesto ausente | `3b3dfb5`: resposta BLOCKED_MISSING_INPUT/INVALID_INPUT, exit 1 e bloqueio preditivo | antes 2 failed/1 passed; depois 3 passed; resposta real estruturada sem stderr |
| D18 alto | fatores NaN/inf e massa de pesos em overflow contaminavam normalização | `0130f82`: rejeitar fatores/produtos/massa inválidos antes do ajuste | antes 21 failed/1 passed; família corrigida 72 passed; 22 novos casos |
| D19 alto | coerção de resultados/hits/ranking truncava frações, aceitava bool/string ou ocultava cardinalidade inválida | `4436784`: reutilizar inteiro estrito e validar antes de aprender | antes 19 failed/12 passed; família corrigida 63 passed; 31 novos casos |
| D20 alto | auditoria científica convertia 6,9 em 6 hits e truncava concurso/cutoff | `e8816c3`: contagens e identificadores integrais estritos | antes 4 failed; família corrigida 13 passed; 4 novos casos |
| D21 alto | replay de freeze e recuperação FREEZING usavam _resolve/_rel sem importação | `66cf0c1`: importar os helpers existentes | antes 4 failed/NameError; família corrigida 27 passed; 4 casos reais de CAS, replay e adulteração |
| EX01 externo | runners do GitHub indisponíveis na rodada anterior | execução federada autorizada | 1.053 testes, UUID/host reais; nenhum run Actions fabricado |

## Prova atual da fonte

- Fonte testada: **`3b3dfb52da1f7ebdffcc3a503496f6c32ae851d2`**.
- Regressão: **1.053 passed; zero failures/errors/skips; 375,49 s**. Os 29 warnings de JUnit/record_property não foram contados como falhas.
- Python **3.13.15**, ambiente do próprio projeto; isolamento, lock exclusivo, fingerprint estável e CURRENT preservado durante a execução.
- Execução real: **FEDERATED_PC / PC-ESCOLA / d195eea4-555f-4bdb-a505-b1e619da31a1**; ci_run_id nulo.
- JUnit SHA256: **`d48f1365ba33bbdc06a5a517c9e8b29a5b54b1d90832e836de4f43a58ce61467`**.
- Certificação CONSTRUCTION_PROVEN SHA256: `bfcbb5dc43a33fda71343d00d795868f75d3ae415cdbb98cac255c85891fa2e8`; governança e integridade global PASS; startup **OK**.
- [Registro da regressão/certificação](SMART_STATE_ARCHIVE/DEEP_REPAIR_20261005/SMART_DEEP_REPAIR_EXECUTION.json), [JUnit atual](SMART_AUDIT_JUNIT_CURRENT.xml) e [inventário](SMART_AUDIT_COMPONENTS_2026-10-05.md).
- Commits posteriores de documentação/evidências preservam o fingerprint de código da fonte testada. A verificação exige fonte ancestral e blobs correspondentes; não trata um certificado antigo como prova de código diferente.

## Processo completo e aprendizado

[Ensaio integrado real](SMART_STATE_ARCHIVE/DEEP_REPAIR_20261005/SMART_FULL_CYCLE_FIXTURE.json), [driver reproduzível](SMART_STATE_ARCHIVE/DEEP_REPAIR_20261005/full_cycle_fixture.py) e [artefatos com hashes](SMART_STATE_ARCHIVE/DEEP_REPAIR_20261005/full_cycle_fixture_artifacts.zip).

Em uma cópia isolada do próprio projeto, com 120 sorteios sintéticos (seed 999), calendário/resultados explicitamente TEST_ONLY e módulos executados da mesma raiz dos dados, passaram: certificação atual → autorização de teste → prepare → autorização de geração de teste → run_full_process → consumo do cartão persistido → freeze idempotente → ingestão sintética → adjudicação → aprendizado/replay/prova sequencial → avanço do histórico de teste → previsão seguinte. Nenhuma função central foi substituída. A única concessão de identidade/startup foi o contrato de sandbox pytest já existente.

Todos os 24 trace_checks passaram, incluindo integração pré/pós-freeze, nove executores e contabilização das 41 capacidades. O cartão foi **12, 18, 27, 29, 39, 50**, confiança LOW/UNPROVEN. Resultado sintético **4, 13, 22, 31, 40, 59**: **zero acertos**, Brier **0,09**, igual ao uniforme **0,09**. Freeze e prefixo do ledger permaneceram intactos; aprendizado chegou a 121; previsão seguinte target 122/cutoff 121, 60 probabilidades finitas com soma **6**, pesos positivos finitos com soma **1**. Isso comprova funcionamento e causalidade do fluxo de teste, sem comprovar vantagem científica.

As descobertas anteriores estão preservadas no mesmo arquivo de evidências: cópia incompleta do registro, limite de caminho Windows, diretório de execução/importação incoerente e o defeito real D21. Os cenários falhos continuam FAIL; seus ZIPs foram verificados byte a byte. Não são apresentados como aprovação final.

## Operação real preservada

[Consultas reais da fonte atual](SMART_STATE_ARCHIVE/DEEP_REPAIR_20261005/SMART_OPERATIONAL_VERIFICATION.json): startup/status **OK**; preflight 3067 **AWAITING_OPERATOR_AUTHORIZATION**, phase OPERATOR_HOLD, mutated_state:false. Dataset, lifecycle, HOLD, missão, ledger e estado mantiveram os mesmos hashes antes/depois. Sem epoch ativo.

Histórico oficial até **3066**, dataset SHA256 `107da17eb2ba8e6d412dbfb1916540d1d715139fef076552229e81abd55301f4`. A recuperação histórica não criou previsão retrospectiva. O próximo concurso continua em HOLD e requer comando explícito de aplicar/gerar, conforme a baseline.

## Alcance, pendências e retomada

Os nove executores são funções determinísticas de papéis; os 37 aliases pertinentes chamam funções/probes nativas e quatro referências ficam em quarentena validada. Não são nove LLMs externos nem execução de todos os SDKs de terceiros.

Os 28 parsers CLI passaram em --help na regressão. Há 42 entradas auxiliares/históricas sem parser; dez foram exercitadas diretamente na rodada anterior e 32 permanecem sem execução direta. O núcleo do processo completo foi agora exercitado pela API real. O inventário distingue cobertura funcional, CLI e evidência histórica.

D17: o tratamento de falha foi corrigido. O manifesto procedural ausente continua bloqueando a promoção daquela pesquisa; dados não foram inventados. [Resposta real](SMART_STATE_ARCHIVE/DEEP_REPAIR_20261005/SMART_PROCEDURAL_DIAGNOSTIC_ENTRYPOINT.json). Nenhuma nova chave, compra ou autorização de acesso foi necessária para as correções atuais.

Para retomar: ler main, baseline §11 e autoridades atuais; conferir fonte/fingerprint/commit remoto; preservar HOLD e evidências históricas. Não repetir recuperação concluída, reconstruir freeze retrospectivo ou declarar MISSION_PROVEN sem prova prospectiva fresca. Preservada a tag `pre-correcao-20261005`; não foi criada outra cerimônia de backup/tag.

## Histórico da rodada anterior

Na conferência inicial de main b1de33e, 988 testes passaram e um falhou porque o próprio diagnóstico gravou .log em runtime, proibido pelo contrato. Os arquivos foram movidos para o arquivo de evidências e o caso de escopo passou; não foi alterado o teste para aceitá-los. [JUnit original](SMART_STATE_ARCHIVE/DEEP_REPAIR_20261005/SMART_DEEP_RECHECK_20261005.xml). A primeira regressão das correções atuais (fonte e8816c3) passou em 1.046 testes; foi substituída pelo run de 1.053 após D17/D21, mantendo o registro INITIAL e o JUnit comprimido no mesmo arquivo.

Fonte f1e663c: 980 passed/4 failed; causas corrigidas. Fonte `6262cdcbd5be7a5ca73bcfc01c4d2e70868a93d2`: 989 passed, JUnit `1113b93a34252f36ae3409c6424571fdd7a45b1b5e76bea9aae2f03bebba9a75`, execução 43309a8a-0b91-40d4-b415-b712f45448f2. PR #21 integrado; checkout novo 229b399 passou status/preflight sem mutação. Esses registros são históricos e foram substituídos pela prova atual de 1.053 testes. Preservados [descoberta original](SMART_AUDIT_DISCOVERY_2026-10-05.xml.gz), [execução anterior](SMART_FEDERATED_EXECUTION_2026-10-05.json), [restauração anterior](SMART_RESTORE_VERIFICATION_2026-10-05.json) e [auxiliares anteriores](SMART_AUXILIARY_EXECUTION_2026-10-05.json).
