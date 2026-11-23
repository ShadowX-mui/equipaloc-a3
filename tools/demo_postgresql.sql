-- Demo ao vivo (PostgreSQL). Rodar:  Get-Content tools\demo_postgresql.sql | docker compose exec -T postgres psql -U a3 -d a3
-- Tudo dentro de uma transacao e termina em ROLLBACK: nao altera os dados de exemplo.
\echo '--- 1) caminho feliz: Elisa (cliente 5) aluga o compressor (equipamento 12) por 3 dias'
BEGIN;
CALL sp_registrar_locacao(5, 12, 3, NULL);
\echo '--- 2) o que o trigger de auditoria registrou'
SELECT auditoria_id, locacao_id, operacao, status_anterior, status_novo, usuario FROM auditoria_locacao ORDER BY auditoria_id;
\echo '--- 3) equipamento 12 agora esta ALUGADO'
SELECT codigo, status FROM equipamento WHERE equipamento_id = 12;
ROLLBACK;

\echo '--- 4) erro de negocio: Diego (cliente 4) tem multa em aberto -> EQL-003'
BEGIN;
CALL sp_registrar_locacao(4, 12, 3, NULL);
ROLLBACK;

\echo '--- 5) INSERT direto em equipamento ja alugado: o trigger barra -> EQL-005'
BEGIN;
INSERT INTO item_locacao (locacao_id, equipamento_id, valor_diaria_cobrada) VALUES (9, 1, 25);
ROLLBACK;
