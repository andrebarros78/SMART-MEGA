# SMART MEGA — REGRAS DE RECALIBRAÇÃO

**Versão:** v5.2-CMN-MAX  
**Objetivo:** definir quando e como o modelo pode ser recalibrado sem overfitting, sem palpite e sem alteração baseada em ruído.

---

## 1. Princípio fundamental

Recalibrar não significa prever.  
Recalibrar significa atualizar parâmetros descritivos, pesos internos, limiares e alertas com base em evidência acumulada.

A Mega-Sena permanece processo aleatório i.i.d., sem memória e sem causalidade entre concursos.

---

## 2. O que pode ser recalibrado

| Componente | Pode recalibrar? | Condição |
|---|:---:|---|
| N total da base | Sim | a cada atualização factual |
| Resultado anterior | Sim | somente com fonte oficial |
| EV | Sim | a cada novo concurso/prêmio/custo |
| Frequência histórica | Sim | a cada base atualizada |
| IC95 por dezena | Sim | a cada base atualizada |
| Soma P10/P25/P75/P90 | Sim | a cada base atualizada |
| Paridade histórica | Sim | a cada base atualizada |
| Quadrantes | Sim | a cada base atualizada |
| Top 20 operacional | Sim | se score recalculado |
| Grupo A e Grupo B | Sim | se score recalculado |
| Pesos leves | Sim | após limiar mínimo |
| Arquitetura de score | Sim, com restrição | apenas revisão ampla |
| Linguagem proibida | Não flexibilizar | permanente |
| Pseudociência | Não | peso 0% permanente |

---

## 3. O que não pode ser feito

É proibido:

- mudar peso estrutural por 1 concurso;
- mudar peso estrutural por 2 concursos;
- criar regra causal por atraso;
- criar regra causal por repetição;
- tratar dezena como “devida”;
- tratar falha isolada como prova estatística;
- apagar erro de execução do diário;
- remover alerta sem auditoria;
- declarar que o modelo passou a prever;
- declarar que Top 20 aumenta chance real;
- esconder EV negativo.

---

## 4. Tipos de recalibração

### 4.1. Recalibração factual

Executar quando houver novo concurso oficial.

Atualiza:

- último concurso;
- resultado oficial;
- N total;
- base histórica;
- EV do concurso seguinte;
- custo, prêmio e status quando confirmados.

Não altera automaticamente pesos estruturais.

### 4.2. Recalibração diagnóstica

Executar quando a base é atualizada ou quando o usuário pede recalibração.

Atualiza:

- frequências;
- IC95;
- soma;
- paridade;
- quadrantes;
- testes estatísticos;
- score;
- Top 20;
- grupos;
- alertas.

Pode atualizar rankings, mas deve marcar que ranking não é previsão.

### 4.3. Recalibração leve

Permitida apenas após pelo menos 50 concursos auditados desde a última recalibração leve.

Pode ajustar:

- peso de frequência histórica;
- peso de cobertura estrutural;
- ativação/desativação de adjacência;
- ativação/desativação de frequência recente;
- alertas operacionais.

Mudança máxima recomendada: 5 pontos percentuais por camada, salvo evidência robusta.

### 4.4. Recalibração de grupos

Permitida após pelo menos 100 concursos auditados.

Atualiza:

- P50;
- P75;
- critérios de Grupo A;
- critérios de Grupo B;
- limiar de exceções.

### 4.5. Reavaliação walk-forward

Permitida após pelo menos 200 concursos auditados.

Atualiza:

- janelas de treino;
- janelas de teste;
- lift;
- p-valor;
- peso walk-forward.

### 4.6. Revisão estatística ampla

Permitida após pelo menos 500 concursos auditados.

Pode rever:

- arquitetura do score;
- pesos máximos e mínimos;
- filtros estruturais;
- regra de diversificação;
- regra de exceções;
- parâmetros de Monte Carlo;
- métrica de comparação contra aleatório.

---

## 5. Gatilhos emergenciais

### 5.1. Captura Top 20 baixa

Se a taxa de captura Top 20 ficar abaixo de 50% por 10 concursos consecutivos:

- ativar alerta emergencial;
- revisar cálculo de score;
- revisar limiares;
- revisar excesso de concentração;
- não alterar pesos imediatamente sem diagnóstico.

### 5.2. Lift abaixo de 1,0

Se o lift contra baseline aleatório ficar abaixo de 1,0 por 20 concursos auditados:

