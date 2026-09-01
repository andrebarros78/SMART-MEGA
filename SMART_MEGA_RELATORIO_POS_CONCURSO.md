# SMART MEGA — RELATÓRIO PÓS-CONCURSO

**Versão:** v5.2-CMN-MAX  
**Objetivo:** auditar resultado oficial, desempenho dos cartões e erros do modelo sem alterar pesos por ruído isolado.

---

## 1. Identificação do relatório

| Campo | Valor |
|---|---|
| Concurso auditado | ___ |
| Data do sorteio | ___ |
| Fonte do resultado oficial | ___ |
| Data da auditoria | ___ |
| Versão do modelo usada | ___ |
| Diário usado | ___ |
| Base histórica usada | ___ |

---

## 2. Resultado oficial

| Dezena 1 | Dezena 2 | Dezena 3 | Dezena 4 | Dezena 5 | Dezena 6 |
|---:|---:|---:|---:|---:|---:|
| ___ | ___ | ___ | ___ | ___ | ___ |

Validação:

- [ ] resultado tem 6 dezenas;
- [ ] dezenas entre 01 e 60;
- [ ] sem repetição;
- [ ] fonte oficial registrada.

---

## 3. Cartões auditados

| Cartão | Dezenas |
|---|---|
| C1 | ___ |
| C2 | ___ |
| C3 | ___ |

> Se os cartões não tiverem sido gerados pelo SMART Mega-Sena, marcar como auditoria externa.

---

## 4. Acertos por cartão

| Cartão | Acertos | Dezenas acertadas | Dezenas erradas |
|---|---:|---|---|
| C1 | ___/6 | ___ | ___ |
| C2 | ___/6 | ___ | ___ |
| C3 | ___/6 | ___ | ___ |

**Melhor cartão:** ___  
**Total de dezenas distintas capturadas no conjunto:** ___/6  
**Dezenas capturadas no conjunto:** ___

---

## 5. Classificação das dezenas sorteadas

| Dezena sorteada | Estava no Top 20? | Estava no Grupo A? | Estava no Grupo B? | Entrou em cartão? | Classificação |
|---:|:---:|:---:|:---:|:---:|---|
| ___ | ☐ | ☐ | ☐ | ☐ | ___ |
| ___ | ☐ | ☐ | ☐ | ☐ | ___ |
| ___ | ☐ | ☐ | ☐ | ☐ | ___ |
| ___ | ☐ | ☐ | ☐ | ☐ | ___ |
| ___ | ☐ | ☐ | ☐ | ☐ | ___ |
| ___ | ☐ | ☐ | ☐ | ☐ | ___ |

Classificações possíveis:

- acerto de execução;
- erro de execução;
- erro de montagem;
- erro de modelo;
- falha de score;
- exceção estrutural justificada;
- fora do escopo.

---

## 6. Top 20 e grupos usados

**Top 20 usado:**  
___

**Grupo A usado:**  
___

**Grupo B usado:**  
___

**Pool complementar usado, se houve:**  
___

---

## 7. Erros de execução

Erro de execução ocorre quando uma dezena elegível pelo próprio modelo não foi protegida ou foi excluída sem teste de substituição documentado.

| Dezena | Evidência | Impacto | Ação |
|---:|---|---|---|
| ___ | ___ | ___ | ___ |

---

## 8. Erros de montagem

Erro de montagem ocorre quando os cartões violam regra operacional:

- soma fora do intervalo;
- paridade inválida;
- quadrante ignorado sem justificativa;
- diversidade excessiva com perda de cobertura;
- concentração excessiva sem justificativa;
- exceção sem documentação;
- função técnica ausente.

| Cartão | Erro | Evidência | Correção futura |
|---|---|---|---|
| ___ | ___ | ___ | ___ |

---

## 9. Erros de modelo

Erro de modelo ocorre quando a dezena sorteada estava fora do Top 20, Grupo A, Grupo B ou score relevante.

| Dezena | Status no modelo | Classificação | Observação |
|---:|---|---|---|
| ___ | ___ | erro de modelo | ___ |

---

## 10. Resultado financeiro

| Item | Valor |
|---|---:|
| Custo total | R$ ___ |
| Prêmio recebido | R$ ___ |
| Saldo | R$ ___ |
| Houve recuperação do investimento? | Sim / Não |
| Faixa atingida | Nenhuma / Quadra / Quina / Sena |
| EV anterior era | Positivo / Negativo / Indeterminado |

> Resultado financeiro não prova capacidade preditiva do modelo.

---

## 11. Comparação contra baseline

| Métrica | Modelo | Baseline aleatório | Interpretação |
|---|---:|---:|---|
| Média de acertos por cartão | ___ | ___ | ___ |
| Melhor cartão | ___ | ___ | ___ |
| Dezenas capturadas no conjunto | ___ | ___ | ___ |
| Quadra ou superior | Sim / Não | ___ | ___ |
| Lift observado | ___ | ___ | ___ |

Se não houver base suficiente:

> Não há evidência estatística suficiente para afirmar vantagem sobre baseline aleatório.

---

## 12. Atualização do diário

Trecho para colar no diário:

```text
AUDITORIA PÓS-CONCURSO

Concurso:
Resultado oficial:
Cartões auditados:
C1:
C2:
C3:

Desempenho:
C1:
C2:
C3:
Total capturado:

Classificação:
Erros de execução:
Erros de montagem:
Erros de modelo:
Resultado financeiro:
Alertas:
Ação recomendada:
Alteração de pesos? NÃO, salvo limiar de recalibração atingido.
```

---

## 13. Regras anti-overfitting pós-concurso

- Não mudar pesos por 1 concurso.
- Não mudar pesos por 2 concursos.
- Não transformar falha isolada em regra.
- Não transformar acerto isolado em prova.
- Não chamar acerto de previsão.
- Não chamar erro de “azar do modelo”.
- Registrar e aguardar limiar estatístico.

---

## 14. Conclusão obrigatória

```text
Esta auditoria registra desempenho e erros operacionais do concurso. Ela não prova previsão, não garante acertos futuros e não altera a probabilidade matemática da Mega-Sena.
```
