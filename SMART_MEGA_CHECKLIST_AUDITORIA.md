# SMART MEGA — CHECKLIST DE AUDITORIA

**Versão:** v5.2-CMN-MAX  
**Objetivo:** impedir geração sem dados, sem EV, sem testes, sem rastreabilidade ou com linguagem preditiva.

---

## 1. Checklist de abertura da sessão

| Item | Status | Observação |
|---|:---:|---|
| Arquivo de regras carregado | ☐ | ___ |
| Diário do modelo carregado | ☐ | ___ |
| Base histórica disponível | ☐ | ___ |
| Pedido do usuário identificado | ☐ | cartões / auditoria / recalibração / arquivo técnico |
| Modo correto selecionado | ☐ | técnico sem cartões / geração / auditoria |
| Proibição de dados inventados reconhecida | ☐ | ___ |
| Proibição de previsão reconhecida | ☐ | ___ |

---

## 2. Checklist de dados factuais

Antes de cartões, todos os itens abaixo devem estar confirmados.

| Dado | Confirmado? | Fonte | Valor |
|---|:---:|---|---|
| Concurso alvo | ☐ | ___ | ___ |
| Data do sorteio | ☐ | ___ | ___ |
| Resultado anterior | ☐ | ___ | ___ |
| Prêmio estimado | ☐ | ___ | ___ |
| Status acumulado | ☐ | ___ | ___ |
| Custo da aposta simples | ☐ | ___ | ___ |
| Base histórica | ☐ | ___ | ___ |
| N total da base | ☐ | ___ | ___ |
| Diário do modelo | ☐ | ___ | ___ |

**Regra de bloqueio:** se qualquer dado essencial estiver ausente, não gerar cartões.

---

## 3. Checklist de integridade da base

| Item | Status | Observação |
|---|:---:|---|
| Base possui coluna de concurso | ☐ | ___ |
| Base possui data ou identificador temporal | ☐ | ___ |
| Base possui 6 dezenas por concurso | ☐ | ___ |
| Todas as dezenas estão entre 01 e 60 | ☐ | ___ |
| Não há repetição dentro de concursos históricos | ☐ | ___ |
| Último concurso da base identificado | ☐ | ___ |
| Resultado oficial anterior está incorporado | ☐ | ___ |
| Duplicidades verificadas | ☐ | ___ |
| N total calculado | ☐ | ___ |

---

## 4. Checklist de EV

| Item | Status | Valor / Observação |
|---|:---:|---|
| Probabilidade de Sena usada | ☐ | ___ |
| Probabilidade de Quina usada | ☐ | ___ |
| Probabilidade de Quadra usada | ☐ | ___ |
| Prêmio de Sena confirmado | ☐ | ___ |
| Prêmio de Quina confirmado ou referência declarada | ☐ | ___ |
| Prêmio de Quadra confirmado ou referência declarada | ☐ | ___ |
| Custo por cartão confirmado | ☐ | ___ |
| EV nominal calculado | ☐ | R$ ___ |
| EV conservador calculado | ☐ | R$ ___ |
| EV total calculado | ☐ | R$ ___ |
| Status do EV declarado | ☐ | positivo / negativo / indeterminado |
| Alerta de EV negativo exibido, se aplicável | ☐ | ___ |

---

## 5. Checklist de testes estatísticos

| Teste | Executado? | Resultado | Decisão |
|---|:---:|---:|---|
| Frequência absoluta por dezena | ☐ | ___ | ___ |
| Frequência relativa por dezena | ☐ | ___ | ___ |
| IC95 por dezena | ☐ | ___ | ___ |
| Correção múltiplos testes | ☐ | ___ | ___ |
| Qui-quadrado uniformidade | ☐ | p=___ | ___ |
| Autocorrelação lag-1 | ☐ | p=___ | ___ |
| Sobreposição consecutiva | ☐ | ___ | ___ |
| Adjacência | ☐ | p=___ | ___ |
| Monte Carlo baseline | ☐ | ___ | ___ |
| Walk-forward, se N ≥ 1.000 | ☐ | lift=___ / p=___ | ___ |
| Soma P10/P25/P75/P90 | ☐ | ___ | ___ |
| Paridade histórica | ☐ | ___ | ___ |
| Quadrantes | ☐ | ___ | ___ |

---

## 6. Checklist de pesos e score

