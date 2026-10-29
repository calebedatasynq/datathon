"""Os dois conjuntos usam o mesmo motor e mantêm seus templates próprios."""

import csv

from agente import config
from agente.dados_base import estabelecimentos_da_base
from agente.perfil import _entrada, perfil_de_entrada, score_empresa
from scripts import exportar_templates


def test_bases_tem_templates_proprios_e_chaves_distintas():
    pastas = [config.RAIZ / "Seguro_Empresarial_Desenvolvimento", config.RAIZ / "Seguro_Empresarial_Teste_Comum"]
    chaves = []
    for pasta, esperado in zip(pastas, [2978, 144]):
        assert all((pasta / nome).is_file() for nome in ["template_resultado_times.csv", "template_coberturas_times.csv"])
        pares = exportar_templates._ordem(pasta)
        assert len(pares) == esperado and len(set(pares)) == esperado
        chaves.append(set(pares))
    assert chaves[0].isdisjoint(chaves[1])


def test_exportacao_desenvolvimento_usa_score_e_cabecalhos_originais(tmp_path, monkeypatch):
    pasta = config.RAIZ / "Seguro_Empresarial_Desenvolvimento"
    preparo = config.DIR_MOTOR / "dados" / "preparados" / "base_desenvolvimento.csv"
    empresa_id, imovel_id = exportar_templates._ordem(pasta)[0]
    monkeypatch.setattr(exportar_templates, "_ordem", lambda _: [(empresa_id, imovel_id)])
    n_resultado, n_coberturas = exportar_templates._exportar_base(pasta, preparo, tmp_path, conversa=False)
    assert n_resultado == 1 and n_coberturas >= 5
    with preparo.open(encoding="utf-8-sig", newline="") as f:
        entrada = next(linha for linha in csv.DictReader(f) if linha["imovel_id"] == imovel_id)
    perfil = perfil_de_entrada(_entrada(entrada))
    assert perfil.plano == score_empresa(_entrada(entrada))["plano_sugerido"]
    assert estabelecimentos_da_base(pasta)[imovel_id].empresa_id == empresa_id
    for nome in ["template_resultado_times.csv", "template_coberturas_times.csv"]:
        with (tmp_path / nome).open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == exportar_templates._cabecalho(pasta, nome)
            rows = list(reader)
            assert all((r["empresa_id"], r["imovel_id"]) == (empresa_id, imovel_id) for r in rows)
            if nome == "template_resultado_times.csv":
                assert rows[0]["plano_recomendado"] == perfil.plano
