"""Aplicacao Python (psycopg 3 e python-oracledb): conecta nos dois bancos, consulta com BIND,
chama procedure, trata o erro de negocio e controla a transacao (commit/rollback).
Rodar:  docker compose --profile apps run --rm app-python
O demo termina com ROLLBACK para nao alterar os dados de exemplo."""
import os
from decimal import Decimal

import oracledb
import psycopg

CLIENTE_OK, CLIENTE_COM_MULTA, EQUIP_LIVRE, EQUIP_ALUGADO = 5, 4, 12, 1


def demo_postgres():
    print("\n=== PostgreSQL (psycopg 3) ===")
    with psycopg.connect(host=os.environ.get("PG_HOST", "localhost"), dbname="a3", user="a3", password="a3lab") as conn:
        cur = conn.cursor()
        # consulta com bind (%s) - nunca concatenar valores no SQL
        cur.execute("SELECT nome, email FROM cliente WHERE cliente_id = %s", (CLIENTE_OK,))
        print("cliente:", cur.fetchone())

        # procedure com INOUT: devolve o id da locacao criada
        cur.execute("CALL sp_registrar_locacao(%s, %s, %s, CAST(%s AS INTEGER))", (CLIENTE_OK, EQUIP_LIVRE, 3, None))
        loc_id = cur.fetchone()[0]
        print("locacao criada:", loc_id)

        # No PostgreSQL um erro ABORTA a transacao inteira; o SAVEPOINT permite tratar o erro e continuar.
        cur.execute("SAVEPOINT antes_do_erro")
        try:
            cur.execute("CALL sp_registrar_locacao(%s, %s, %s, CAST(%s AS INTEGER))", (CLIENTE_COM_MULTA, EQUIP_LIVRE, 3, None))
        except psycopg.errors.RaiseException as e:
            print("erro de negocio tratado:", str(e).splitlines()[0])
            cur.execute("ROLLBACK TO SAVEPOINT antes_do_erro")

        # NUMERIC deve ir como Decimal (nao float) para nao perder precisao
        cur.execute("SELECT valor_diaria FROM equipamento WHERE valor_diaria = %s", (Decimal("45.00"),))
        print("equipamentos de diaria 45.00:", cur.fetchall())

        # devolucao no mesmo fluxo; depois desfaz tudo (demo nao suja o banco)
        cur.execute("CALL sp_devolver_locacao(%s, CAST(%s AS DATE), CAST(%s AS INTEGER))", (loc_id, None, None))
        cur.execute("SELECT status FROM locacao WHERE locacao_id = %s", (loc_id,))
        print("status apos devolver:", cur.fetchone()[0])
        conn.rollback()
        print("ROLLBACK feito: nada foi gravado")


def demo_oracle():
    print("\n=== Oracle (python-oracledb, modo thin) ===")
    with oracledb.connect(user="a3", password="a3lab", dsn=f"{os.environ.get('ORA_HOST', 'localhost')}:1521/XEPDB1") as conn:
        cur = conn.cursor()
        cur.execute("SELECT nome, email FROM cliente WHERE cliente_id = :id", id=CLIENTE_OK)   # bind nomeado
        print("cliente:", cur.fetchone())

        loc_id = cur.var(int)                                  # parametro OUT
        cur.callproc("sp_registrar_locacao", [CLIENTE_OK, EQUIP_LIVRE, 3, loc_id])
        print("locacao criada:", int(loc_id.getvalue()))

        try:
            cur.callproc("sp_registrar_locacao", [CLIENTE_COM_MULTA, EQUIP_LIVRE, 3, cur.var(int)])
        except oracledb.DatabaseError as e:
            (erro,) = e.args
            # erro.message ja comeca com "ORA-20003:"; nao repetir o prefixo
            print(f"erro de negocio tratado: {erro.message.splitlines()[0]}")

        cur.callproc("sp_devolver_locacao", [int(loc_id.getvalue()), None, None])
        cur.execute("SELECT status FROM locacao WHERE locacao_id = :id", id=int(loc_id.getvalue()))
        print("status apos devolver:", cur.fetchone()[0])
        conn.rollback()
        print("ROLLBACK feito: nada foi gravado")


if __name__ == "__main__":
    # A3_DBS=postgres (padrao) roda so o PostgreSQL; A3_DBS=postgres,oracle roda tambem o extra Oracle
    dbs = [d.strip() for d in os.environ.get("A3_DBS", "postgres").split(",")]
    if "postgres" in dbs:
        demo_postgres()
    if "oracle" in dbs:
        demo_oracle()
