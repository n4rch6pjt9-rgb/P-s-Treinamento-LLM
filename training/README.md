# Pós-treino (SFT) do classificador de escopo LicitaGym

Fine-tuning de um LLM pequeno (Gemma 3 1B-it) com **Tunix + LoRA**. O modelo lê a descrição do item de licitação (e o
objeto) e responde a categoria de escopo da Playfit:

`forte` · `fraco` · `piso` · `borracha` · `obra_piso` · `manutencao` · `fora`

O `src/` deste repositório é o *Tunix Architecture Explorer* (documentação visual). O código de treino fica aqui em
`training/`.

## Por que e quando

- **Por quê:** hoje o escopo sai de regras de texto (`coletor/escopo.py` + taxonomia de pisos v0.2 no LicitaGym). Elas erram
  em casos como "solução de gestão para academia", que vira `forte`, e deixam cerca de 84% dos itens do banco sem categoria.
- **Quando vale:** o SFT só compensa com **1.500 a 2.000 exemplos revisados por humano**. Abaixo disso, use o Gemini com
  alguns exemplos no prompt (`rotular_gemini.py`) direto.
- **Critério de aceite:** o modelo só vai para produção se o **macro-F1 no teste superar o das regras**.

## Fluxo

```
coletar  ──▶ candidatos.jsonl ──▶ rotular_gemini ──▶ rotulos_sugeridos.csv ──(revisão humana)──▶ rotulos.csv
                                                                                                    │
                                          test.jsonl ◀── montar (split por licitação 70/15/15) ◀────┘
                                              │
                        sft_tunix.ipynb (Colab) ──▶ preds_sft.jsonl ──▶ avaliar.py (vs regras) ──▶ aceite?
```

1. **Coletar** (local, nunca no Colab):
   ```bash
   export SUPABASE_URL=https://<projeto>.supabase.co SUPABASE_SERVICE_ROLE_KEY=...   # itens do LicitaGym
   python training/export_dataset.py coletar --sesc-ufs sp,rj,sc,go,rs,pr --sesc-max 400 \
       --coletor-licitagym ../LicitaGym/services/coletor-externo
   ```
   - **Itens do LicitaGym:** `licitacao_itens` + objeto da licitação. A leitura exige `service_role`; a chave fica só no seu ambiente.
   - **Objetos do Sesc:** vêm da **API de dados abertos** (`transparencia-{uf}.sesc.com.br/.../api/213`), que é pública e oficial.
     Dão volume e variedade, inclusive exemplos `fora`.
   - **`rotulo_regra`:** é só uma **dica** para a revisão, nunca o gabarito.
2. **Pré-rótulo** (opcional): `GEMINI_API_KEY=... python training/rotular_gemini.py --limite 500`.
   - Gera `rotulos_sugeridos.csv`, com as discordâncias entre regra e Gemini no topo.
3. **Revisão humana:**
   - Abra o CSV numa planilha, corrija a coluna `categoria` e preencha `revisado_por`.
   - Salve como `training/data/rotulos.csv`. **Só linhas revisadas entram no treino.**
4. **Montar:** `python training/export_dataset.py montar`.
   - Gera `train/val/test.jsonl` e `resumo.json`.
   - O split é por licitação: itens do mesmo certame não vazam entre treino e teste.
5. **Treinar:**
   - Suba os `.jsonl` para `MyDrive/licitagym-treino/`.
   - Abra `training/sft_tunix.ipynb` no Colab com **TPU v5e-1** ou **GPU T4**. O TPU v2-8 saiu do Colab grátis em set/2025.
   - Crie o Secret `HF_TOKEN`, depois de aceitar a licença do `google/gemma-3-1b-it` no Hugging Face.
6. **Avaliar contra as regras:**
   ```bash
   python training/avaliar.py --gabarito training/data/test.jsonl --pred sft=preds_sft.jsonl \
       --baseline-regras ../LicitaGym/services/coletor-externo
   ```

## Arquivos

| Arquivo | O que faz |
|---|---|
| `comum.py` | rótulos, prompt, formato da resposta (`{"categoria": ...}`), leitura da saída, split por grupo |
| `export_dataset.py` | `coletar` (Supabase + API Sesc) e `montar` (só rótulos revisados) |
| `rotular_gemini.py` | pré-rótulo em lote com Gemini para revisão |
| `config/sft_classificador.yaml` | modelo, LoRA, dados, treino, avaliação |
| `sft_tunix.ipynb` | Colab: instala Tunix, carrega Gemma 3 1B, aplica LoRA (qwix), treina (`PeftTrainer`), avalia e exporta safetensors mesclado |
| `avaliar.py` | macro-F1, acurácia, confusão; baseline com as regras do coletor |
| `tests/` | `pytest training/tests` |

## Segurança e dados

- **`training/data/` é ignorado pelo git:** candidatos, rótulos e splits ficam fora do repositório. Eles têm texto público de licitação, mas os rótulos são da empresa.
- **Nada de chave no notebook:** só o `HF_TOKEN`, pelos Secrets do Colab. A `service_role` do Supabase fica só na máquina local.
- **API do Sesc:** a coleta usa 1 s de pausa entre chamadas e *User-Agent* só em ASCII. A API responde 500 quando o *User-Agent* tem acento.

## Referências

- Tunix: https://github.com/google/tunix. API conferida no commit `96431d6`, com base no notebook `examples/qlora_gemma.ipynb`.
- Não verificado em hardware:
  - a malha para 8 dispositivos;
  - o layout exato dos checkpoints na versão main;
  - o desempenho na T4.
- Rode primeiro com `max_steps` baixo.