- ativar alerta crítico;
- declarar que o modelo não superou aleatório;
- reduzir alegações operacionais;
- revisar score em modo diagnóstico;
- preservar aviso de não-garantia.

### 5.3. Falha repetida de execução

Se a mesma classe de erro de execução ocorrer 3 vezes em janela curta:

- registrar falha recorrente;
- criar trava operacional;
- exigir teste de substituição;
- não transformar em previsão.

---

## 6. Testes obrigatórios na recalibração

| Teste | Obrigatório? | Condição |
|---|:---:|---|
| Qui-quadrado uniformidade | Sim | sempre que houver base |
| IC95 por dezena | Sim | sempre que houver base |
| Correção múltiplos testes | Sim | sempre que houver análise individual |
| Autocorrelação lag-1 | Sim | sempre que possível |
| Adjacência | Sim | sempre que possível |
| Monte Carlo baseline | Sim | sempre que possível |
| Walk-forward | Sim | N ≥ 1.000 |
| Soma histórica | Sim | sempre que houver base |
| Paridade histórica | Sim | sempre que houver base |
| Quadrantes | Sim | sempre que houver base |

---

## 7. Matriz decisória de pesos

### 7.1. Frequência histórica

| Resultado do qui-quadrado | Peso recomendado |
|---|---:|
| p > 0,20 | 8% |
| 0,05 < p ≤ 0,20 | 12% |
| p ≤ 0,05 | até 18% |

Mesmo com p ≤ 0,05, não afirmar previsão.

### 7.2. Autocorrelação e frequência recente

| Resultado | Decisão |
|---|---|
| p > 0,10 | frequência recente = 0%; auditoria serial = 0% |
| p ≤ 0,10 | permitir peso moderado com justificativa |

### 7.3. Adjacência

| Resultado | Decisão |
|---|---|
| p > 0,10 | adjacência = 0% |
| 0,05 < p ≤ 0,10 | adjacência até 5% |
| p ≤ 0,05 | adjacência até 10% |

### 7.4. Walk-forward

| Resultado | Decisão |
|---|---|
| lift > 1,05 e p ≤ 0,05 | até 30% |
| lift > 1,00 e p ≤ 0,10 | até 15% |
| sem significância | mínimo ou 0% |
| lift < 1,00 | alerta e redução |

---

## 8. Procedimento de recalibração

### Etapa R1 — Preparação

- carregar base;
- confirmar N;
- confirmar último concurso;
- confirmar resultado oficial;
- carregar diário anterior;
- identificar janela desde última recalibração.

### Etapa R2 — Diagnóstico

Calcular:

- frequências;
- IC95;
- testes;
- soma;
- paridade;
- quadrantes;
- Monte Carlo;
- walk-forward, se aplicável.

### Etapa R3 — Comparação

Comparar com diário anterior:

- mudança de pesos;
- mudança de Top 20;
- mudança de Grupo A/B;
- mudança de soma P10/P90;
- mudança de paridade;
- mudança de lift;
- mudança de captura Top 20;
- mudança de erros recorrentes.

### Etapa R4 — Decisão

Classificar:

- sem alteração;
- ajuste factual;
- recalibração diagnóstica;
- recalibração leve;
- recalibração de grupos;
- reavaliação walk-forward;
- revisão ampla;
- alerta emergencial.

### Etapa R5 — Registro

Atualizar:

- diário do modelo;
- checklist;
- relatório de recalibração;
- alertas;
- próxima data/concurso de revisão.

---

## 9. Modelo de registro de recalibração

```text
RECALIBRAÇÃO SMART MEGA v5.2-CMN-MAX

Data:
Concurso base:
N total:
Tipo de recalibração:
Motivo:
Testes executados:
Resultados principais:
Pesos antes:
Pesos depois:
Diferenças:
Top 20 antes:
Top 20 depois:
Grupo A antes:
Grupo A depois:
Grupo B antes:
Grupo B depois:
Alertas criados:
Alertas encerrados:
Cartões gerados? NÃO / SIM, se solicitado em etapa separada.
Justificativa anti-overfitting:
Aviso de não-garantia:
```

---

## 10. Declaração obrigatória

Toda recalibração deve terminar com:

> Esta recalibração atualiza parâmetros internos de organização e auditoria. Ela não cria previsão, não garante acertos e não altera a probabilidade matemática da Mega-Sena.
