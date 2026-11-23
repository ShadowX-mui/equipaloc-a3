#!/bin/bash
# Carga inicial do PostgreSQL. Qualquer erro ABORTA a subida (ON_ERROR_STOP + exit 1).
for f in /sql/postgresql/01_ddl.sql \
         /sql/postgresql/02_inserts.sql \
         /sql/procedures/postgresql_procedures.sql \
         /sql/postgresql/04_indices.sql; do
    echo ">> executando $f"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$f" || { echo "FALHA em $f"; exit 1; }
done
echo ">> PostgreSQL pronto (esquema, dados, procedures e indices)"
