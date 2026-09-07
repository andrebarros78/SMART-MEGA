# Release Notes â€” SMART-MEGA B7 v7.0.0

- Linha B7 isolada da VF6.3 em `b7-predictive-edge`.
- CorreÃ§Ã£o de portabilidade para artefatos legados com caminho absoluto, sem permitir escape da raiz do projeto.
- RetenÃ§Ã£o das 60 probabilidades por concurso para auditoria independente.
- Brier score, binary log loss, ECE e `Prospective Edge` contra baseline uniforme.
- SeleÃ§Ã£o de calibraÃ§Ã£o somente na validaÃ§Ã£o; holdout protegido.
- Gate de nÃ£o regressÃ£o exige confianÃ§a positiva em Brier e log loss; caso contrÃ¡rio forÃ§a baseline uniforme.
- Challenger calibrado permanece shadow quando o gate nÃ£o passa.
- Freeze prospectivo B7 com cronograma CAIXA e trava temporal prÃ©-sorteio.
- Operador Ãºnico B7 com modos `status`, `historical-audit`, `freeze` e `verify`.
- VerificaÃ§Ã£o de hashes de dataset, relatÃ³rio, frontier, PDF de cronograma e polÃ­tica de horÃ¡rio.
- ProteÃ§Ã£o contra sobrescrita/replay de freeze.
- RemoÃ§Ã£o dos scripts transitÃ³rios `_fix_partial_patch.py` e `_patch_parallel_epoch.py`.
- VersÃ£o: 7.0.0.

Estado cientÃ­fico no fechamento: nenhuma vantagem probabilÃ­stica positiva foi comprovada; portanto nÃ£o existe claim de aumento de chance de jackpot neste release.
