# SMART-MEGA — BASELINE OPERACIONAL GITHUB-NATIVE

**Baseline ID:** SMART_GITHUB_NATIVE_BASELINE_2026-09-28  
**Status:** NORMATIVA PARA IDENTIDADE, LOCALIZAÇÃO, BOOTSTRAP E REPRODUTIBILIDADE  
**Repositório canônico:** `andrebarros78/SMART-MEGA`  
**Branch canônica:** `main`  
**Baseline histórica preservada:** `SMART_EXECUTIVE_PRIORITIZED_PLAN_BASELINE_2026-08-21.md`

## 1. Precedência e escopo

Esta baseline supersede a baseline histórica **somente** nas regras de identidade física, host, root local, Python local e descoberta do repositório.

O plano executivo P0 -> P1 -> P2, os critérios 6/6, os contratos científicos, as regras de não regressão, anti-overfit, causalidade, integridade e prova permanecem válidos salvo quando conflitarem com a portabilidade GitHub-native aqui definida.

`DESKTOP-4T6AS9K` e `C:\SMART-MEGA` são origem histórica/proveniência da migração. Eles **não são requisitos operacionais** e não podem ser usados para rejeitar um checkout válido em outro host ou caminho.

## 2. Identidade operacional canônica

A identidade operacional é determinada por:

1. repositório Git `andrebarros78/SMART-MEGA`;
2. branch de referência `main` para baseline aprovada;
3. commit Git explicitamente testado para qualquer prova ou release;
4. root operacional resolvida dinamicamente pelo Git top-level do checkout atual;
5. ausência de dependência em hostname ou letra de unidade específicos.

A root operacional deve ser obtida por equivalente a:

```text
git rev-parse --show-toplevel
```

Nenhum arquivo operacional novo pode exigir `C:\SMART-MEGA`, `DESKTOP-4T6AS9K` ou qualquer outro host/path físico fixo.

## 3. Bootstrap reproduzível

Em um ambiente limpo:

1. clonar `andrebarros78/SMART-MEGA`;
2. fazer checkout do commit/branch desejado;
3. usar Python 3.13 compatível;
4. criar ambiente virtual no checkout ou em diretório externo;
5. instalar `requirements.txt`;
6. executar `python -m pip check`;
7. executar a regressão integral;
8. exigir baseline Git limpa após a execução, salvo evidências explicitamente geradas e ignoradas.

O ambiente virtual local histórico `.venv` não é autoridade e não deve ser versionado.

## 4. Estado/runtime canônico

O estado ativo é descrito por `SMART_ACTIVE_EPOCH.json` e pelos artefatos por ele referenciados. Arquivos com SHA-256 declarado devem existir e corresponder exatamente ao hash declarado antes de serem aceitos como autoridade.

Caminhos opcionais/reservados declarados no epoch não devem ser fabricados apenas para satisfazer existência nominal; a obrigatoriedade depende do contrato e do estado do lifecycle.

## 5. Prova de portabilidade

A migração GitHub-native foi comprovada no commit:

`35158323dc9a98720306704d1ed043f9e4bcb8b6`

Evidências de aceitação:

- checkout em GitHub-hosted Windows runner fora de `C:\SMART-MEGA`;
- Python 3.13 reconstruído no runner;
- instalação integral de `requirements.txt`;
- `pip check` aprovado;
- regressão integral: **903 passed / 0 failed**;
- histórico Git fonte incorporado ao `main`;
- branches históricas e 28 tags preservadas;
- secret scan da árvore corrente e histórico aprovados;
- `git fsck` aprovado;
- nenhum force-push necessário.

Essa evidência comprova portabilidade técnica daquela baseline. Alterações futuras exigem nova prova fresca; PASS histórico não autoriza declarar uma versão posterior como comprovada.

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
