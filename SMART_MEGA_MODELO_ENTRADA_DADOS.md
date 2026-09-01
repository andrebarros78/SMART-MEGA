# SMART MEGA — MODELO DE ENTRADA DE DADOS

**Versão:** v5.2-CMN-MAX  
**Objetivo:** padronizar as informações que o usuário deve fornecer ou que o GPT deve confirmar antes de qualquer cálculo, geração ou auditoria.

---

## 1. Entrada mínima para geração de cartões

Preencher todos os campos obrigatórios.

```yaml
modo_solicitado: "geracao_cartoes"

dados_oficiais:
  concurso_alvo: 
  data_sorteio:
  resultado_anterior:
    concurso:
    data:
    dezenas: []
  premio_estimado:
  status_acumulado:
  custo_aposta_simples:
  fonte_dados_oficiais:

base_historica:
  arquivo:
  origem:
  ultimo_concurso_na_base:
  n_total_concursos:
  colunas_dezenas:
  base_validada: false
  observacoes:

diario_modelo:
  arquivo:
  versao:
  ultima_atualizacao:
  concursos_auditados:
  carregado: false

parametros_operacionais:
  quantidade_cartoes: 3
  dezenas_por_cartao: 6
  universo: "01-60"
  permitir_excecoes_fora_top20: "somente com justificativa"
  exigir_ev: true
  exigir_aviso_nao_garantia: true
```

---

## 2. Entrada para modo técnico sem cartões

Usar quando o usuário pedir arquivos, regras, modelos, documentação ou melhoria do GPT.

```yaml
modo_solicitado: "tecnico_sem_cartoes"

objetivo:
  tipo: "arquivo_tecnico | revisao_prompt | checklist | diario | relatorio | recalibracao_regras"
  arquivos_solicitados: []
  manter_compatibilidade_com:
    - "instrucoesmega-gpt.md"
  gerar_cartoes: false
  inventar_dados: false

restricoes:
  usar_placeholders: true
  preencher_concurso: false
  preencher_resultado: false
  preencher_premio: false
  preencher_top20: false
  preencher_grupos: false
```

---

## 3. Entrada para auditoria pós-concurso

```yaml
modo_solicitado: "auditoria_pos_concurso"

resultado_oficial:
  concurso:
  data:
  dezenas: []
  fonte:

cartoes_auditados:
  C1: []
  C2: []
  C3: []

modelo_usado:
  versao:
  top20_usado: []
  grupo_a: []
  grupo_b: []
  pesos_ativos:
    walk_forward:
    frequencia_historica:
    cobertura_estrutural:
    adjacencia:
    frequencia_recente:
    auditoria_serial:
    penalizacao_rateio:

dados_financeiros:
  custo_total:
  retorno_obtido:
  premio_quadra:
  premio_quina:
  premio_sena:
```

---

## 4. Entrada para recalibração

```yaml
modo_solicitado: "recalibracao"

base_historica:
  arquivo:
  origem:
  n_total_concursos:
  ultimo_concurso:
  inclui_resultado_anterior: false

diario_anterior:
  arquivo:
  versao:
  ultima_recalibracao:
  concursos_desde_recalibracao:
  alertas_ativos: []

recalibracao_solicitada:
  tipo: "factual | diagnostica | leve | grupos | walk_forward | ampla"
  gerar_cartoes_apos_recalibracao: false
  motivo:

limiares:
  concursos_para_pesos_leves: 50
  concursos_para_grupos: 100
  concursos_para_walk_forward: 200
  concursos_para_revisao_ampla: 500
```

---

## 5. Validação de resultado anterior

Formato aceito:

```text
Concurso anterior:
Data:
Resultado:
DD — DD — DD — DD — DD — DD
Fonte:
```

Regras:

- exatamente 6 dezenas;
- dezenas entre 01 e 60;
- sem repetição;
- fonte identificada;
- concurso e data preenchidos.

---

## 6. Validação da base histórica

Checklist mínimo:

```yaml
validacao_base:
  possui_concurso: false
  possui_data: false
  possui_6_dezenas: false
  dezenas_entre_01_60: false
  sem_repeticao_por_concurso: false
  sem_concursos_duplicados: false
  ultimo_concurso_identificado: false
  n_total_calculado: false
```

Se qualquer item crítico falhar, bloquear cálculo e listar pendências.

---

## 7. Modelo de dados para EV

```yaml
ev:
  premio_sena:
  premio_sena_tipo: "liquido | bruto | desconhecido"
  premio_quina:
  premio_quadra:
  custo_cartao:
  quantidade_cartoes:
  usar_cenario_nominal: true
  usar_cenario_conservador: true
  observacoes:
```

Saída esperada:

```text
EV nominal por cartão:
EV conservador por cartão:
EV nominal total:
EV conservador total:
Status:
Observação:
```

---

## 8. Modelo de dados para score

```yaml
score:
  pesos:
    walk_forward:
    frequencia_historica:
    cobertura_estrutural:
    adjacencia:
    frequencia_recente:
    auditoria_serial:
    penalizacao_rateio:
  testes:
    uniformidade_p:
    autocorrelacao_p:
    adjacencia_p:
    walk_forward_lift:
    walk_forward_p:
  limiares:
    grupo_a:
    grupo_b:
    soma_p10:
    soma_p25:
    soma_p75:
    soma_p90:
  top20: []
  grupo_a: []
  grupo_b: []
```

---

## 9. Resposta quando entrada estiver incompleta

Usar exatamente este padrão:

```text
Não posso continuar porque faltam dados essenciais:

- ___
- ___
- ___

Nenhum cartão foi gerado e nenhum dado foi inferido.
```

---

## 10. Campos que nunca devem ser inventados

- concurso;
- data;
- resultado oficial;
- prêmio estimado;
- status acumulado;
- custo da aposta;
- base histórica;
- N total;
- Top 20 calculado;
- Grupo A;
- Grupo B;
- p-valores;
- lift;
- EV;
- cartões.
