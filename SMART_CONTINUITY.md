# SMART-MEGA — continuidade canônica atual

Autoridade: GitHub `andrebarros78/SMART-MEGA`, branch `main`. Root local é o Git top-level do checkout; hostname/path históricos não são requisito.

Leia primeiro [baseline GitHub-native](SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md), [retomada e evidências](SMART_AUDIT_HANDOFF_2026-10-05.md) e [inventário](SMART_AUDIT_COMPONENTS_2026-10-05.md). Este documento substitui o snapshot desatualizado de setembro.

## Autoridades reais

- Construção: `SMART_PRODUCT_CERTIFICATION.json`, com fonte/fingerprint/JUnit vinculados em `SMART_CANONICAL_ROOT.json`.
- Execução federada de 05/10/2026: `SMART_FEDERATED_EXECUTION_2026-10-05.json`; Python 3.13.15, 989 testes aprovados, startup OK. Não é um run do GitHub Actions.
- Operação: `SMART_OPERATIONAL_LIFECYCLE.json` e `SMART_NEXT_CYCLE_HOLD.json`. Snapshot observado: HOLD, histórico até 3066, próximo target 3067, sem epoch ativo.
- Ciência: `SMART_MISSION_STATUS.json`. UNPROVEN / INSUFFICIENT_EVIDENCE permanece separado da construção do software.

## Operação

`python smart_operator.py status` e `python smart_operator.py preflight --target 3067` são consultas. Preparação/geração exigem autorização explícita e validação do alvo futuro; a base precisa estar completa até N-1. Nunca gerar cartão retrospectivo para um resultado conhecido.

O PC Escola e a rede federada foram autorizados para executar diretamente este repositório quando o Actions estiver indisponível. Persistir no GitHub e conferir o commit remoto antes de considerar mudança local canônica. Não copiar código/config/segredos de outros projetos.

## Retomada

Conferir main e as autoridades atuais antes de agir. O relatório registra o que já passou e o que está NÃO VERIFICADO. Não reiniciar ingestão já concluída, não reconstruir freeze histórico e não declarar vantagem preditiva sem prova prospectiva.
