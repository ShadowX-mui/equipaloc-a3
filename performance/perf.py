"""Mede o efeito dos 3 indices (criterio 5). Rode com:  docker compose run --rm perf
Cria uma massa de dados em ESQUEMA A PARTE (PostgreSQL: schema perf | Oracle: usuario a3_perf),
mede os planos e tempos ANTES, cria os indices, mede DEPOIS e grava performance/explain_antes_depois.txt.
Os tempos sao reais, medidos na maquina de quem roda: nada aqui e inventado."""
import os
import statistics
import time
from datetime import datetime
from pathlib import Path

import oracledb
import psycopg

SAIDA = Path("/app/performance/explain_antes_depois.txt")
DBS = [d.strip() for d in os.environ.get("A3_DBS", "postgres").split(",") if d.strip()]
EXECUCOES = 10
N_CLIENTES, N_LOCACOES, N_ITENS, N_EQUIP = 20000, 200000, 300000, 500

# Consultas medidas (a mesma logica nos dois bancos). {p} = prefixo do esquema.
CONSULTAS = [
    ("Q-A  FK locacao.cliente_id  (historico de um cliente)",
     "SELECT COUNT(*), MAX(data_saida) FROM {p}locacao WHERE cliente_id = 4242", "idx_locacao_cliente"),
    ("Q-B  FK item_locacao.equipamento_id  (locacoes de um equipamento)",
     "SELECT COUNT(*) FROM {p}item_locacao WHERE equipamento_id = 42", "idx_item_equipamento"),
    ("Q-C  busca: locacoes abertas ha muito tempo (status + data_prevista)",
     "SELECT COUNT(*) FROM {p}locacao WHERE status = 'ABERTA' AND data_prevista < {hoje} - 300",
     "idx_locacao_status_prevista"),
]
INDICES = [
    ("idx_locacao_cliente", "locacao (cliente_id)"),
    ("idx_item_equipamento", "item_locacao (equipamento_id)"),
    ("idx_locacao_status_prevista", "locacao (status, data_prevista)"),
]


def conectar(fn, tentativas=30):
    ultimo = None
    for _ in range(tentativas):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(2)
    raise RuntimeError(ultimo)


def tempo_ms(cur, sql):
    medidas = []
    for _ in range(EXECUCOES):
        t0 = time.perf_counter()
        cur.execute(sql)
        cur.fetchall()
        medidas.append((time.perf_counter() - t0) * 1000)
    return statistics.mean(medidas), min(medidas)


# ---------------------------------------------------------------- PostgreSQL
def pg_setup(cur):
    cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'perf'")
    if cur.fetchone():
        raise SystemExit("O esquema perf ja existe. Rode 'docker compose down -v' e suba de novo "
                         "(este script nao usa DROP: a massa so e criada num banco limpo).")
    cur.execute("CREATE SCHEMA perf")
    cur.execute("CREATE TABLE perf.locacao (locacao_id INTEGER PRIMARY KEY, cliente_id INTEGER NOT NULL, "
                "data_saida DATE NOT NULL, data_prevista DATE NOT NULL, status VARCHAR(10) NOT NULL)")
    cur.execute("CREATE TABLE perf.item_locacao (item_id INTEGER PRIMARY KEY, locacao_id INTEGER NOT NULL, "
                "equipamento_id INTEGER NOT NULL)")
    cur.execute(f"INSERT INTO perf.locacao SELECT g, 1 + (g * 7919) % {N_CLIENTES}, "
                f"CURRENT_DATE - (g % 365), CURRENT_DATE - (g % 365) + 5, "
                f"CASE WHEN g % 50 = 0 THEN 'ABERTA' ELSE 'DEVOLVIDA' END FROM generate_series(1, {N_LOCACOES}) g")
    cur.execute(f"INSERT INTO perf.item_locacao SELECT g, 1 + g % {N_LOCACOES}, 1 + (g * 31) % {N_EQUIP} "
                f"FROM generate_series(1, {N_ITENS}) g")
    cur.execute("ANALYZE perf.locacao")
    cur.execute("ANALYZE perf.item_locacao")


def pg_plano(cur, sql):
    cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql)
    return [r[0] for r in cur.fetchall()]


def pg_run():
    conn = conectar(lambda: psycopg.connect(host=os.environ.get("PG_HOST", "localhost"), dbname="a3",
                                            user="a3", password="a3lab", autocommit=True))
    cur = conn.cursor()
    pg_setup(cur)
    return roda(cur, "PostgreSQL 17", "perf.", "CURRENT_DATE", pg_plano,
                lambda c: (c.execute("ANALYZE perf.locacao"), c.execute("ANALYZE perf.item_locacao")),
                lambda c, nome, alvo: c.execute(f"CREATE INDEX {nome} ON perf.{alvo}"))


