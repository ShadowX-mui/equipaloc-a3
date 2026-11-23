"""Gera 02_inserts.sql para PostgreSQL e Oracle a partir de UMA definicao.
Assim os dois bancos recebem exatamente os mesmos dados.
Datas sao relativas a hoje (D-n) para as consultas darem o mesmo resultado em qualquer dia.
Sem acentos nos textos (evita problemas de charset no sqlplus). Nenhum dado pessoal real.
Os IDs nao sao informados: a IDENTITY gera 1..n na ordem dos INSERTs (por isso um INSERT por linha).
"""
PERFIS = [("PADRAO", 3), ("PREMIUM", 6)]
CATEGORIAS = ["ELETRICA", "CONSTRUCAO", "LIMPEZA", "JARDIM"]           # ids 1..4
CLIENTES = [  # (perfil_id, nome, email)
    (1, "Ana Teste", "ana@exemplo.test"), (1, "Bruno Exemplo", "bruno@exemplo.test"),
    (2, "Carla Modelo", "carla@exemplo.test"), (1, "Diego Ficticio", "diego@exemplo.test"),
    (1, "Elisa Demo", "elisa@exemplo.test"), (2, "Fabio Amostra", "fabio@exemplo.test"),
    (1, "Gabi Simulada", "gabi@exemplo.test"), (1, "Hugo Lab", "hugo@exemplo.test"),
]
EQUIPS = [  # (categoria_id, codigo, descricao, diaria, reposicao, status)  ids 1..12
    (1, "FUR-001", "Furadeira de impacto 600W", 25, 350, "ALUGADO"),
    (1, "FUR-002", "Furadeira de bancada", 40, 900, "DISPONIVEL"),
    (1, "SER-001", "Serra circular", 35, 600, "ALUGADO"),
    (2, "BET-001", "Betoneira 150L", 60, 2500, "ALUGADO"),
    (2, "AND-001", "Andaime modular", 45, 1800, "ALUGADO"),
    (2, "ESC-001", "Escada extensiva", 20, 400, "ALUGADO"),
    (3, "LAV-001", "Lavadora de alta pressao", 50, 1200, "ALUGADO"),
    (3, "ASP-001", "Aspirador industrial", 30, 700, "DISPONIVEL"),
    (4, "ROC-001", "Rocadeira", 40, 1000, "MANUTENCAO"),
    (4, "MOT-001", "Motosserra", 55, 1500, "DISPONIVEL"),
    (4, "COR-001", "Cortador de grama", 35, 800, "DISPONIVEL"),
    (1, "COMP-001", "Compressor de ar", 45, 1100, "DISPONIVEL"),
]
# (cliente, saida, prevista, devolucao|None, itens[equipamento ids], avaria_eq|None)   offsets = dias antes (+) / depois (-) de hoje
# Convencao: valores sao "D-n" => n positivo = n dias atras; negativo = no futuro.
LOCACOES = [
    (1, 30, 25, 25, [1], None),            # L1  devolvida no prazo
    (1, 28, 23, 20, [4], None),            # L2  3 dias de atraso
    (2, 24, 19, 19, [7, 8], None),         # L3  2 itens (N:M)
    (3, 22, 17, 17, [5, 6, 3], None),      # L4  3 itens
    (4, 20, 15, 10, [9], 9),               # L5  5 dias de atraso + avaria
    (5, 16, 11, 11, [10, 11], None),       # L6
    (2, 14, 9, 9, [2], None),              # L7
    (6, 10, 5, 4, [3, 1, 11, 8], None),    # L8  1 dia de atraso, 4 itens
    (1, 3, -2, None, [6], None),           # L9  aberta, no prazo (vence D+2)
    (3, 6, 1, None, [4], None),            # L10 aberta, ATRASADA (venceu ontem)
    (7, 5, 0, None, [7], None),            # L11 aberta, VENCE HOJE (fronteira)
    (2, 2, -3, None, [1, 3], None),        # L12 aberta, 2 itens
    (6, 1, -4, None, [5], None),           # L13 aberta
]
MULTAS = [  # (locacao_id, tipo, valor, status, geracao_offset)
    (2, "ATRASO", "18.00", "PAGA", 20), (5, "ATRASO", "20.00", "ABERTA", 10),
    (5, "AVARIA", "150.00", "ABERTA", 10), (8, "ATRASO", "12.50", "PAGA", 4),
]

def d(db, n):
    base = "CURRENT_DATE" if db == "pg" else "TRUNC(SYSDATE)"
    return base if n == 0 else f"{base} - {n}" if n > 0 else f"{base} + {-n}"

def gen(db):
    o = [f"-- EquipaLoc - dados de exemplo ({'PostgreSQL' if db=='pg' else 'Oracle'}). GERADO por tools/gen_seed.py",
         "-- Datas relativas a hoje. IDs gerados pela IDENTITY na ordem dos INSERTs (1..n).", ""]
    for nome, mx in PERFIS:
        o.append(f"INSERT INTO perfil_cliente (nome, max_itens_abertos) VALUES ('{nome}', {mx});")
    for n in CATEGORIAS:
        o.append(f"INSERT INTO categoria (nome) VALUES ('{n}');")
    for p, n, e in CLIENTES:
        o.append(f"INSERT INTO cliente (perfil_id, nome, email) VALUES ({p}, '{n}', '{e}');")
    for c, cod, desc, di, rp, st in EQUIPS:
        o.append(f"INSERT INTO equipamento (categoria_id, codigo, descricao, valor_diaria, valor_reposicao, status) "
                 f"VALUES ({c}, '{cod}', '{desc}', {di}.00, {rp}.00, '{st}');")
    for i, (cli, s, p, dv, itens, av) in enumerate(LOCACOES, 1):
        st = "ABERTA" if dv is None else "DEVOLVIDA"
        dvs = "NULL" if dv is None else d(db, dv)
        o.append(f"INSERT INTO locacao (cliente_id, data_saida, data_prevista, data_devolucao, status) "
                 f"VALUES ({cli}, {d(db,s)}, {d(db,p)}, {dvs}, '{st}');")
        for eq in itens:
            diaria = EQUIPS[eq-1][3]
            flag = "S" if av == eq else "N"
            o.append(f"INSERT INTO item_locacao (locacao_id, equipamento_id, valor_diaria_cobrada, avaria) "
                     f"VALUES ({i}, {eq}, {diaria}.00, '{flag}');")
    for loc, tp, v, st, off in MULTAS:
        o.append(f"INSERT INTO multa (locacao_id, tipo, valor, status, data_geracao) "
                 f"VALUES ({loc}, '{tp}', {v}, '{st}', {d(db,off)});")
    if db == "ora":
        o.append("COMMIT;")
    return "\n".join(o) + "\n"

open("postgresql/02_inserts.sql", "w").write(gen("pg"))
open("oracle/02_inserts.sql", "w").write(gen("ora"))
print("ok")
