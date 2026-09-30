import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import avaliar  # noqa: E402
import export_dataset  # noqa: E402
from comum import ROTULOS, dividir, ler_resposta, montar_prompt, montar_resposta, para_sft  # noqa: E402


def _regs(n_lic=40, itens=5):
    rot = list(ROTULOS)
    return [{"id": f"i{l}-{k}", "grupo": f"lic{l}", "descricao": f"item {k}", "categoria": rot[(l + k) % len(rot)]}
            for l in range(n_lic) for k in range(itens)]


def test_split_por_licitacao_sem_vazamento_e_deterministico():
    a, b = dividir(_regs()), dividir(_regs())
    assert a == b
    grupos = {n: {r["grupo"] for r in v} for n, v in a.items()}
    assert not (grupos["train"] & grupos["val"]) and not (grupos["train"] & grupos["test"]) and not (grupos["val"] & grupos["test"])
    total = sum(len(v) for v in a.values())
    assert total == 200 and 0.6 < len(a["train"]) / total < 0.8


@pytest.mark.parametrize("saida,esperado", [
    ('{"categoria": "piso"}', "piso"),
    ('Resposta: {"categoria":"obra_piso"} <end_of_turn>', "obra_piso"),
    ("categoria forte", "forte"),
    ('{"categoria": "academia"}', None),
    ("", None),
])
def test_ler_resposta(saida, esperado):
    assert ler_resposta(saida) == esperado


def test_prompt_e_resposta():
    p = montar_prompt("Placa emborrachada 1x1", "Aquisição de piso para academia")
    assert p.endswith("Item: Placa emborrachada 1x1") and "Objeto da licitação:" in p
    assert ler_resposta(montar_resposta("piso")) == "piso"
    with pytest.raises(ValueError):
        montar_resposta("academia")
    s = para_sft({"id": "x", "licitacao_id": 7, "descricao": "Bola", "categoria": "fraco"})
    assert s["grupo"] == "7" and json.loads(s["response"]) == {"categoria": "fraco"}


def test_metricas_macro_f1():
    gab = {"a": "piso", "b": "piso", "c": "forte", "d": "fora"}
    m = avaliar.metricas(gab, {"a": "piso", "b": "forte", "c": "forte", "d": None})
    assert m["acuracia"] == 0.5 and m["saidas_invalidas"] == 1
    assert m["por_rotulo"]["piso"]["recall"] == 0.5 and m["por_rotulo"]["forte"]["precisao"] == 0.5
    assert 0 < m["macro_f1"] < 1


def test_montar_usa_so_rotulos_revisados(tmp_path, monkeypatch):
    monkeypatch.setattr(export_dataset, "DADOS", tmp_path)
    regs = _regs(10, 3)
    with open(tmp_path / "candidatos.jsonl", "w", encoding="utf-8") as f:
        for r in regs:
            f.write(json.dumps({k: v for k, v in r.items() if k != "categoria"}) + "\n")
    with open(tmp_path / "rotulos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "categoria", "revisado_por"])
        w.writeheader()
        for i, r in enumerate(regs):
            w.writerow({"id": r["id"], "categoria": r["categoria"], "revisado_por": "marcelo" if i % 2 == 0 else ""})
        w.writerow({"id": "fantasma", "categoria": "piso", "revisado_por": "marcelo"})
    export_dataset.main(["montar"])
    linhas = sum(1 for n in ("train", "val", "test") for _ in open(tmp_path / f"{n}.jsonl", encoding="utf-8"))
    assert linhas == 15  # só as revisadas que existem nos candidatos
    resumo = json.loads((tmp_path / "resumo.json").read_text(encoding="utf-8"))
    assert sum(v["total"] for v in resumo.values()) == 15
