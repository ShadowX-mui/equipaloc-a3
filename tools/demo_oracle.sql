-- Demo ao vivo (Oracle). Rodar:  Get-Content tools\demo_oracle.sql | docker compose exec -T oracle sqlplus -s a3/a3lab@//localhost:1521/XEPDB1
-- Termina em ROLLBACK: nao altera os dados de exemplo.
SET SERVEROUTPUT ON
SET LINESIZE 200
COLUMN usuario FORMAT A8
PROMPT --- 1) caminho feliz: Elisa (cliente 5) aluga o compressor (equipamento 12) por 3 dias
VARIABLE id NUMBER
EXEC sp_registrar_locacao(5, 12, 3, :id)
PRINT id
PROMPT --- 2) o que o trigger de auditoria registrou
SELECT auditoria_id, locacao_id, operacao, status_anterior, status_novo, usuario FROM auditoria_locacao ORDER BY auditoria_id;
PROMPT --- 3) equipamento 12 agora esta ALUGADO
SELECT codigo, status FROM equipamento WHERE equipamento_id = 12;
ROLLBACK;

PROMPT --- 4) erro de negocio: Diego (cliente 4) tem multa em aberto -> EQL-003
EXEC sp_registrar_locacao(4, 12, 3, :id)
ROLLBACK;

PROMPT --- 5) INSERT direto em equipamento ja alugado: o trigger barra -> EQL-005
INSERT INTO item_locacao (locacao_id, equipamento_id, valor_diaria_cobrada) VALUES (9, 1, 25);
ROLLBACK;
EXIT
