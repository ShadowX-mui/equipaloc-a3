"""Duas sessoes disputando o MESMO equipamento: a segunda espera o lock e leva EQL-005.
Este teste faz COMMIT de verdade (precisa, para a 2a sessao enxergar), entao limpa tudo no final."""
import threading
import time

import pytest

from conftest import DB, DBS, connect


@pytest.mark.parametrize("kind", DBS)
def test_duas_sessoes_no_mesmo_equipamento(kind):
    a, b = DB(kind, connect(kind)), DB(kind, connect(kind))
    resultado = {}
    loc_a = None
    try:
        loc_a = a.registrar(5, 12, 3)            # sessao A segura o lock do equipamento 12 (sem commit)

        def sessao_b():
            try:
                b.registrar(7, 12, 3)            # deve ficar BLOQUEADA ate A decidir
                resultado["erro"] = None
            except Exception as e:  # noqa: BLE001
                resultado["erro"] = str(e)

        t = threading.Thread(target=sessao_b)
        t.start()
        time.sleep(2)
        assert t.is_alive(), "a sessao B deveria estar esperando o lock da sessao A"
        a.conn.commit()                          # A confirma; B acorda e enxerga ALUGADO
        t.join(timeout=30)
        assert not t.is_alive()
        assert "EQL-005" in (resultado.get("erro") or ""), resultado
    finally:
        b.rollback()
        a.rollback()
        if loc_a is not None:                    # limpeza do que o teste commitou
            a.exec("DELETE FROM item_locacao WHERE locacao_id = ?", loc_a)
            a.exec("DELETE FROM auditoria_locacao WHERE locacao_id = ?", loc_a)
            a.exec("DELETE FROM locacao WHERE locacao_id = ?", loc_a)
            a.exec("UPDATE equipamento SET status = 'DISPONIVEL' WHERE equipamento_id = 12")
            a.conn.commit()
        a.conn.close()
        b.conn.close()
