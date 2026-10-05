# SMART-MEGA V6 — auditoria e retomada — 05/10/2026

**Construção: CONSTRUCTION_PROVEN. Núcleo operacional e persistência em checkout novo verificados.** A ciência continua UNPROVEN / INSUFFICIENT_EVIDENCE; nenhuma garantia de acerto.

## Produto e cartão

Produto Python/CLI experimental para o operador gerar prospectivamente um jogo de Mega-Sena: seis dezenas distintas de 1 a 60. Histórico oficial validado → Champion/Challenger → scores congelados → portfólio/seletor → cartão principal. O processo completo persiste `runtime/learning_epochs/<epoch>/SMART_<concurso>_PRIMARY_CARD.json`; o operador consome/devolve o cartão e a adjudicação registra o resultado. O portfólio é auxiliar.

Stack: Python 3.13, NumPy/pandas, River, estatística e OR-Tools; batch, sem aplicação HTTP identificada. Persistência operacional XLSX/JSON, ledger, CAS/journal/locks e commits no GitHub. SQLite/MLflow é auxiliar. Autoridade única: `andrebarros78/SMART-MEGA`, `main`. A execução federada foi explicitamente autorizada em 05/10/2026 e reconciliada na baseline; nenhum código/config/segredo de outro projeto foi importado.

## Defeitos encontrados → correções → evidências

| ID / severidade | Arquivo:linha / causa | Correção | Evidência |
|---|---|---|---|
| D01 bloqueante | `smart_github_operator.py:240`: CRLF histórico rejeitado como espaço final | `f96aab6`: aceitar terminador CRLF sem aceitar trailing space | Git bare, push e clone com bytes LF/CRLF; espaço real rejeitado |
| D02 alto | `smart_primary_card_selector.py:41,90`: pesos/objetivo NaN/inf | `f96aab6`: validação finita | testes de configuração/overflow PASS |
| D03 alto | `smart_primary_card_selector.py:105`: fallback retornava cartão inviável | `f96aab6`: erro claro, sem cartão inventado | inviabilidade rejeitada |
| D04 alto | `smart_primary_card_selector.py:45`: bool/fração aceitos como dezena | `f96aab6`: inteiro estrito | entradas inválidas rejeitadas |
| D05 alto | `smart_primary_card_selector.py:57`: colisão de chaves normalizadas | `f96aab6`: rejeitar duplicação | teste dedicado PASS |
| D06 médio | `smart_primary_card_selector.py:99`: limite ímpar do pool não tentado | `f96aab6`: incluir limite exato | teste dedicado PASS |
| D07 médio | `smart_github_operator.py:59,66,211`: subprocessos sem limite | `f96aab6`: Git 60 s / operação 4.800 s | teste de timeout PASS |
| D08 médio | `smart_github_operator.py:279`: erro sem contrato | `f96aab6`: `{erro, causa, acao_sugerida}` | teste e resposta real de falha Windows |
| D09 alto | `smart_full_process_pipeline.py:58`: cartão/resposta sem run_id | PR #21 / fonte testada `6262cdc`: persistir/devolver identidade e UTC | E2E persistido e consumidor validado |
| D10 alto | `smart_full_process_pipeline.py:58`: confiança ausente | PR #21: LOW, UNPROVEN_PROSPECTIVE, calibrated:false, garantia:false | E2E e rejeição de confiança fabricada |
| D11 médio | E2Es anteriores substituíam etapas essenciais | `test_smart_signal_agent.py`: núcleo real + histórico de 120 sorteios | cartão, replay, resultado e Brier PASS |
| D12 bloqueante operacional | lifecycle/dados parados em 3062 | `47137a4`: recuperar resultados até 3066 sem previsão retrospectiva | workflow 37366096200 SUCCESS; HOLD 3067 e hashes persistidos |
| D13 bloqueante da execução federada | `smart_github_certify.py:33` / `smart_product_certification.py:107`: exigência exclusiva de run do Actions | `7ac7fb0`: executor real + UUID/host/origin; ci_run_id nulo | 10 testes de proveniência e certificação real PASS |
| D14 bloqueante Windows | `smart_github_operator.py:206`: C:/ comparado literalmente com C:\\ | `6f54d88`: comparar Paths resolvidos | falha original reproduzida; três testes Git corrigidos |
| D15 alto | `smart_repository_integrity.py:235`: exigia epoch FROZEN mesmo em HOLD válido | `6262cdc`: reconciliar lifecycle; preservar validação estrita de freeze | HOLD sem mutação PASS; ausência/tampering/dataset incoerente rejeitados |
| D16 médio documental | `SMART_CONTINUITY.md:3`: snapshot de setembro, path fixo e 863 testes | continuidade remete às autoridades atuais e ao relatório | texto atualizado / checkout novo PASS |
| D17 médio / pendente auxiliar | smart_procedural_coverage_gate.py:20: manifesto CRONOGRAM_ARCHIVE_MANIFEST.json ausente no checkout; traceback sem erro padronizado | NÃO CORRIGIDO: dados não inventados; rotina procedural não é fonte obrigatória do cartão principal | execução real exit 1 / 0,301 s; stack em SMART_AUXILIARY_EXECUTION_2026-10-05.json |
| EX01 externo | runners do GitHub não adquiridos | execução direta autorizada no PC Escola | 989 testes e certificação fora do Actions |

