# SMART-MEGA V6 — contrato de testemunho criptográfico PIT

Escopo: somente leitura, diagnóstico não produtivo, sem autorização para gerar cartões. Chaves privadas não são armazenadas no projeto.

- `smart_video_pit_evidence.py` vincula contest anterior, corte temporal declarado, SHA-256 do checkpoint físico, SHA-256 dos bytes de um quadro, assinatura Ed25519 e chave pública previamente autorizada por autoridade externa.
- Detecta assinaturas inválidas, chaves revogadas, dados de resultado, arquivos sintéticos, timestamps inválidos, hashes falsos, links simbólicos e contaminação de schema.
- Uma assinatura válida NÃO comprova, sozinha, disponibilidade antes do cutoff: o emissor pode assinar hoje uma data passada. O contrato depende ainda de recibo temporal independente, proveniente de autoridade externa verificável, que este componente não declara possuir.
- O resultado `SIGNED_FRAME_WITNESS_ONLY` vincula bytes; não comprova frames reais nem causa física de previsão. `pit_independently_attested=false`; `media_source_authorized=false`; `predictive_weight=0.0`.
- O consumidor B2 aceita testemunhos como anexos opcionais e conta vínculos assinados sem alterar a classificação PIT nem produzir pesos.
- Sem quadros oficiais autorizados, recibos temporais externos válidos e comparações prospectivas fora da amostra, contribuição preditiva permanece `NOT_MEASURED`.

Os testes positivos usam chaves e bytes gerados exclusivamente durante o ensaio; nunca representam mídia da CAIXA ou autenticação temporal real.
