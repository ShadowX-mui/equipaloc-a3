"""Infra dos testes: um adaptador unico (DB) para PostgreSQL e Oracle.
SQL nos testes usa '?' como placeholder; o adaptador converte para %s (PG) ou :1,:2 (Oracle).
Cada teste roda numa transacao que sofre ROLLBACK no fim (as procedures nao fazem COMMIT)."""
import os
import re
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import oracledb
import psycopg
import pytest

SQL_DIR = Path(os.environ.get("SQL_DIR", "/app/sql"))
# Bancos testados: A3_DBS=postgres (padrao, caminho principal) ou A3_DBS=postgres,oracle (extra opcional)
DBS = [d.strip() for d in os.environ.get("A3_DBS", "postgres").split(",") if d.strip()]
DIRS = {"postgres": "postgresql", "oracle": "oracle"}


def connect(kind, tentativas=30):
    ultimo = None
    for _ in range(tentativas):
        try:
            if kind == "postgres":
                return psycopg.connect(host=os.environ.get("PG_HOST", "localhost"), port=5432,
                                       dbname="a3", user="a3", password="a3lab")
            return oracledb.connect(user="a3", password="a3lab",
                                    dsn=f"{os.environ.get('ORA_HOST', 'localhost')}:1521/XEPDB1")
        except Exception as e:  # banco ainda subindo
            ultimo = e
            time.sleep(2)
    raise RuntimeError(f"nao conectou em {kind}: {ultimo}")


class DB:
    def __init__(self, kind, conn):
        self.kind, self.conn = kind, conn

    def _sql(self, sql):
        n = iter(range(1, 100))
        if self.kind == "postgres":
            return re.sub(r"\?", "%s", sql)
        return re.sub(r"\?", lambda m: f":{next(n)}", sql)

    def exec(self, sql, *params):
        cur = self.conn.cursor()
        cur.execute(self._sql(sql), params)
        return cur

    def all(self, sql, *params):
        return self.exec(sql, *params).fetchall()

    def one(self, sql, *params):
        return self.exec(sql, *params).fetchone()

    def scalar(self, sql, *params):
        row = self.one(sql, *params)
        return None if row is None else row[0]

    def rollback(self):
        self.conn.rollback()

    # ---- chamadas das procedures (mesma assinatura logica nos dois bancos) ----
    def registrar(self, cliente, equipamento, dias):
        cur = self.conn.cursor()
        if self.kind == "postgres":
            cur.execute("CALL sp_registrar_locacao(%s, %s, %s, CAST(%s AS INTEGER))",
                        (cliente, equipamento, dias, None))
            return cur.fetchone()[0]
        out = cur.var(int)
        cur.callproc("sp_registrar_locacao", [cliente, equipamento, dias, out])
        return int(out.getvalue())

    def devolver(self, locacao, data=None, avaria_eq=None):
        cur = self.conn.cursor()
        if self.kind == "postgres":
            cur.execute("CALL sp_devolver_locacao(%s, CAST(%s AS DATE), CAST(%s AS INTEGER))",
                        (locacao, data, avaria_eq))
        else:
            cur.callproc("sp_devolver_locacao", [locacao, data, avaria_eq])


def dec(v):
    return Decimal(str(v)).quantize(Decimal("0.01"))


def norm(v):
    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
        return dec(v)
    if isinstance(v, (date, datetime)):
        return str(v)[:10]
    return v


def norm_rows(rows):
    return [tuple(norm(c) for c in r) for r in rows]


def expect_error(db, fragmento, fn):
    """Exige que fn() falhe e que a mensagem do banco contenha `fragmento` (codigo EQL-00n ou nome da constraint)."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001 - os dois drivers usam hierarquias de excecao diferentes
        msg = str(e)
        db.rollback()
        assert fragmento.lower() in msg.lower(), f"esperava '{fragmento}' em: {msg}"
        return
    db.rollback()
    pytest.fail(f"esperava erro contendo '{fragmento}', mas nao houve erro")


def carregar_consultas(dialeto):
    """Le NN_consultas.sql e devolve {'Q01': sql, ...} (sem comentarios e sem ';' final)."""
    texto = (SQL_DIR / dialeto / "03_consultas.sql").read_text(encoding="utf-8")
    partes = re.split(r"^-- @(Q\d\d)[^\n]*\n", texto, flags=re.M)
    consultas = {}
    for i in range(1, len(partes), 2):
        linhas = [l for l in partes[i + 1].splitlines() if not l.strip().startswith("--")]
        consultas[partes[i]] = "\n".join(linhas).strip().rstrip(";").strip()
    return consultas


@pytest.fixture(scope="session")
def conexoes():
    cs = {k: connect(k) for k in DBS}
    yield cs
    for c in cs.values():
        c.close()


@pytest.fixture(params=DBS)
def db(request, conexoes):
    d = DB(request.param, conexoes[request.param])
    d.rollback()
    yield d
    d.rollback()


@pytest.fixture(scope="session")
def consultas():
    return {k: carregar_consultas(DIRS[k]) for k in DBS}


def pytest_collection_modifyitems(config, items):
    """A comparacao entre bancos so existe quando os DOIS estao selecionados (A3_DBS=postgres,oracle)."""
    if {"postgres", "oracle"} <= set(DBS):
        return
    fora = [i for i in items if "resultado_identico_nos_dois_bancos" in i.name]
    if fora:
        config.hook.pytest_deselected(items=fora)
        items[:] = [i for i in items if i not in fora]
