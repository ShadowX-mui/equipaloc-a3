# AGENTS.md - memoria do projeto para o agente de IA

## Projeto
A3 de Banco de Dados: **EquipaLoc** (aluguel de ferramentas e equipamentos).
**SGBD escolhido: PostgreSQL 17. Linguagem da aplicacao: Python 3.12.** Use sempre o dialeto PostgreSQL
(`VARCHAR`, `NUMERIC`, `IDENTITY`, PL/pgSQL) e NAO misture dialetos.
Oracle XE 21 e a aplicacao Java sao **extras opcionais** (profile `oracle` do compose), fora do caminho principal.
Tudo sobe com `docker compose up -d --wait`.

## Comandos
- `docker compose up -d --wait` -> sobe o PostgreSQL ja carregado
- `docker compose run --rm testes` -> testes automatizados no PostgreSQL
- `docker compose run --rm perf` -> EXPLAIN antes/depois (gera performance/explain_antes_depois.txt)
- `docker compose --profile apps run --rm app-python`
- Extras: `docker compose --profile oracle up -d --wait`, `... run --rm testes-oracle`, `... run --rm app-java`
- `docker compose down -v` -> derruba e apaga tudo

## Estrutura
`der/` DER PlantUML | `postgresql/` e `oracle/` (01_ddl, 02_inserts, 03_consultas, 04_indices) |
`procedures/` PL/pgSQL e PL/SQL | `performance/` | `tests/` pytest | `python/` | `java/` (JDBC: `LocacaoDao` = base, uma subclasse por dialeto) | `docker/`
`tools/gen_seed.py` gera os dois 02_inserts.sql a partir de uma unica definicao.

## Regras de negocio (RN) - implementadas DENTRO do banco
RN-01 multa de 10% da soma das diarias por dia de atraso, teto 50% do valor contratado |
RN-02 limite de itens abertos por perfil (PADRAO 3, PREMIUM 6) | RN-03 cliente com multa aberta nao aluga |
RN-04 equipamento so em UMA locacao aberta (trigger, vale para INSERT direto) | RN-05 prazo de 1 a 15 dias |
RN-06 avaria cobra 15% do valor de reposicao. Erros de negocio: codigos `EQL-001` a `EQL-009`.

## Convencoes
- Constraints nomeadas: `pk_`, `uk_`, `fk_`, `ck_`. `ON DELETE` explicito (no Oracle, RESTRICT = omitir a clausula).
- Procedures **nao fazem COMMIT**; erro de negocio via `RAISE EXCEPTION` (PG) e `RAISE_APPLICATION_ERROR(-2000n)` (Oracle).
- SQL em ASCII (sem acentos em literais) para evitar problemas de charset no sqlplus.
- Dados de exemplo com datas relativas a hoje; nenhum dado pessoal real.

## Regras para o agente
1. Todo SQL escrito pelo agente so vale depois de **executado nos dois bancos** pelo grupo.
2. Nunca `DROP`, `TRUNCATE` ou `DELETE/UPDATE` sem `WHERE` por sugestao do agente, e nunca contra banco fora do laboratorio.
3. Nunca inventar tempos ou planos de execucao: colar a saida real.
4. `git push` e senhas/chaves de API ficam fora do agente e fora do Git. As senhas do compose sao de laboratorio.
5. Mantenha este arquivo coerente com o repositorio sempre que a estrutura mudar.