## Verificação

- Primeiro run federado, fonte f1e663c: **980 passed / 4 failed**, 448,06 s; duas causas corrigidas em commits separados. [Stack traces originais](SMART_AUDIT_DISCOVERY_2026-10-05.xml.gz).
- Correções focadas: **25 passed**, 16,36 s.
- Fonte final testada: `6262cdcbd5be7a5ca73bcfc01c4d2e70868a93d2`; **989 passed / zero failures/errors/skips**, 399,97 s. Os 29 warnings são de propriedades JUnit/record_property; não foram contabilizados como testes falhos.
- Python 3.13.15, ambiente separado, dependências do `requirements.lock.txt`; `pip check`: sem dependências quebradas.
- JUnit SHA256: `1113b93a34252f36ae3409c6424571fdd7a45b1b5e76bea9aae2f03bebba9a75`.
- Execução: `FEDERATED_PC / PC-ESCOLA / 43309a8a-0b91-40d4-b415-b712f45448f2`. Certificação CONSTRUCTION_PROVEN, governança e integridade global válidas; startup **OK**.
- E2E com fixture realista: target 121, cartão **12, 18, 27, 29, 39, 50**; run_id `fixture-121`; 60 probabilidades finitas em [0,1], soma 6; replay sem alteração; resultado **4, 13, 22, 31, 40, 59**; zero acertos do cartão; **Brier 0,09**, baseline uniforme 0,09; resultado duplicado rejeitado sem mutação. Isso prova fluxo, não vantagem preditiva.
- [Evidência detalhada com entrada/saída/status/tempo dos 28 CLI](SMART_FEDERATED_EXECUTION_2026-10-05.json), [JUnit](SMART_AUDIT_JUNIT_CURRENT.xml) e [inventário completo](SMART_AUDIT_COMPONENTS_2026-10-05.md).
- Produção canônica: resultados oficiais até 3066, HOLD 3067; recuperação não criou cartão/freeze/autoridade retrospectiva. Dataset SHA256 `107da17eb2ba8e6d412dbfb1916540d1d715139fef076552229e81abd55301f4`.
- **Checkout novo / persistência após reinício: PASS** no commit 229b399. Artefatos e dataset com hashes idênticos, árvore limpa; status OK (40,32 s); preflight 3067 AWAITING_OPERATOR_AUTHORIZATION (51,68 s). Não há servidor web a reiniciar. [Prova](SMART_RESTORE_VERIFICATION_2026-10-05.json).

## Decisões e limites

Probabilidades de inclusão de seis dezenas somam **6**; pesos da mistura somam **1**. Confiança desconhecida fica LOW/UNPROVEN, sem percentual inventado. Fixture temporal marcada TEST_ONLY não promove previsão retrospectiva a produção. Main prevalece sobre anexos e documentos históricos. Preservados registros, bytes históricos e a tag `pre-correcao-20261005`. Não foi criado registro paralelo de agentes/skills: nove executores determinísticos, 37 aliases nativos e quatro fontes em quarentena validada; não são nove agentes LLM externos.

Encontrados 70 arquivos com entrada executável: 28 parsers testados com --help e 42 scripts sem parser. O inventário distingue execução direta de cobertura funcional. Entradas auxiliares/históricas não exercitadas diretamente estão **NÃO VERIFICADAS**; não foram ativadas arbitrariamente nem usadas para alegar operação total.

## Pendências e continuidade

Sem nova chave, compra ou autorização de acesso necessária para este fechamento técnico. O próximo concurso permanece em HOLD e exige comando explícito de aplicar/gerar; não foi selecionado silenciosamente.

1. Ler main e os arquivos de autoridade atuais: checkout novo, hashes, startup, status e preflight já foram verificados; não repetir recuperação concluída.
2. Conferir commit remoto e a correspondência do fingerprint com a fonte testada antes de qualquer nova alteração.
3. Atualizar o estado acima somente com a prova observada; não usar certificados antigos como prova de alteração nova.
4. Para auditoria exaustiva das 42 entradas auxiliares, usar o inventário e seus contratos/fixtures; ausência de execução direta continua explícita.

## Continuação após integração em main

PR #21 MERGED; main confirmado em 23594f8c417c22f96950c15541cd9a5f4413f869. Dez auxiliares foram executados em clones isolados desse commit: oito exit 0; __main__ do certificador rejeitou a ausência de proveniência Actions (esperado, sem fabricar run); gate procedural falhou por manifesto ausente. Entrada, saída, tempo e stack persistidos em [prova auxiliar](SMART_AUXILIARY_EXECUTION_2026-10-05.json). Restam 32 entradas diretas sem execução. Os 989 testes e a certificação do núcleo permanecem relativos à mesma fonte; esta continuação só acrescenta evidência/documentação, sem trocar código ou dados operacionais. D17 é pendência interna da auditoria auxiliar, não pedido de chave/acesso ao usuário.
