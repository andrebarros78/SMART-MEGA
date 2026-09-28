# SMART-MEGA

SMART-MEGA é mantido neste repositório como fonte canônica GitHub-native.

## Fonte canônica

- Repositório: `andrebarros78/SMART-MEGA`
- Baseline aprovada: `main`
- Root operacional: o Git top-level do checkout atual
- Python de referência para CI: 3.13

Nenhum host, letra de unidade ou caminho físico específico é requisito operacional. A antiga origem `DESKTOP-4T6AS9K` / `C:\SMART-MEGA` é apenas proveniência histórica da migração.

## Começar

Leia, nesta ordem:

1. `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`
2. `SMART_EXECUTIVE_PRIORITIZED_PLAN_BASELINE_2026-08-21.md`
3. `AI_START_HERE.md`
4. `AGENTS.md`

## Bootstrap limpo

```powershell
git clone https://github.com/andrebarros78/SMART-MEGA.git
Set-Location SMART-MEGA
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --disable-warnings
```

Em outros sistemas, use o executável Python 3.13 equivalente. O ambiente virtual não é versionado.

## Gates de integridade

O repositório mantém dois níveis principais de CI:

- **Repository Integrity**: valida identidade GitHub-native e hashes do estado/epoch canônico.
- **SMART-MEGA CI**: instala dependências e executa a regressão integral.

A baseline de migração validada em `main` executou **903 testes com sucesso** em GitHub-hosted Windows runner independente.

## Estado canônico

`SMART_ACTIVE_EPOCH.json` descreve o epoch ativo e referencia artefatos científicos/runtime por caminhos relativos. Quando um SHA-256 é declarado como autoridade, o arquivo correspondente deve existir e corresponder exatamente ao hash declarado.

Caminhos reservados/opcionais não devem ser fabricados apenas porque aparecem em `state_paths`.

## Regra de mudança

Toda alteração material deve seguir:

`medir -> alterar -> testar -> comparar -> corrigir -> retestar`

Um PASS histórico não prova um commit novo. `MISSION_PROVEN` somente pode ser atribuído a uma baseline com evidência fresca posterior às alterações relevantes.
