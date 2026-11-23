"""Constraints barrando dado invalido e ON DELETE (criterios: DDL)."""
from datetime import date, timedelta

from conftest import expect_error


def test_check_diaria_positiva(db):
    expect_error(db, "ck_equip_diaria", lambda: db.exec(
        "INSERT INTO equipamento (categoria_id, codigo, descricao, valor_diaria, valor_reposicao, status) "
        "VALUES (1, 'X-001', 'teste', 0, 100, 'DISPONIVEL')"))


def test_check_prazo_maximo_15_dias(db):
    hoje = date.today()
    expect_error(db, "ck_locacao_prazo", lambda: db.exec(
        "INSERT INTO locacao (cliente_id, data_saida, data_prevista, status) VALUES (1, ?, ?, 'ABERTA')",
        hoje, hoje + timedelta(days=16)))


def test_unique_codigo_equipamento(db):
    expect_error(db, "uk_equip_codigo", lambda: db.exec(
        "INSERT INTO equipamento (categoria_id, codigo, descricao, valor_diaria, valor_reposicao) "
        "VALUES (1, 'FUR-001', 'duplicado', 10, 100)"))


def test_fk_item_exige_locacao_existente(db):
    # equipamento 12 esta DISPONIVEL, entao o trigger passa e quem barra e a FK
    expect_error(db, "fk_item_locacao", lambda: db.exec(
        "INSERT INTO item_locacao (locacao_id, equipamento_id, valor_diaria_cobrada) VALUES (99999, 12, 45)"))


def test_on_delete_restrict_equipamento_com_item(db):
    expect_error(db, "fk_item_equipamento", lambda: db.exec(
        "DELETE FROM equipamento WHERE codigo = 'FUR-001'"))


def test_on_delete_cascade_apaga_itens_da_locacao(db):
    # locacao 1 nao tem multa, entao pode ser apagada; seus itens somem junto (CASCADE)
    assert db.scalar("SELECT COUNT(*) FROM item_locacao WHERE locacao_id = 1") == 1
    db.exec("DELETE FROM locacao WHERE locacao_id = 1")
    assert db.scalar("SELECT COUNT(*) FROM item_locacao WHERE locacao_id = 1") == 0


def test_on_delete_restrict_locacao_com_multa(db):
    expect_error(db, "fk_multa_locacao", lambda: db.exec("DELETE FROM locacao WHERE locacao_id = 2"))