# ---------------------------------------------------------------- Oracle
def ora_setup(cur):
    cur.execute("SELECT COUNT(*) FROM user_tables WHERE table_name IN ('LOCACAO', 'ITEM_LOCACAO')")
    if cur.fetchone()[0]:
        raise SystemExit("As tabelas de performance do Oracle ja existem. Rode 'docker compose down -v' e suba de novo "
                         "(este script nao usa DROP: a massa so e criada num banco limpo).")
    cur.execute("CREATE TABLE locacao (locacao_id NUMBER(10) PRIMARY KEY, cliente_id NUMBER(10) NOT NULL, "
                "data_saida DATE NOT NULL, data_prevista DATE NOT NULL, status VARCHAR2(10) NOT NULL)")
    cur.execute("CREATE TABLE item_locacao (item_id NUMBER(10) PRIMARY KEY, locacao_id NUMBER(10) NOT NULL, "
                "equipamento_id NUMBER(10) NOT NULL)")
    cur.execute(f"INSERT INTO locacao SELECT LEVEL, 1 + MOD(LEVEL * 7919, {N_CLIENTES}), "
                f"TRUNC(SYSDATE) - MOD(LEVEL, 365), TRUNC(SYSDATE) - MOD(LEVEL, 365) + 5, "
                f"CASE WHEN MOD(LEVEL, 50) = 0 THEN 'ABERTA' ELSE 'DEVOLVIDA' END "
                f"FROM dual CONNECT BY LEVEL <= {N_LOCACOES}")
    cur.execute(f"INSERT INTO item_locacao SELECT LEVEL, 1 + MOD(LEVEL, {N_LOCACOES}), 1 + MOD(LEVEL * 31, {N_EQUIP}) "
                f"FROM dual CONNECT BY LEVEL <= {N_ITENS}")
    cur.connection.commit()
    ora_stats(cur)


def ora_stats(cur):
    for t in ("LOCACAO", "ITEM_LOCACAO"):
        cur.execute(f"BEGIN DBMS_STATS.GATHER_TABLE_STATS(USER, '{t}'); END;")


def ora_plano(cur, sql):
    cur.execute("EXPLAIN PLAN FOR " + sql)
    cur.execute("SELECT plan_table_output FROM TABLE(DBMS_XPLAN.DISPLAY())")
    return [r[0] for r in cur.fetchall()]


def ora_run():
    conn = conectar(lambda: oracledb.connect(user="a3_perf", password="a3perf",
                                             dsn=f"{os.environ.get('ORA_HOST', 'localhost')}:1521/XEPDB1"))
    cur = conn.cursor()
    ora_setup(cur)
    return roda(cur, "Oracle XE 21", "", "TRUNC(SYSDATE)", ora_plano, ora_stats,
                lambda c, nome, alvo: c.execute(f"CREATE INDEX {nome} ON {alvo}"))


# ---------------------------------------------------------------- comum
def roda(cur, titulo, prefixo, hoje, plano, estatisticas, criar_indice):
    out, resumo = [f"{'=' * 78}\n{titulo}   (massa: {N_LOCACOES} locacoes, {N_ITENS} itens)\n{'=' * 78}"], []
    antes = {}
    out.append("\n######## ANTES dos indices ########")
    for nome, sql, _ in CONSULTAS:
        q = sql.format(p=prefixo, hoje=hoje)
        out.append(f"\n--- {nome}\n{q}\n" + "\n".join(plano(cur, q)))
        antes[nome] = tempo_ms(cur, q)
        out.append(f"Tempo medido ({EXECUCOES} execucoes): media {antes[nome][0]:.3f} ms | minimo {antes[nome][1]:.3f} ms")
    for idx, alvo in INDICES:
        criar_indice(cur, idx, alvo)
    estatisticas(cur)
    out.append("\n######## DEPOIS dos indices ########")
    for nome, sql, idx in CONSULTAS:
        q = sql.format(p=prefixo, hoje=hoje)
        out.append(f"\n--- {nome}   [indice: {idx}]\n{q}\n" + "\n".join(plano(cur, q)))
        depois = tempo_ms(cur, q)
        out.append(f"Tempo medido ({EXECUCOES} execucoes): media {depois[0]:.3f} ms | minimo {depois[1]:.3f} ms")
        resumo.append((titulo, nome.split("  ")[0], antes[nome][0], depois[0]))
    return "\n".join(out), resumo


def main():
    textos, resumo = [], []
    for fn in [pg_run] + ([ora_run] if "oracle" in DBS else []):
        t, r = fn()
        textos.append(t)
        resumo += r
    tabela = ["", "=" * 78, "RESUMO (media em ms; quanto menor, melhor)", "=" * 78,
              f"{'Banco':<16}{'Consulta':<8}{'Antes (ms)':>14}{'Depois (ms)':>14}{'Ganho':>10}"]
    for banco, q, a, d in resumo:
        tabela.append(f"{banco:<16}{q:<8}{a:>14.3f}{d:>14.3f}{(a / d if d else 0):>9.1f}x")
    cab = f"Gerado por performance/perf.py em {datetime.now():%Y-%m-%d %H:%M:%S} (tempos reais desta maquina)\n"
    texto = cab + "\n\n".join(textos) + "\n" + "\n".join(tabela) + "\n"
    SAIDA.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"\nGravado em {SAIDA}")


if __name__ == "__main__":
    main()
