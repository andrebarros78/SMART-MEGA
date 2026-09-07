# SMART-MEGA B7 â€” Release 7.0.0

## Objetivo operacional

A B7 Ã© a linha paralela do SMART-MEGA destinada a medir, falsificar e acumular evidÃªncia prospectiva de possÃ­vel vantagem preditiva sem contaminar a baseline VF6.3. Ela deve produzir probabilidades completas para as 60 dezenas, aplicar pesos dinÃ¢micos e redundÃ¢ncia, executar walk-forward causal, separar calibraÃ§Ã£o/validaÃ§Ã£o/holdout, controlar mÃºltiplos testes e congelar previsÃµes antes do resultado oficial.

A B7 **nÃ£o declara vantagem preditiva quando a evidÃªncia nÃ£o a sustenta**. No release 7.0.0, o gate probabilÃ­stico nÃ£o aprovou vantagem sobre o uniforme; portanto o canÃ´nico opera em `UNIFORM_BASELINE_NO_REGRESSION` e o modelo calibrado permanece `SHADOW_ONLY_UNTIL_FUTURE_OOS_PROOF`.

## Modos

- `status`: estado da versÃ£o e Ãºltimo freeze validado.
- `historical-audit`: walk-forward e calibraÃ§Ã£o histÃ³rica com Brier, log loss, ECE e retenÃ§Ã£o das 60 probabilidades.
- `freeze`: congelamento prospectivo com cutoff causal, cronograma oficial e trava temporal prÃ©-sorteio.
- `verify`: valida hashes, referÃªncias, cronograma, polÃ­tica de horÃ¡rio, flags causais e mapas de probabilidade.

## OperaÃ§Ã£o

```bat
smart_python.cmd smart_b7_operator.py status
```

```bat
smart_python.cmd smart_b7_operator.py verify --freeze B7_3055_PROSPECTIVE_FREEZE_FINAL.json
```

Para novo alvo, o histÃ³rico canÃ´nico deve terminar exatamente em `target-1` e o cronograma oficial correspondente deve estar disponÃ­vel na fonte procedural. O freeze recusa alvo retrospectivo, divergÃªncia de data oficial e sobrescrita do artefato existente.

## EvidÃªncia 3055

- cutoff: 3054;
- resultado usado na geraÃ§Ã£o: nÃ£o;
- cronograma: 08/09/2026;
- canÃ´nico: uniforme sem regressÃ£o;
- Top-6 registrado pelo ranking: 11, 30, 27, 10, 35, 38;
- challenger calibrado: shadow, sem autoridade de produÃ§Ã£o;
- promoÃ§Ã£o: somente apÃ³s evidÃªncia futura fora da amostra suficiente.

## SeguranÃ§a e isolamento

O runtime Ã© local/CLI e nÃ£o expÃµe servidor prÃ³prio. O launcher canÃ´nico limpa `PYTHONPATH` e executa Python com `-E`, impedindo que projetos vizinhos entrem no `sys.path`. AquisiÃ§Ãµes externas usam rotinas explÃ­citas para fontes pÃºblicas; nÃ£o hÃ¡ credencial necessÃ¡ria para o nÃºcleo B7.

## PersistÃªncia

A evidÃªncia Ã© baseada em arquivos com SHA-256, freezes imutÃ¡veis e artefatos JSON/XLSX. NÃ£o hÃ¡ banco operacional obrigatÃ³rio no nÃºcleo B7. O freeze prospectivo mantÃ©m referÃªncias por hash ao dataset, relatÃ³rio histÃ³rico, frontier shadow, polÃ­tica de horÃ¡rio e cronograma oficial.

## LimitaÃ§Ãµes comprovadas

A vantagem prospectiva positiva ainda nÃ£o foi comprovada. O holdout do challenger apresentou melhor mÃ©dia de hits do Top-6, mas nÃ£o melhora robusta em proper scoring rules; por isso o sistema neutralizou automaticamente o peso probabilÃ­stico canÃ´nico. Essa limitaÃ§Ã£o Ã© deliberadamente preservada no release para evitar falso aprendizado.

## Rollback

A baseline anterior preservada Ã© a tag `VF6.3`. A B7 reside em branch e worktree prÃ³prios e nÃ£o altera a VF6.3.
