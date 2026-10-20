# SMART-MEGA V6 — executor de homologação Linux sem GitHub Actions

**Data:** 20/10/2026, horário de Brasília. **Escopo:** PR #67, sem alterações na `main`. **Executor:** VPS Linux `wmcp-cloud-01`, via missão LMCP persistente `m_82f9822ffb5f403594217eb18eb8aa9f`.

## Decisão de arquitetura

A CI não depende mais de um job do GitHub Actions para rodar os gates disponíveis. Foi criado `smart_linux_ci.py`, uma entrada independente com os modos:

- `python3 smart_linux_ci.py --profile focused`: executa os testes direcionados do projeto, verifica todos os arquivos Python versionados e produz recibo imutável (create-only) com SHA-256.
- `python3 smart_linux_ci.py --profile full --certify`: verifica **todos** os pacotes e versões do `requirements.lock.txt` antes de executar o **runner original `smart_regression_runner.run_regression`**. Se aprovado, chama a certificação existente por `smart_github_certify.refresh`, identificando explicitamente o host como `LMCP_LINUX_VPS` e sem fingir que o resultado veio de GitHub Actions ou de outro PC.

O arquivo de certificação `smart_product_certification.py` foi estendido para validar a nova identidade `LMCP_LINUX_VPS` de forma estrita, mantendo a compatibilidade com `GITHUB_ACTIONS` e `FEDERATED_PC`. A identidade Linux só é aceita para o host canônico `wmcp-cloud-01` e um UUID legítimo da execução, vinculada ao commit, fingerprint e JUnit original.

**Proteções:** código de origem GitHub canônico, worktree isolada, Git limpo, não autenticar/instalar dependências por via alternativa, sem criação de certificação científica 6/6, sem promoção de código ou alteração dos resultados produtivos.

## Evidência de execução real

Fonte exata testada: `683c16523d397a4c6bea62e3e4e40bd8f562eeae`.

| Gate | Resultado | Prova |
|---|---|---|
| Perfil direcionado Linux | **PASS, 56 testes** | Recibo SHA `d71a3cc467da8d5685a89f366639140687bf63cd0e61b26d76aadab3158920b3` |
| Análise sintática dos arquivos Python versionados | **PASS, 518 arquivos** | Mesmo recibo |
| Proveniência de certificação Linux e preservação do perfil PC | **4 testes PASS** incluídos nos 56 | `test_smart_linux_certification_provenance.py` |
| Perfil completo e certificação | **BLOCKED_DEPENDENCIES, 0 testes executados** | Recibo SHA `57c7abc9b9f85f6f504f33d130a392b9b1a9b4f16952725a8deed162233a880e` |
| Dependências exatas do lock | **75 exigidas; 1 presente; 74 indisponíveis** no Python isolado | Mesmo recibo de bloqueio |
| Homologação total e `MISSION_PROVEN` | **NÃO COMPROVADAS** | Gate fail-closed |

Recibos íntegros versionados no GitHub:

- `release_evidence/ci_linux/SMART_LINUX_CI_focused_0e26afcf808f48ce836eca6d19484645.json`
- `release_evidence/ci_linux/SMART_LINUX_CI_full_5462cda862b744a684a115bae1c7723d.json`

O GitHub Actions não é necessário para usar os novos comandos. Todavia, a política do executor LMCP recusou a instalação dessas dependências com `installation_requires_signed_typed_admin_operation`; a rota tipada retornou `admin_operation_not_allowed`. A solicitação de capacidade governada `capreq_68e0d83804ad4d7d895f7371b2a715ef` foi aberta e não houve confirmação de aprovação. **Não contornar a política com pip alternativo, Docker não autorizado, outro PC ou pacotes de outros projetos.**

## Critério seguinte

Liberar formalmente um runtime Python de testes **isolado, com as 75 dependências travadas**, seguindo as políticas LMCP; executar o perfil completo com `--certify`; verificar contagem real do JUnit, certificado, integridade e não regressão. **Até isso acontecer: manter PR #67 em draft e `main` protegida.**

A conclusão do pós-resultado 3071 e a geração preditiva oficial do 3072 são gates operacionais separados e ainda não foram provados por este trabalho de CI.

**Status terminal:** `LINUX_CI_FOCUSED_PASS_FULL_CERTIFICATION_BLOCKED_DEPENDENCIES`.
