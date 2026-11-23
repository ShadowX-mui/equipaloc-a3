"""Consultas: resultados esperados (calculados a partir dos dados de exemplo) e igualdade entre os dois bancos."""
import pytest

from conftest import dec, norm_rows

QUERIES = [f"Q{n:02d}" for n in range(1, 11)]


def rodar(db, consultas, q):
    return norm_rows(db.all(consultas[db.kind][q]))


def test_q01_receita_por_categoria(db, consultas):
    assert rodar(db, consultas, "Q01") == [
        ("JARDIM", dec(4), dec(825)), ("ELETRICA", dec(5), dec(800)),
        ("CONSTRUCAO", dec(3), dec(625)), ("LIMPEZA", dec(3), dec(550))]


def test_q03_clientes_recorrentes_inclui_fronteira_de_exatamente_2(db, consultas):
    assert rodar(db, consultas, "Q03") == [
        ("Ana Teste", dec(3)), ("Bruno Exemplo", dec(3)), ("Carla Modelo", dec(2)), ("Fabio Amostra", dec(2))]


def test_q04_ranking_com_empate_no_primeiro_lugar(db, consultas):
    r = rodar(db, consultas, "Q04")
    assert r[:2] == [("FUR-001", dec(3), dec(1)), ("SER-001", dec(3), dec(1))]
    assert r[2][2] == dec(3)                              # RANK pula a posicao 2


def test_q02_fronteira_vence_hoje(db, consultas):
    situacoes = {(r[0], r[2]): r[3] for r in rodar(db, consultas, "Q02")}
    assert situacoes[(11, "LAV-001")] == "VENCE HOJE"
    assert situacoes[(10, "BET-001")] == "ATRASADA"
    assert situacoes[(9, "ESC-001")] == "NO PRAZO"


def test_q07_anti_join_equipamento_nunca_alugado(db, consultas):
    assert rodar(db, consultas, "Q07") == [("COMP-001",)]


def test_q08_subconsulta_correlacionada(db, consultas):
    assert [r[0] for r in rodar(db, consultas, "Q08")] == [
        "AND-001", "BET-001", "COMP-001", "FUR-002", "LAV-001", "MOT-001"]


def test_q09_rollup_total_geral(db, consultas):
    r = rodar(db, consultas, "Q09")
    assert r[-1] == (None, None, dec(4), dec(200.50))     # total geral vem por ultimo
    assert len(r) == 6                                    # 3 combinacoes + 2 subtotais + total


def test_q10_divisao_relacional(db, consultas):
    assert rodar(db, consultas, "Q10") == [("Fabio Amostra",)]


@pytest.mark.parametrize("q", QUERIES)
def test_resultado_identico_nos_dois_bancos(conexoes, consultas, q):
    from conftest import DB
    pg, ora = DB("postgres", conexoes["postgres"]), DB("oracle", conexoes["oracle"])
    rp, ro = rodar(pg, consultas, q), rodar(ora, consultas, q)
    assert rp == ro, f"{q} difere entre PostgreSQL e Oracle"
    assert len(rp) > 0
