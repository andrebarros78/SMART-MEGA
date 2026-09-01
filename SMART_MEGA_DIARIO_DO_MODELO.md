# SMART MEGA — DIÁRIO DO MODELO

**Versão do diário:** v5.2-CMN-MAX  
**Função:** registrar estado do modelo, testes, pesos, auditorias, alertas e alterações sem inventar dados.  
**Uso:** preencher somente com dados verificados, calculados ou auditados.

---

## 1. Identificação

| Campo | Valor |
|---|---|
| Versão do modelo | SMART Mega-Sena v5.2-CMN-MAX |
| Data da atualização | ___ |
| Responsável pela atualização | ___ |
| Fonte principal | ___ |
| Arquivo base utilizado | ___ |
| Hash/identificador da base, se houver | ___ |
| Observações gerais | ___ |

---

## 2. Contexto factual

| Dado | Valor | Fonte | Status |
|---|---:|---|:---:|
| Último concurso incorporado | ___ | ___ | ☐ confirmado |
| Resultado do último concurso | ___ | ___ | ☐ confirmado |
| Próximo concurso operacional | ___ | ___ | ☐ confirmado |
| Data do próximo sorteio | ___ | ___ | ☐ confirmado |
| Prêmio estimado | R$ ___ | ___ | ☐ confirmado |
| Status acumulado | Sim / Não / Indeterminado | ___ | ☐ confirmado |
| Custo da aposta simples | R$ ___ | ___ | ☐ confirmado |
| Base histórica | ___ | ___ | ☐ confirmado |
| N total de concursos | ___ | ___ | ☐ confirmado |

> Regra: se qualquer dado essencial estiver ausente ou não confirmado, o modelo não deve gerar cartões.

---

## 3. Estado estatístico da base

| Métrica | Valor | Método | Observação |
|---|---:|---|---|
| N concursos | ___ | contagem da base | ___ |
| Total de dezenas observadas | ___ | N × 6 | ___ |
| Frequência teórica por dezena | 10% | regra da modalidade | ___ |
| IC95 inferior | ___ | fórmula binomial | ___ |
| IC95 superior | ___ | fórmula binomial | ___ |
| Dezena com maior frequência histórica | ___ | cálculo | descritivo, não preditivo |
| Dezena com menor frequência histórica | ___ | cálculo | descritivo, não preditivo |

---

## 4. Testes estatísticos

| Teste | Resultado | p-valor | Decisão operacional |
|---|---:|---:|---|
| Uniformidade qui-quadrado | ___ | ___ | ___ |
| Correção múltiplos testes | Bonferroni / FDR / outro | ___ | ___ |
| Autocorrelação lag-1 | ___ | ___ | ___ |
| Sobreposição concursos consecutivos | ___ | ___ | ___ |
| Adjacência | ___ | ___ | ___ |
| Monte Carlo baseline | ___ | ___ | ___ |
| Walk-forward | lift ___ | p ___ | ___ |
| Paridade histórica | ___ | — | ___ |
| Soma histórica | P10 ___ / P25 ___ / P75 ___ / P90 ___ | — | ___ |
| Quadrantes | ___ | — | ___ |

---

## 5. Pesos ativos

| Camada | Peso | Justificativa | Ativa? |
|---|---:|---|:---:|
| Walk-forward | ___% | ___ | ☐ |
| Frequência histórica | ___% | ___ | ☐ |
| Cobertura estrutural | ___% | ___ | ☐ |
| Adjacência | ___% | ___ | ☐ |
| Frequência recente | ___% | ___ | ☐ |
| Auditoria serial | ___% | ___ | ☐ |
| Penalização/rateio | ___% | ___ | ☐ |

**Total:** ___%

> Regra: os pesos devem somar 100%. Camadas zeradas precisam ter motivo documentado.

---

## 6. Limiares calibrados

| Limiar | Valor | Base de cálculo | Status |
|---|---:|---|:---:|
| Grupo A | score ≥ ___ | P75 | ☐ |
| Grupo B | score ≥ ___ e < ___ | P50–P75 | ☐ |
| Soma P10 | ___ | histórico | ☐ |
| Soma P25 | ___ | histórico | ☐ |
| Soma P75 | ___ | histórico | ☐ |
| Soma P90 | ___ | histórico | ☐ |
| Paridades permitidas | ___ | frequência ≥ 8% | ☐ |
| Mínimo de dezenas únicas | ___ | regra operacional | ☐ |
| Score_div mínimo | ___ | regra operacional | ☐ |

---

## 7. Top 20 operacional

