# SMART-MEGA — BASELINE OPERACIONAL GITHUB-NATIVE

**Arquivo:** `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`  
**Baseline ID:** SMART_GITHUB_NATIVE_BASELINE_2026-09-28  
**Status:** NORMATIVA PARA IDENTIDADE, LOCALIZAÇÃO, BOOTSTRAP E REPRODUTIBILIDADE  
**Repositório canônico:** `andrebarros78/SMART-MEGA`  
**Branch canônica:** `main`  
**Baseline histórica preservada:** `SMART_EXECUTIVE_PRIORITIZED_PLAN_BASELINE_2026-08-21.md`

## 1. Precedência e escopo

Esta baseline supersede qualquer regra histórica de identidade física, hostname, root local, ambiente Python local ou máquina específica.

O plano executivo P0 -> P1 -> P2, os critérios 6/6, os contratos científicos, as regras de não regressão, anti-overfit, causalidade, integridade e prova permanecem válidos salvo quando conflitarem com a portabilidade GitHub-native aqui definida.

Nenhum host físico, sistema operacional externo ao GitHub Actions, letra de unidade ou caminho local fixo constitui autoridade operacional.

## 2. Identidade operacional canônica

A identidade operacional é determinada por:

1. repositório Git `andrebarros78/SMART-MEGA`;
2. branch de referência `main` para baseline aprovada;
3. commit Git explicitamente testado para qualquer prova ou release;
4. root operacional resolvida dinamicamente pelo Git top-level do checkout atual;
5. execução oficial dos gates em runners GitHub-hosted Ubuntu;
6. ausência de dependência em hostname, máquina física ou caminho local específico.

A root operacional deve ser obtida por equivalente a:

```text
git rev-parse --show-toplevel
```

Nenhum arquivo operacional novo pode exigir host, caminho físico ou máquina específica.

## 3. Bootstrap reproduzível

Em um ambiente limpo GitHub-hosted:

1. fazer checkout de `andrebarros78/SMART-MEGA` no commit/branch desejado;
2. usar Python 3.13 compatível;
3. instalar `requirements.lock.txt`;
4. executar `python -m pip check`;
5. executar a regressão integral;
6. executar os gates de integridade aplicáveis;
7. exigir baseline Git limpa após a execução, salvo evidências explicitamente geradas e ignoradas.

Ambientes virtuais locais não são autoridade e não devem ser versionados.

## 4. Estado/runtime canônico

O estado ativo é descrito por `SMART_ACTIVE_EPOCH.json` e pelos artefatos por ele referenciados.

Para artefatos binários, SHA-256 declarado deve corresponder byte a byte ao arquivo versionado.

Para artefatos textuais, a verificação pode reconhecer equivalência de conteúdo entre terminações de linha LF e CRLF, sem aceitar qualquer alteração semântica. Essa portabilidade não autoriza normalização de binários nem alteração do conteúdo lógico das autoridades históricas.

Caminhos opcionais/reservados declarados no epoch não devem ser fabricados apenas para satisfazer existência nominal; a obrigatoriedade depende do contrato e do estado do lifecycle.

## 5. Prova GitHub-native

A única prova operacional corrente é a produzida por GitHub Actions no mesmo commit sob julgamento.

Para um commit ser aceito como baseline GitHub-native, deve haver, no mínimo:

- checkout em runner GitHub-hosted Ubuntu;
- Python 3.13 reconstruído no runner;
- instalação integral de `requirements.lock.txt`;
- `pip check` aprovado;
- regressão integral aprovada;
- Repository Integrity aprovado;
- ausência de dependência operacional em máquina física ou executor externo;
- evidências vinculadas ao mesmo commit avaliado.

PASS histórico não autoriza declarar uma versão posterior como comprovada. Toda alteração material exige prova fresca.

## 6. Regra 6/6

A arquitetura continua sujeita aos seis critérios do projeto:

1. captação e qualidade;
2. interpretação;
3. conversão em pesos;
4. calibração e adaptação;
5. aprendizado e robustez;
6. resultado comprovado.

Qualquer alteração material deve seguir medir -> alterar -> testar -> comparar -> retestar e não pode reduzir o resultado global.

`MISSION_PROVEN` exige evidência fresca posterior ao último byte funcional relevante.

## 7. Arquivos de descoberta

`README.md`, `AGENTS.md`, `AI_START_HERE.md` e `SMART_AI_EXECUTION_ENTRYPOINT.md` devem apontar para esta baseline GitHub-native como autoridade de identidade/localização e para a baseline histórica como autoridade do plano executivo preservado.
