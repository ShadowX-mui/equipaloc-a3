"""Triggers: regra valida mesmo para INSERT direto (sem passar pela procedure) e auditoria."""
from conftest import expect_error


def test_trigger_barra_insert_direto_em_equipamento_alugado(db):
    expect_error(db, "EQL-005", lambda: db.exec(
        "INSERT INTO item_locacao (locacao_id, equipamento_id, valor_diaria_cobrada) VALUES (9, 1, 25)"))


def test_trigger_marca_equipamento_como_alugado_no_insert_direto(db):
    db.exec("INSERT INTO item_locacao (locacao_id, equipamento_id, valor_diaria_cobrada) VALUES (9, 12, 45)")
    assert db.scalar("SELECT status FROM equipamento WHERE equipamento_id = 12") == "ALUGADO"


def test_trigger_barra_equipamento_em_manutencao(db):
    expect_error(db, "EQL-005", lambda: db.exec(
        "INSERT INTO item_locacao (locacao_id, equipamento_id, valor_diaria_cobrada) VALUES (9, 9, 40)"))


def test_trigger_auditoria_registra_mudanca_de_status(db):
    antes = db.scalar("SELECT COUNT(*) FROM auditoria_locacao WHERE locacao_id = 11")
    db.devolver(11)
    row = db.one("SELECT operacao, status_anterior, status_novo FROM auditoria_locacao "
                 "WHERE locacao_id = 11 AND operacao = 'UPDATE'")
    assert antes == 0
    assert row == ("UPDATE", "ABERTA", "DEVOLVIDA")


def test_trigger_auditoria_registra_insert_da_locacao(db):
    loc = db.registrar(5, 12, 3)
    assert db.scalar("SELECT COUNT(*) FROM auditoria_locacao WHERE locacao_id = ? AND operacao = 'INSERT'", loc) == 1
