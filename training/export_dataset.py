"""Monta o dataset do classificador de escopo (SFT).

Dois passos, para que nenhum rótulo "de regra" vire gabarito sem revisão humana:

  1) coletar  -> data/candidatos.jsonl
     - itens de licitação do LicitaGym (Supabase, só service_role: rode local, nunca no Colab);
     - objetos de licitações do Sesc pela API de dados abertos (pública), para ganhar volume e variedade.
     Cada candidato leva o rótulo atual das regras (rotulo_regra), só como dica para a revisão.

  2) montar   -> data/{train,val,test}.jsonl  (formato {"id","grupo","prompt","response"})
     Junta candidatos com data/rotulos.csv (id,categoria,revisado_por) e usa SÓ linhas revisadas.
     Split 70/15/15 por licitação (itens do mesmo certame nunca vazam entre treino e teste).

Uso:
  export SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...
  python training/export_dataset.py coletar --sesc-ufs sp,rj,sc,go --sesc-max 400 \
      --coletor-licitagym ../LicitaGym/services/coletor-externo
  python training/rotular_gemini.py            # pré-rótulo para revisão (opcional)
  python training/export_dataset.py montar
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Garante que podemos importar módulos auxiliares na mesma pasta
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from comum import ROTULOS, dividir, normalizar, para_sft  # noqa: E402
except ImportError:
    # Fallback caso o arquivo comum.py ainda não exista ou tenha outro nome
    ROTULOS = ["forte", "fraco", "piso", "borracha", "obra_piso", "manutencao", "fora"]
    def dividir(regs, semente=42):
        import random
        random.seed(semente)
        random.shuffle(regs)
        n = len(regs)
        n_train = int(n * 0.7)
        n_val = int(n * 0.15)
        return {
            "train": regs[:n_train],
            "val": regs[n_train:n_train+n_val],
