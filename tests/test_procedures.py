"""Procedures: caminho feliz, erros de negocio e valores-limite (RN-01 a RN-06)."""
from conftest import dec, expect_error

# IDs conhecidos dos dados de exemplo (gerados na ordem de insercao):
#   clientes: 1 Ana, 2 Bruno (PADRAO, 2 itens abertos), 4 Diego (multa aberta), 5 Elisa, 6 Fabio (PREMIUM)
#   equipamentos: 1 FUR-001 (alugado), 2 FUR-002 e 8 ASP-001 (disponiveis), 12 COMP-001 (nunca alugado)
#   locacoes abertas: 9 (vence D+2), 10 (atrasada 1 dia), 11 (VENCE HOJE), 12 (2 itens), 13


def test_registrar_caminho_feliz(db):
    loc = db.registrar(5, 12, 5)
    assert db.one("SELECT status, data_prevista - data_saida FROM locacao WHERE locacao_id = ?", loc) == ("ABERTA", 5)
    assert db.scalar("SELECT status FROM equipamento WHERE equipamento_id = 12") == "ALUGADO"
    assert dec(db.scalar("SELECT valor_diaria_cobrada FROM item_locacao WHERE locacao_id = ?", loc)) == dec(45)


def test_registrar_prazo_15_ok_e_16_erro(db):
    assert db.registrar(5, 12, 15) is not None          # fronteira: 15 dias e aceito
    db.rollback()
    expect_error(db, "EQL-001", lambda: db.registrar(5, 12, 16))   # 16 dias e rejeitado


def test_registrar_cliente_inexistente(db):
    expect_error(db, "EQL-002", lambda: db.registrar(999, 12, 3))


def test_registrar_cliente_com_multa_aberta(db):
    expect_error(db, "EQL-003", lambda: db.registrar(4, 12, 3))


def test_registrar_limite_do_perfil_3_ok_4_erro(db):
    db.registrar(2, 2, 3)                                # Bruno tinha 2 abertos -> 3o item: ok (fronteira)
    expect_error(db, "EQL-004", lambda: db.registrar(2, 8, 3))     # 4o item: bloqueado


def test_registrar_equipamento_ja_alugado(db):
    expect_error(db, "EQL-005", lambda: db.registrar(5, 1, 3))


def test_devolver_com_atraso_gera_multa(db):
    db.devolver(10)                                      # venceu ontem: 1 dia * 10% * 60 = 6.00
    assert dec(db.scalar("SELECT valor FROM multa WHERE locacao_id = 10 AND tipo = 'ATRASO'")) == dec(6)
    assert db.scalar("SELECT status FROM locacao WHERE locacao_id = 10") == "DEVOLVIDA"
    assert db.scalar("SELECT status FROM equipamento WHERE equipamento_id = 4") == "DISPONIVEL"


def test_devolver_no_dia_do_vencimento_nao_gera_multa(db):
    db.devolver(11)                                      # fronteira: vence hoje, devolvido hoje
    assert db.scalar("SELECT COUNT(*) FROM multa WHERE locacao_id = 11") == 0
    assert db.scalar("SELECT status FROM locacao WHERE locacao_id = 11") == "DEVOLVIDA"


def test_devolver_multa_respeita_teto_de_50_por_cento(db):
    # locacao 9: diaria 20, 5 dias contratados (valor 100). 40 dias de atraso => 10%*20*40 = 80, teto = 50
    prevista = db.scalar("SELECT data_prevista FROM locacao WHERE locacao_id = 9")
    db.devolver(9, db.scalar("SELECT data_prevista + 40 FROM locacao WHERE locacao_id = 9"))
    assert prevista is not None
    assert dec(db.scalar("SELECT valor FROM multa WHERE locacao_id = 9 AND tipo = 'ATRASO'")) == dec(50)


def test_devolver_com_avaria(db):
    db.devolver(12, None, 3)                             # SER-001 (reposicao 600) => 15% = 90.00
    assert dec(db.scalar("SELECT valor FROM multa WHERE locacao_id = 12 AND tipo = 'AVARIA'")) == dec(90)
    assert db.scalar("SELECT status FROM equipamento WHERE equipamento_id = 3") == "MANUTENCAO"
    assert db.scalar("SELECT status FROM equipamento WHERE equipamento_id = 1") == "DISPONIVEL"
    assert db.scalar("SELECT avaria FROM item_locacao WHERE locacao_id = 12 AND equipamento_id = 3") == "S"


def test_devolver_locacao_inexistente(db):
    expect_error(db, "EQL-006", lambda: db.devolver(9999))


def test_devolver_locacao_ja_devolvida(db):
    expect_error(db, "EQL-007", lambda: db.devolver(1))


def test_devolver_avaria_de_equipamento_de_outra_locacao(db):
    expect_error(db, "EQL-008", lambda: db.devolver(12, None, 12))


def test_devolver_antes_da_saida(db):
    expect_error(db, "EQL-009", lambda: db.devolver(
        13, db.scalar("SELECT data_saida - 1 FROM locacao WHERE locacao_id = 13")))
