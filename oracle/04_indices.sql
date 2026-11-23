-- =====================================================================
-- EquipaLoc - indices (Oracle). Nem o PostgreSQL nem o Oracle indexam FK sozinhos.
-- A UK uk_item_loc_equip (locacao_id, equipamento_id) ja cobre a FK item_locacao.locacao_id.
-- Cada indice abaixo e medido antes/depois em performance/ (docker compose run --rm perf).
-- =====================================================================

-- 1) FK usada em JOIN: historico de locacoes por cliente
CREATE INDEX idx_locacao_cliente ON locacao (cliente_id);

-- 2) FK usada em JOIN: em quais locacoes um equipamento aparece (consultas Q01, Q04, Q07)
CREATE INDEX idx_item_equipamento ON item_locacao (equipamento_id);

-- 3) Indice de BUSCA: locacoes abertas e vencidas (status + data_prevista)
CREATE INDEX idx_locacao_status_prevista ON locacao (status, data_prevista);
