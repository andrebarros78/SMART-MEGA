# SMART-MEGA — continuidade canônica atual

Autoridade e moradia permanente únicas: GitHub `andrebarros78/SMART-MEGA`, branch `main`. O root de execução é o Git top-level do checkout atual; hostname e caminho históricos não são requisitos.

Leia primeiro a [baseline GitHub-native](SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md). O objetivo permanece concluir e operar o produto preditivo existente, com captação, interpretação, pesos, calibração, aprendizado e robustez comprovados. Planos e anexos históricos estão subordinados às ordens atuais e ao código vivo de main.

## Autoridades reais

- Construção atual: [SMART_PRODUCT_CERTIFICATION.json](SMART_PRODUCT_CERTIFICATION.json). A fonte efetivamente testada, a execução real, o fingerprint e os resultados de regressão estão vinculados em [SMART_CANONICAL_ROOT.json](SMART_CANONICAL_ROOT.json) e [SMART_AUDIT_JUNIT_CURRENT.xml](SMART_AUDIT_JUNIT_CURRENT.xml). Conferir esses arquivos; números de snapshots antigos não descrevem a versão atual.
- Operação real: [SMART_OPERATIONAL_LIFECYCLE.json](SMART_OPERATIONAL_LIFECYCLE.json) em FROZEN para 3067; [SMART_ACTIVE_EPOCH.json](SMART_ACTIVE_EPOCH.json) identifica o epoch `operator-3067-e305750ba8e6-20261006T010444976861Z`, cutoff 3066, resultado não utilizado.
- Cartão principal 3067: [SMART_3067_PRIMARY_CARD.json](runtime/learning_epochs/operator-3067-e305750ba8e6-20261006T010444976861Z/SMART_3067_PRIMARY_CARD.json), dezenas **10, 11, 27, 35, 38, 53**. SHA-256 dos bytes: `e253f955d725aae7b6c069b312116b974a40cab00e023985f6b95f9b57ae880f`.
- Geração produtiva: [FULL_PROCESS_PROOF.json](runtime/learning_epochs/operator-3067-e305750ba8e6-20261006T010444976861Z/FULL_PROCESS_PROOF.json), PASS, 24 verificações causais. Preparação, autorização e freeze foram persistidos por execuções reais do Actions; a geração original usou o certificado semântico `e305750ba8e653ceda070f85220deeec85eab7169bdb528a97e424cf9a6f23ab`.
- Ciência: [SMART_MISSION_STATUS.json](SMART_MISSION_STATUS.json) permanece MISSION_ACTIVE, UNPROVEN / INSUFFICIENT_EVIDENCE. Confiança do cartão: LOW / UNPROVEN_PROSPECTIVE, sem probabilidade calibrada ou garantia de seis acertos. Aprovação de engenharia não comprova vantagem prospectiva.
- Fechamento 1: [evidências reconciliadas e validação anterior ao registro Git](release_evidence/FECHAMENTO_1_20261006/PRE_COMMIT_VALIDATION.json). A tag anotada deste fechamento vincula o estado final publicado às verificações posteriores de certificação, integração, recuperação e limpeza.

## Operação e preservação

Consultar `python -E -B -X utf8 smart_operator.py status` e resolver o contrato atual: FROZEN, `generation_proof_valid=True`, modo ORIGINAL_FULL_PROCESS_PROOF. Não preparar, reautorizar ou reconstruir o cartão 3067. A autorização manual de geração já foi consumida pelo freeze válido.

Preflight é a consulta de preparação de um epoch ainda não congelado; suas condições RESET_READY não constituem prova de prontidão do cartão já FROZEN. Para 3067, conferir status/startup, contrato do epoch, provas originais e hashes preservados.

Aguardar o resultado oficial verificável de 3067, previsto para 06/10/2026 às 21h de Brasília conforme a autoridade de calendário do epoch. Depois, adjudicar o freeze original, medir/calibrar, aprender e seguir o ciclo autorizado. Nunca fornecer resultado fictício à operação real ou criar previsão retrospectiva.

Uma renovação de certificação prova o código atual e não substitui a proveniência histórica da geração congelada. O certificado e a integridade global usados na geração foram preservados nas evidências deste fechamento; active epoch, cartão, freeze, ledger e prova causal permanecem imutáveis.

## Retomada e limites

O PC Escola e a execução federada estão autorizados para executar diretamente este repositório. Persistir no GitHub e conferir o commit remoto antes de considerar uma mudança canônica. Não importar código, configuração ou segredos de outros projetos. Os nove agentes existentes são executores determinísticos de papéis nativos, com 41 capacidades contabilizadas; isso não comprova nove LLMs nem execução de SDKs externos em quarentena.

[Auditoria de 05/10](SMART_AUDIT_HANDOFF_2026-10-05.md), [inventário de 05/10](SMART_AUDIT_COMPONENTS_2026-10-05.md) e a fixture sintética anterior são registros históricos. Seus 1.053 testes e o HOLD anterior à preparação de 3067 não substituem as autoridades atuais. O [SBOM atual](SMART_DEPENDENCY_SBOM_R3.json) acompanha o lock vigente; os SBOMs G07 e RAG+Excel 3059 preservam as versões e os hashes das respectivas provas históricas.

Fechamento obrigatório: RECONCILIAR → VALIDAR → CONSOLIDAR → FECHAR → VERSIONAR → PROVAR → SELAR. Corrigir e retestar falhas antes de git add/commit. Para recuperar um checkout Windows com arquivos históricos longos, utilizar a opção Git `core.longpaths=true` apenas no meio de execução. Exigir árvore limpa, funcionamento, integração, persistência, recuperação e integridade; commit isolado não autoriza MISSION_PROVEN ou selo de escopo.
