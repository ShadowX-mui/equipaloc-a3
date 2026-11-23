#!/bin/bash
# Carga inicial do Oracle XE (roda dentro do container, depois que o banco e o usuario a3 existem).
# Qualquer erro ABORTA a subida: WHENEVER SQLERROR EXIT + "|| exit 1".
export NLS_LANG=AMERICAN_AMERICA.AL32UTF8
APP="a3/a3lab@//localhost:1521/XEPDB1"

# Usuario separado para a massa de dados de performance (esquema a parte)
sqlplus -s -L / as sysdba <<'SQL' || { echo "FALHA ao criar a3_perf"; exit 1; }
WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SESSION SET CONTAINER = XEPDB1;
CREATE USER a3_perf IDENTIFIED BY a3perf;
GRANT CREATE SESSION, CREATE TABLE, UNLIMITED TABLESPACE TO a3_perf;
EXIT
SQL

run_sql() {
    echo ">> executando $1"
    sqlplus -s -L "$APP" <<SQL || { echo "FALHA em $1"; exit 1; }
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET DEFINE OFF
SET SQLBLANKLINES ON
SET SERVEROUTPUT ON
@$1
EXIT
SQL
}

run_sql /sql/oracle/01_ddl.sql
run_sql /sql/oracle/02_inserts.sql
run_sql /sql/procedures/oracle_procedures.sql

# CREATE PROCEDURE/TRIGGER com erro de compilacao NAO dispara WHENEVER SQLERROR:
# conferimos USER_ERRORS e abortamos se houver qualquer objeto invalido.
sqlplus -s -L "$APP" <<'SQL' || { echo "FALHA: objetos PL/SQL com erro de compilacao"; exit 1; }
WHENEVER SQLERROR EXIT SQL.SQLCODE
DECLARE
    n NUMBER;
BEGIN
    SELECT COUNT(*) INTO n FROM user_errors;
    IF n > 0 THEN
        RAISE_APPLICATION_ERROR(-20999, 'Objetos PL/SQL com erro de compilacao (ver USER_ERRORS)');
    END IF;
END;
/
EXIT
SQL

run_sql /sql/oracle/04_indices.sql

touch /tmp/a3_init_ok
echo ">> Oracle pronto (esquema, dados, procedures e indices)"
