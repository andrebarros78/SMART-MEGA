# SMART-MEGA

SMART-MEGA é mantido no GitHub como sua única fonte canônica de projeto.

## Fonte canônica

- Repositório: `andrebarros78/SMART-MEGA`
- Branch canônica: `main`
- Política operacional: `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`
- Root local: Git top-level do checkout atual

Chat, memória de IA, anexos, runners e cópias locais não substituem o estado persistido no GitHub.

## Começar

Leia:

1. `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`
2. `AI_START_HERE.md`
3. `AGENTS.md`

A baseline histórica `SMART_EXECUTIVE_PRIORITIZED_PLAN_BASELINE_2026-08-21.md` é consultada apenas quando relevante e somente no que não conflitar com a política atual.

## Execução mínima

Antes de qualquer ação: **PEDIDO OU INDISPENSÁVEL?**

Se não foi pedido e não é indispensável para atingir o objetivo atual, não executar.

Backup, snapshot, regressão ampla, refatoração, hardening, nova infraestrutura e documentação adicional não são etapas automáticas.

## Bootstrap

```powershell
git clone https://github.com/andrebarros78/SMART-MEGA.git
Set-Location SMART-MEGA
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Em outros sistemas, use o executável Python 3.13 equivalente. O ambiente virtual não é versionado.

Testes devem ser proporcionais ao comportamento alterado. Regressão integral só é executada quando o impacto for sistêmico, quando um gate existente realmente a exigir para a mudança ou quando solicitada explicitamente.

## Operação autônoma

O agente/IA deve descobrir o estado real, fazer a menor correção suficiente, executar a validação necessária, corrigir falhas recuperáveis e persistir o resultado no GitHub sem transferir trabalho técnico rotineiro ao usuário.

Falha de ferramenta ou conector não constitui bloqueio enquanto existir rota técnica autorizada.

## Estado canônico

Estado que deva sobreviver à execução precisa estar persistido no GitHub. Uma alteração ocorrida apenas em runner, memória ou checkout local não é canônica.

Artefatos com SHA-256 declarado devem existir e corresponder ao hash declarado quando forem usados como autoridade.

## Regra científica

Nunca gerar ou reinterpretar retrospectivamente um cartão usando resultado já conhecido. Concursos sem geração prospectiva válida permanecem sem geração válida.

Os critérios 6/6 do projeto permanecem obrigatórios, mas devem ser perseguidos com a menor complexidade necessária. `MISSION_PROVEN` exige evidência fresca do estado canônico atual.
