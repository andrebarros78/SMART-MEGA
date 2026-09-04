# SMART-MEGA â€” CONTRATO CANÃ”NICO DE DADOS

Fonte operacional atual: `Mega-Sena_through_3053_v2.xlsx`. Cutoff cientÃ­fico atual: concurso 3053.

Contrato por linha: um concurso Ãºnico e ordenado, seis dezenas inteiras distintas em `Bola1..Bola6`, cada uma no intervalo 1..60, sem nulos. Dados posteriores ao cutoff declarado sÃ£o proibidos em treinamento, seleÃ§Ã£o, calibraÃ§Ã£o ou congelamento destinado ao concurso seguinte.

Todo artefato cientÃ­fico deve registrar arquivo, SHA-256, cutoff, seed quando aplicÃ¡vel e versÃ£o/esquema. O `smart_data_quality_gate.py` Ã© o gate operacional existente; falha de integridade bloqueia promoÃ§Ã£o.

Dataset SHA-256 atual: `287afcdb89ba822c6e4acc848a80583a17653d646581d2a582cad3abc1947c60`.