| Item | Status | Observação |
|---|:---:|---|
| Pesos somam 100% | ☐ | ___ |
| Camadas zeradas foram justificadas | ☐ | ___ |
| Frequência recente zerada se autocorrelação sem suporte | ☐ | ___ |
| Adjacência zerada se teste sem suporte | ☐ | ___ |
| Walk-forward limitado se sem significância | ☐ | ___ |
| Penalização/rateio documentada como sociológica, não causal | ☐ | ___ |
| Score calculado para 01 a 60 | ☐ | ___ |
| Top 20 gerado por score reproduzível | ☐ | ___ |
| Grupo A calculado | ☐ | ___ |
| Grupo B calculado | ☐ | ___ |
| Exceções abaixo de P50 justificadas | ☐ | ___ |

---

## 7. Checklist de linguagem

| Item | Status |
|---|:---:|
| Não usa “vai sair” | ☐ |
| Não usa “deve sair” | ☐ |
| Não usa “está na hora” | ☐ |
| Não usa “dezena quente/fria” como previsão | ☐ |
| Não usa “dívida” ou “pressão” | ☐ |
| Não usa astrologia, numerologia ou superstição | ☐ |
| Declara que Top 20 não é maior probabilidade real | ☐ |
| Declara que score é interno e não preditivo | ☐ |
| Declara EV e risco financeiro | ☐ |
| Inclui aviso de não-garantia | ☐ |

---

## 8. Checklist de geração de cartões

Usar somente quando o usuário pedir cartões.

| Item | Status | Observação |
|---|:---:|---|
| Exatamente 3 cartões | ☐ | ___ |
| 6 dezenas por cartão | ☐ | ___ |
| Dezenas entre 01 e 60 | ☐ | ___ |
| Sem repetição interna | ☐ | ___ |
| Preferência por Top 20 | ☐ | ___ |
| Exceções documentadas | ☐ | ___ |
| Soma entre P10 e P90 | ☐ | ___ |
| Preferência P25–P75 avaliada | ☐ | ___ |
| Paridade válida | ☐ | ___ |
| Quadrantes cobertos no conjunto | ☐ | ___ |
| Δ(C1,C2) calculado | ☐ | ___ |
| Δ(C1,C3) calculado | ☐ | ___ |
| Δ(C2,C3) calculado | ☐ | ___ |
| Score_div calculado | ☐ | ___ |
| Dezenas únicas calculadas | ☐ | ___ |
| Função técnica por dezena registrada | ☐ | ___ |
| Melhor cartão único indicado pelo modelo | ☐ | ___ |
| Melhor combinação de 2 cartões indicada | ☐ | ___ |

---

## 9. Checklist de auditoria pós-concurso

| Item | Status | Observação |
|---|:---:|---|
| Resultado oficial confirmado | ☐ | ___ |
| Acertos por cartão calculados | ☐ | ___ |
| Dezenas acertadas listadas | ☐ | ___ |
| Dezenas erradas listadas | ☐ | ___ |
| Sorteadas no Top 20 identificadas | ☐ | ___ |
| Sorteadas no Grupo A identificadas | ☐ | ___ |
| Sorteadas no Grupo B identificadas | ☐ | ___ |
| Sorteadas fora do score identificadas | ☐ | ___ |
| Erros de execução classificados | ☐ | ___ |
| Erros de montagem classificados | ☐ | ___ |
| Erros de modelo classificados | ☐ | ___ |
| Resultado financeiro indicado | ☐ | ___ |
| Diário atualizado sem overfitting | ☐ | ___ |

---

## 10. Checklist anti-overfitting

| Item | Status |
|---|:---:|
| Nenhum peso alterado por 1 concurso isolado | ☐ |
| Nenhum peso alterado por 2 concursos isolados | ☐ |
| Recalibração leve só com limiar mínimo | ☐ |
| Mudança estrutural só com evidência acumulada | ☐ |
| Falha isolada tratada como auditoria, não regra geral | ☐ |
| Alerta registrado sem promessa de correção futura | ☐ |

---

## 11. Bloqueio final

Se qualquer item crítico falhar, responder:

```text
Entrega bloqueada pelo checklist SMART Mega-Sena v5.2-CMN-MAX.

Itens pendentes:
- ___
- ___
- ___

Não foram gerados cartões.
```
