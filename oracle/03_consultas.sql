-- EquipaLoc - 10 consultas analiticas (Oracle).
-- Cada consulta comeca com o marcador '-- @Qnn' (usado pelos testes automatizados).
-- O resultado precisa ser IGUAL nos dois bancos (tests/test_consultas.py confere).

-- @Q01 Objetivo: Receita contratada por categoria (JOIN + agregacao) - quanto cada categoria rendeu nas locacoes ja devolvidas.
SELECT c.nome AS categoria,
       COUNT(*) AS qtd_itens,
       SUM(i.valor_diaria_cobrada * (l.data_prevista - l.data_saida)) AS receita
  FROM item_locacao i
  JOIN locacao l      ON l.locacao_id = i.locacao_id
  JOIN equipamento e  ON e.equipamento_id = i.equipamento_id
  JOIN categoria c    ON c.categoria_id = e.categoria_id
 WHERE l.status = 'DEVOLVIDA'
 GROUP BY c.nome
 ORDER BY receita DESC, c.nome;

-- @Q02 Objetivo: Locacoes abertas e a situacao de cada item (JOIN) - ATRASADA, VENCE HOJE ou NO PRAZO. Dado de fronteira: vence hoje.
SELECT l.locacao_id,
       cli.nome AS cliente,
       e.codigo AS equipamento,
       CASE WHEN l.data_prevista < TRUNC(SYSDATE) THEN 'ATRASADA'
            WHEN l.data_prevista = TRUNC(SYSDATE) THEN 'VENCE HOJE'
            ELSE 'NO PRAZO' END AS situacao
  FROM locacao l
  JOIN cliente cli    ON cli.cliente_id = l.cliente_id
  JOIN item_locacao i ON i.locacao_id = l.locacao_id
  JOIN equipamento e  ON e.equipamento_id = i.equipamento_id
 WHERE l.status = 'ABERTA'
 ORDER BY l.locacao_id, e.codigo;

-- @Q03 Objetivo: Clientes recorrentes (GROUP BY/HAVING) - 2 ou mais locacoes. Fronteira: clientes com exatamente 2.
SELECT cli.nome AS cliente, COUNT(*) AS qtd_locacoes
  FROM cliente cli
  JOIN locacao l ON l.cliente_id = cli.cliente_id
 GROUP BY cli.nome
HAVING COUNT(*) >= 2
 ORDER BY qtd_locacoes DESC, cli.nome;

-- @Q04 Objetivo: Ranking de equipamentos mais alugados (window RANK) - ha empate no 1o lugar e RANK pula posicoes.
SELECT codigo, qtd_locacoes,
       RANK() OVER (ORDER BY qtd_locacoes DESC) AS posicao
  FROM (SELECT e.codigo, COUNT(*) AS qtd_locacoes
          FROM item_locacao i
          JOIN equipamento e ON e.equipamento_id = i.equipamento_id
         GROUP BY e.codigo) t
 ORDER BY posicao, codigo;

-- @Q05 Objetivo: Receita acumulada por locacao em ordem cronologica (window SUM() OVER).
SELECT t.locacao_id,
       t.valor_contratado,
       SUM(t.valor_contratado) OVER (ORDER BY t.data_saida, t.locacao_id) AS acumulado
  FROM (SELECT l.locacao_id, l.data_saida,
               SUM(i.valor_diaria_cobrada * (l.data_prevista - l.data_saida)) AS valor_contratado
          FROM locacao l
          JOIN item_locacao i ON i.locacao_id = l.locacao_id
         GROUP BY l.locacao_id, l.data_saida) t
 ORDER BY t.data_saida, t.locacao_id;

-- @Q06 Objetivo: Ultimo equipamento alugado por cliente (window ROW_NUMBER particionado).
SELECT cliente, equipamento
  FROM (SELECT cli.nome AS cliente,
               e.codigo AS equipamento,
               ROW_NUMBER() OVER (PARTITION BY cli.cliente_id
                                  ORDER BY l.data_saida DESC, i.item_id DESC) AS rn
          FROM cliente cli
          JOIN locacao l      ON l.cliente_id = cli.cliente_id
          JOIN item_locacao i ON i.locacao_id = l.locacao_id
          JOIN equipamento e  ON e.equipamento_id = i.equipamento_id) t
 WHERE rn = 1
 ORDER BY cliente;

-- @Q07 Objetivo: Equipamentos NUNCA alugados (anti-join com NOT EXISTS).
SELECT e.codigo
  FROM equipamento e
 WHERE NOT EXISTS (SELECT 1 FROM item_locacao i WHERE i.equipamento_id = e.equipamento_id)
 ORDER BY e.codigo;

-- @Q08 Objetivo: Equipamentos com diaria acima da media da propria categoria (subconsulta correlacionada).
SELECT e.codigo, e.valor_diaria
  FROM equipamento e
 WHERE e.valor_diaria > (SELECT AVG(x.valor_diaria)
                           FROM equipamento x
                          WHERE x.categoria_id = e.categoria_id)
 ORDER BY e.codigo;

-- @Q09 Objetivo: Multas por tipo e status com subtotais e total geral (ROLLUP).
SELECT tipo, status, COUNT(*) AS qtd, SUM(valor) AS total
  FROM multa
 GROUP BY ROLLUP (tipo, status)
 ORDER BY tipo NULLS LAST, status NULLS LAST;

-- @Q10 Objetivo: Clientes que ja alugaram equipamento de TODAS as categorias (divisao relacional com NOT EXISTS duplo).
SELECT cli.nome AS cliente
  FROM cliente cli
 WHERE NOT EXISTS (
        SELECT 1 FROM categoria c
         WHERE NOT EXISTS (
                SELECT 1
                  FROM locacao l
                  JOIN item_locacao i ON i.locacao_id = l.locacao_id
                  JOIN equipamento e  ON e.equipamento_id = i.equipamento_id
                 WHERE l.cliente_id = cli.cliente_id
                   AND e.categoria_id = c.categoria_id))
 ORDER BY cli.nome;
