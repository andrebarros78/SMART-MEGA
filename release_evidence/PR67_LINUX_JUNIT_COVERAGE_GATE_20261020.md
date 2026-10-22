# SMART-MEGA V6 — gate seguinte: cobertura JUnit imutável e homologação Linux

**Data:** 20/10/2026 (Brasília). **Escopo:** somente a PR #67 do repositório `andrebarros78/SMART-MEGA`, utilizando a VPS Linux `wmcp-cloud-01`.

## Problema adicional identificado

O executor Linux já confrontava JUnit candidato e JUnit CURRENT com o recibo do runner. Entretanto, **não exigia uma contagem mínima de testes compatível com o JUnit histórico versionado**. Assim, uma execução green de 1 teste poderia, em princípio, satisfazer a validação de consistência interna sem provar não regressão de cobertura.

## Correção implementada e testada

- `smart_linux_ci.baseline_junit_counts` lê **exclusivamente** `HEAD:SMART_AUDIT_JUNIT_CURRENT.xml` com `git show`, evitando usar uma cópia de trabalho mutável. Rejeita JUnit ausente, inválido, contendo declaração DOCTYPE/ENTITY, com falhas/erros ou contagem nula.
- O JUnit presente no commit de base registra **1.295 testes**, sem falhas, erros ou testes pulados. Essa é uma **referência histórica**, não a contagem de uma suíte reexecutada.
- `verify_full_junit` exige contagem real de testes igual ou maior que essa baseline e número de pulados não superior à baseline, além de todos os controles anteriores de integridade, hash, bloqueio de sobrescrita, identidade do runner e fonte.
- Se as dependências estiverem prontas, mas não houver JUnit de referência versionado, o executor retorna `BLOCKED_BASELINE_EVIDENCE`, sem iniciar uma homologação indevida.
- Testes RED→GREEN confirmaram que a regra não existia e agora rejeita regressão artificial de 1 vs. 1.295 testes.

## Execução comprovada

- **Checkout limpo, HEAD exato:** `61a19518ba204e126248437fd907d4315ec74086`
- **VPS:** `wmcp-cloud-01` (sem utilizar PCs Casa, Escola ou Vendas).
- `python3 smart_linux_ci.py --profile focused`: **64/64 testes aprovados**, sem necessidade de GitHub Actions.
- `ast.parse` dos **518 arquivos Python rastreados**: PASS, conforme recibo do perfil direcionado.
- `python3 smart_linux_ci.py --profile full --certify`: `BLOCKED_DEPENDENCIES`; 74 das 75 distribuições versionadas permanecem ausentes no ambiente Python isolado; nenhum teste da suíte completa executado.
- Recibos JSON versionados, auto-hash SHA-256 comprovado de forma independente:
  - `release_evidence/ci_linux/SMART_LINUX_CI_focused_55a91cd51bd64f638ef84c15df0b87bd.json` — `9fff4c7ec51d4fd21ee566b5493b33d606c44ad682f5289ae3c36b3ecb8304c3`.
  - `release_evidence/ci_linux/SMART_LINUX_CI_full_179c15c7f6d84203ab86d5a91b61b88d.json` — `c14d9376e7b8fe5640c3a0f580b6b17a48a2e29a6f84cd16f32a0b1bd9adb385`.
- O perfil completo foi **bloqueado legitimamente**, sem certificado integral falso e sem alteração na baseline produtiva.

## Autoridade externa pendente

A solicitação LMCP `capreq_68e0d83804ad4d7d895f7371b2a715ef` (`isolated_python_test_dependencies`) foi verificada novamente: `DISCOVERY_PENDING`; nenhuma liberação ou Human Gate retornado. A instalação por shell ou por outra operação administrativa previamente negada **não foi contornada**.

## Critério para conclusão de engenharia

1. Receber capacidade governada que autorize instalar os pacotes travados na venv isolada.
2. Verificar versões instaladas e executar `python3 smart_linux_ci.py --profile full --certify` no commit exato revisado, com baseline de 1.295 testes e hash/relatório JUnit novos.
3. Inspecionar certificado, governança, invariantes, regressão global e ausência de falhas; corrigir qualquer falha e retestar.
4. Somente após aprovação integral e revisão de autoridade, integrar à `main`; sem falsificar congelamentos históricos 3060/3061 nem declarar 6/6 preditivo sem prova.
5. Concluir o ciclo operacional 3071 e gerar o 3072 com as autoridades corretas; o gerador de contingência não representa previsão preditiva oficial.

**Estado final deste gate:** `FOCUSED_64_PASS_FULL_BLOCKED_DEPENDENCIES`. **MISSÃO CONTINUA**. PR #67 permanece em draft; `main` não alterada.
