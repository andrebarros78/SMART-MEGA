# SMART-MEGA — continuidade canônica atual

Autoridade e moradia permanente únicas: GitHub `andrebarros78/SMART-MEGA`, branch `main`. Root de execução local é o Git top-level do checkout atual; hostname/path históricos não são requisito.

Leia primeiro [baseline GitHub-native, §11](SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md), [correções e evidências atuais](SMART_AUDIT_HANDOFF_2026-10-05.md) e [inventário](SMART_AUDIT_COMPONENTS_2026-10-05.md). O objetivo é concluir o produto preditivo existente, corrigindo captação, interpretação, pesos, calibração, aprendizado, robustez e seu fluxo completo. Planos/anexos antigos estão subordinados às ordens atuais.

## Autoridades reais

- Construção: `SMART_PRODUCT_CERTIFICATION.json`, com fonte/fingerprint/JUnit vinculados em `SMART_CANONICAL_ROOT.json`.
- Fonte atual testada: `3b3dfb52da1f7ebdffcc3a503496f6c32ae851d2`; Python 3.13.15, **1.053 testes aprovados**, startup **OK**. [Execução federada real](SMART_STATE_ARCHIVE/DEEP_REPAIR_20261005/SMART_DEEP_REPAIR_EXECUTION.json), UUID d195eea4-555f-4bdb-a505-b1e619da31a1, PC-ESCOLA. Não é um run do Actions.
- [Ciclo integrado PASS](SMART_STATE_ARCHIVE/DEEP_REPAIR_20261005/SMART_FULL_CYCLE_FIXTURE.json): geração, cartão persistido, freeze/replay, resultado sintético, adjudicação, aprendizado, avanço e previsão seguinte; funções centrais reais. Fixture TEST_ONLY não tem autoridade produtiva/científica.
- Operação: `SMART_OPERATIONAL_LIFECYCLE.json` e `SMART_NEXT_CYCLE_HOLD.json`. HOLD, histórico oficial até 3066, próximo target 3067, sem epoch ativo. [Status/preflight sem mutação](SMART_STATE_ARCHIVE/DEEP_REPAIR_20261005/SMART_OPERATIONAL_VERIFICATION.json).
- Ciência: `SMART_MISSION_STATUS.json`: MISSION_ACTIVE, UNPROVEN / INSUFFICIENT_EVIDENCE. Construção aprovada não comprova vantagem prospectiva.
- [Entrega em main verificada](SMART_STATE_ARCHIVE/DEEP_REPAIR_20261005/SMART_DELIVERY_VERIFICATION.json): commit cee2b12d172f02c03b9e9ec97aa2c782b796e24e obtido do remoto, árvore inicialmente limpa, status OK e preflight HOLD sem mutação. A persistência posterior desta prova altera somente evidência/documentação, preservando o código da fonte testada.

## Operação

`python smart_operator.py status` e `python smart_operator.py preflight --target 3067` são consultas. Preparação/geração exigem autorização explícita e validação do alvo futuro; a base precisa estar completa até N-1. Nunca gerar cartão retrospectivo para resultado conhecido.

O PC Escola e a rede federada foram autorizados para executar diretamente este repositório quando o Actions estiver indisponível. Persistir no GitHub e conferir o commit remoto antes de considerar mudança local canônica. Não copiar código/config/segredos de outros projetos. Agentes/skills adicionais entram para uma lacuna real indispensável; o ecossistema existente tem nove executores determinísticos e 41 capacidades contabilizadas.

## Retomada

Conferir main e autoridades atuais antes de agir. Documentação/evidências posteriores à fonte testada são válidas somente com fingerprint de código preservado e fonte ancestral. O relatório distingue provas atuais, registros históricos e entradas auxiliares NÃO VERIFICADAS. Não reiniciar ingestão concluída, reconstruir freeze histórico nem declarar vantagem/MISSION_PROVEN sem prova prospectiva.
