# SMART-MEGA V6 — Decisão de release e homologação (21/10/2026)

**Gate:** `SMART_V6_GITHUB_ONLY_RELEASE_20261021`
**Decisão:** `RELEASE_BLOCKED_NOT_HOMOLOGATED`
**Produção:** `main` preservada; não autorizar merge da PR #67 nem promover certificação histórica para a revisão nova.

## Identidade e estado observado via GitHub API

- Repositório canônico: `andrebarros78/SMART-MEGA`.
- Base produtiva `main`: `c0b50af68ffbf537e56cca8abf898c7e23536442`.
- PR: https://github.com/andrebarros78/SMART-MEGA/pull/67, `draft=true`, `merged=false`, `mergeable=true`.
- Revisão antes deste gate: `c717177f39abe38c08d47e3166cf798cd184bfdb`.
- Escopo acumulado até essa revisão: 84 commits, 56 arquivos alterados.
- `check-runs` retornados para essa revisão: **0**. Statuses retornados: **0**. Reviews registrados: **0**.
- Branch `main`: `protected=false`, sem verificações de status obrigatórias.
- Política vigente: `SMART_GITHUB_NATIVE_ONLY_20261021`. O usuário solicitou não utilizar GitHub Actions neste gate, nem VPS, LMCP, PC Casa, Escola ou Vendas.
- `SMART_PRODUCT_CERTIFICATION.json` anteriormente declarou `CONSTRUCTION_PROVEN`, mas sua autoridade é historicamente vinculada a outra revisão. Isso NÃO certifica a alteração atual, a geração de cartão ou o objetivo científico 6/6.

## Deficiência material de autoridade eliminada no código candidato

`smart_github_certify.py::execution_provenance` ainda aceitava identidades `FEDERATED_PC` e `LMCP_LINUX_VPS`. `smart_product_certification.py::regression_source_binding` podia aprovar recibos dessas rotas ou um recibo sem identidade tipada.

Neste gate:
1. Proibir ambas as rotas antigas de emitir nova certificação.
2. Exigir declaração tipada `GITHUB_ACTIONS` com `run_id` idêntico ao identificador da evidência e vinculado ao SHA e repositório de origem.
3. Tratar recibos anteriores externos como evidência histórica não autorizante; não sobrescrever cartões, arquivos congelados, relatórios ou certificados históricos.
4. Versionar regressões de rejeição de executor externo e de recibo não atribuído.

## Separação indispensável de estados

**Publicação de código em PR = SIM**, uma evidência de Git/GitHub.

**Homologação funcional da revisão = NÃO**, pois não há runner executado permitido, logs nem suíte plena sobre o commit candidato. A ausência de Actions **não** autoriza migrar testes para VPS/PC ou fabricar um recibo de aprovação.

**Publicação produtiva = NÃO**, enquanto a regressão completa, a integridade, o consumidor de cartões, a segurança transacional, os contratos de autoridade e a elegibilidade científica não tiverem provas verificáveis para o commit exato.

**6/6 = NÃO COMPROVADO**, e `MISSION_PROVEN` não pode ser emitido.

## Critérios objetivos para destravar a promoção

- Commit candidato fixado, fonte e `main` comparadas sem alterações históricas inesperadas.
- Testes funcionais/regrassão completos realmente executados por infraestrutura **explicitamente autorizada** e vinculados ao SHA em GitHub, com número de testes, falhas, erros, cobertura e origem comprováveis.
- CI funcional e consumidor de cartão prospectivo aprovado, sem informação futura, sem falsa certificação, sem sinal pós-sorteio ponderado antes do sorteio.
- Revisão da PR e proteção da branch produtiva contra merges não homologados, com prova efetiva da configuração GitHub.
- Só então promover o commit validado, confirmar HEAD remoto `main`, estado limpo e evidências de implantação. Sem isso, manter `draft` e `main` inalterada.

**Classificação deste relatório:** inspeção remota/verificação estática; NÃO constitui execução de teste, certificação operacional, científica ou autorização de deploy.