| Rank | Dezena | Score | Grupo | IC95 | Função técnica | Observação |
|---:|---:|---:|:---:|:---:|---|---|
| 1 | ___ | ___ | ___ | ___ | ___ | ___ |
| 2 | ___ | ___ | ___ | ___ | ___ | ___ |
| 3 | ___ | ___ | ___ | ___ | ___ | ___ |
| 4 | ___ | ___ | ___ | ___ | ___ | ___ |
| 5 | ___ | ___ | ___ | ___ | ___ | ___ |
| 6 | ___ | ___ | ___ | ___ | ___ | ___ |
| 7 | ___ | ___ | ___ | ___ | ___ | ___ |
| 8 | ___ | ___ | ___ | ___ | ___ | ___ |
| 9 | ___ | ___ | ___ | ___ | ___ | ___ |
| 10 | ___ | ___ | ___ | ___ | ___ | ___ |
| 11 | ___ | ___ | ___ | ___ | ___ | ___ |
| 12 | ___ | ___ | ___ | ___ | ___ | ___ |
| 13 | ___ | ___ | ___ | ___ | ___ | ___ |
| 14 | ___ | ___ | ___ | ___ | ___ | ___ |
| 15 | ___ | ___ | ___ | ___ | ___ | ___ |
| 16 | ___ | ___ | ___ | ___ | ___ | ___ |
| 17 | ___ | ___ | ___ | ___ | ___ | ___ |
| 18 | ___ | ___ | ___ | ___ | ___ | ___ |
| 19 | ___ | ___ | ___ | ___ | ___ | ___ |
| 20 | ___ | ___ | ___ | ___ | ___ | ___ |

> Observação obrigatória: Top 20 é classificação interna. Não significa maior probabilidade real no próximo sorteio.

---

## 8. Grupos operacionais

**Grupo A:**  
___

**Grupo B:**  
___

**Pool complementar justificado:**  
___

**Dezenas bloqueadas ou despriorizadas por regra técnica:**  
___

---

## 9. Alertas ativos

| Alerta | Tipo | Origem | Ação requerida | Status |
|---|---|---|---|:---:|
| ___ | EV / Dados / Score / Auditoria / Recalibração | ___ | ___ | ☐ aberto |
| ___ | EV / Dados / Score / Auditoria / Recalibração | ___ | ___ | ☐ aberto |
| ___ | EV / Dados / Score / Auditoria / Recalibração | ___ | ___ | ☐ aberto |

Se não houver alertas:

> Nenhum alerta ativo.

---

## 10. Histórico de auditorias

| Concurso | Resultado oficial | Cartões auditados? | Melhor cartão | Acertos totais no conjunto | Erros de execução | Erros de modelo | Observações |
|---:|---|:---:|---|---:|---:|---:|---|
| ___ | ___ | ☐ | ___ | ___ | ___ | ___ | ___ |

---

## 11. Métricas de desempenho

| Métrica | Valor | Janela | Observação |
|---|---:|---|---|
| Taxa captura Top 20 | ___% | ___ concursos | ___ |
| Lift contra aleatório | ___ | ___ concursos | ___ |
| Média de acertos por cartão | ___ | ___ concursos | ___ |
| Frequência de Quadra | ___ | ___ concursos | ___ |
| Frequência de Quina | ___ | ___ concursos | ___ |
| Modelo superou aleatório? | Sim / Não / Sem dados | ___ | ___ |
| Concursos desde última recalibração | ___ | ___ | ___ |

---

## 12. Recalibração

| Item | Última recalibração | Próxima recalibração | Critério |
|---|---:|---:|---|
| Pesos leves | ___ | ___ | 50 concursos auditados |
| P50/P75 dos grupos | ___ | ___ | 100 concursos auditados |
| Walk-forward | ___ | ___ | 200 concursos auditados |
| Revisão ampla | ___ | ___ | 500 concursos auditados |
| Revisão emergencial Top 20 | ___ | ___ | 10 concursos com captura < 50% |
| Alerta crítico de lift | ___ | ___ | 20 concursos com lift < 1,0 |

---

## 13. Registro de mudanças

| Data | Versão | Mudança | Motivo | Evidência | Aprovado? |
|---|---|---|---|---|:---:|
| ___ | ___ | ___ | ___ | ___ | ☐ |

---

## 14. Declaração final do diário

Este diário é um registro técnico e auditável. Ele não prevê sorteios, não garante acertos e não altera a probabilidade matemática da Mega-Sena. Qualquer dado não confirmado deve permanecer em branco.
