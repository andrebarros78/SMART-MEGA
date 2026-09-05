# SMART-MEGA â€” CONTRATO DE TREINAMENTO HISTORICO

## Objetivo
Reprocessar o historico completo da Mega-Sena em ordem cronologica usando a arquitetura atual, com todos os agentes ativos em suas funcoes, sem permitir acesso a informacao futura.

## Regra causal
Para o concurso N, o sistema so pode usar dados dos concursos anteriores a N. A previsao, scores, pesos e atribuicoes devem ser congelados antes da revelacao do resultado de N. Somente depois o resultado real pode alimentar aprendizado para N+1.

## O que pode aprender
Qualidade real dos sinais, intensidade, confiabilidade, estabilidade, redundancia, correlacao, contexto, regime, utilidade marginal, interacoes, erros recorrentes, falsos positivos, falsos negativos, atraso de sinal e degradacao.

## O que nao pode aprender
Numero futuro, resultado do proprio concurso antes da previsao, ajustes retroativos para melhorar o mesmo concurso, combinacoes escolhidas depois de conhecer o resultado, ou qualquer informacao que nao existia no cutoff cronologico.

## Politica de memoria
O replay ocorre em estado SHADOW. A memoria e os pesos atuais de producao permanecem preservados como baseline. Nenhum estado reconstruido substitui a producao automaticamente.

## Regra de promocao
A memoria reconstruida deve superar a baseline atual em avaliacao fora da amostra/calibracao e nao pode degradar calibracao, robustez ou integridade. Caso contrario, permanece shadow ou e rejeitada.

## Formato minimo de entrada
Arquivo XLSX ou CSV contendo `Concurso`, `Bola1`, `Bola2`, `Bola3`, `Bola4`, `Bola5`, `Bola6`. `Data do Sorteio` e recomendada. Concursos devem ser unicos e estritamente crescentes; dezenas devem estar entre 1 e 60 e ser distintas dentro de cada concurso.
