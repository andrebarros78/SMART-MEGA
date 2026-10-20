# SMART-MEGA V6 — gate de engenharia do atestador Linux (20/10/2026)

**Missão:** homologar o produto sem depender do GitHub Actions e sem produzir falsos certificados. **Local:** VPS Linux `wmcp-cloud-01`, checkout isolado e limpo. **Origem:** `andrebarros78/SMART-MEGA`. **Branch:** `fix/v6-current-epoch-scoped-history-20261020`.

## 1. Falhas comprovadas e corrigidas (RED → GREEN)

O novo `smart_linux_ci.py` reconhecia `status=PASS` no JSON escrito em stdout pelo subprocesso mesmo quando não existia **nenhum arquivo JUnit real**. Um teste negativo reproduziu a aceitação falsa. O atestador agora exige:
- as duas evidências físicas `SMART_AUDIT_JUNIT_CANDIDATE.xml` e `SMART_AUDIT_JUNIT_CURRENT.xml`;
- parse da suíte com o utilitário original `smart_regression_evidence.junit_summary`;
- SHA-256, número de testes, falhas e erros coerentes em ambas e no registro de promoção;
- provas do executor de fingerprint imutável, ambiente estável, exclusividade de lock e preservação do certificado durante o teste;
- rejeição de arquivos simbólicos ou de relatórios incompletos.

Uma segunda falha ocorreu quando a saída do subprocesso não era JSON válido: `JSONDecodeError` interrompia o fluxo sem registro. Agora o status é `FAIL`, com recibo rastreável. A análise de JUnit inválido também é fail-closed.

Os testes foram escritos antes do reparo: reproduziram um falso positivo e uma exceção. Após correção, houve regressão verde.

## 2. Prova executada na VPS, no commit exato

- **HEAD testado:** `0d46803460361c3e193983e1c010c8777f7fe533`.
- `python3 smart_linux_ci.py --profile focused`: **PASS, 60 testes**, usando o ambiente autorizado.
- Checkout Git limpo antes e depois; nenhuma alteração produtiva.
- Recibo SHA-256: `96ee6ee793551e3877fdf806dfc4c00e13050ed16064fd0d3f1811ec1878a783`.
- Arquivo: `release_evidence/ci_linux/SMART_LINUX_CI_focused_c267ff2764d74e7c85a1202422c0a2f1.json`.
- `python3 smart_linux_ci.py --profile full --certify`: **BLOCKED_DEPENDENCIES**, sem executar e sem certificar a suíte completa.
- Recibo SHA-256: `ab4a61fbbb8984cecbb975adedbde085fd8b4ac7232065fb210de08879ac200d`.
- Arquivo: `release_evidence/ci_linux/SMART_LINUX_CI_full_59ce42b0f21b40989f0d7614449c8bdf.json`.

`requirements.lock.txt` fixa 75 distribuições Python. No runtime isolado, 74 versões ainda não estão disponíveis. As tentativas de instalação foram previamente recusadas pela autoridade de operações tipadas do LMCP; **não** foram contornadas.

## 3. Gate de autoridade

Solicitação já registrada: `capreq_68e0d83804ad4d7d895f7371b2a715ef`, `isolated_python_test_dependencies`, status `DISCOVERY_PENDING` na última leitura. Missão persistente: `m_82f9822ffb5f403594217eb18eb8aa9f`.

**Ações permitidas após liberação da capacidade:** utilizar exclusivamente o workspace isolado, instalar exatamente o lock e executar o perfil `full --certify`; o atestador reutiliza o runner original e a certificação do projeto com identidade `LMCP_LINUX_VPS`. Se qualquer teste, hash, gate de integridade ou dependência falhar, retornar `FAIL` e não promover a `main`.

## 4. Status

- Executor Linux e provas direcionadas: **PASS**.
- Gate completo com todos os testes: **NÃO EXECUTADO** — dependências ausentes.
- Certificação construtiva atualizada, operacional 3071 e cartão preditivo oficial 3072: **NÃO COMPROVADOS**.
- Científico 6/6: **NÃO COMPROVADO**.
- `main`: **NÃO ALTERADA**.
- PR #67: **draft; sem autorização de merge**.

**Conclusão do gate:** atestador Linux resistente a falsos positivos e apto a iniciar a certificação quando houver runtime governado. `MISSION_PROVEN` permanece bloqueada até prova integral.
