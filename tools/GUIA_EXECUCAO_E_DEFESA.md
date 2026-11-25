# Guia: primeira execução, defesa oral e entrega

## 1. Primeira execução (na ordem)

1. Instale o Docker Desktop. Escolha oficial: **PostgreSQL + Python** (leve). O Oracle (extra opcional) precisa de ~2 GB.
2. Na pasta do projeto: `docker compose up -d --wait` (a 1ª vez baixa a imagem do PostgreSQL; sobe em segundos).
3. Se algo falhar: `docker compose logs postgres` ou `docker compose logs oracle`. **Copie a mensagem de erro inteira**
   e leve ao Claude. Cada erro encontrado e corrigido é uma linha do registro de IA no README.
4. `docker compose run --rm testes` (todos devem passar).
5. `docker compose run --rm perf` (gera `performance/explain_antes_depois.txt`).
6. `docker compose --profile apps run --rm app-python`.
   Extras opcionais: `docker compose --profile oracle up -d --wait`, depois `docker compose --profile oracle run --rm testes-oracle` (84 testes nos dois bancos) e `docker compose --profile oracle run --rm app-java`.
7. Teste final do zero: `docker compose down -v` e repita 2 e 4. Para recriar também o Oracle: `docker compose --profile oracle down -v`.
   **Na véspera e no dia da apresentação, recrie tudo do zero:** os dados de exemplo têm datas relativas ao dia em que o banco foi criado, e um container antigo faz testes de data falharem.

**Onde é mais provável aparecer problema (por isso a revisão é obrigatória):** init do Oracle (`docker/oracle/init.sh`:
conexão do `sqlplus`, usuário `a3_perf`), sintaxe PL/SQL, versões de dependências do Python/Java no build,
`CALL` com parâmetro `INOUT` no PostgreSQL. Nada disso foi executado pelo agente.

## 2. Roteiro da defesa oral (o professor escolhe um trecho; eu explico)

| Artefato | O que saber explicar em 1 minuto |
|---|---|
| **DER** | Por que `item_locacao` existe (N:M com atributos), por que `multa` e `perfil_cliente` são tabelas, por que a auditoria não tem FK. |
| **DDL** | Convenção `pk_/uk_/fk_/ck_`; `ck_locacao_prazo` (RN-05); por que `CASCADE` só em item e `RESTRICT` no resto; no Oracle RESTRICT = omitir a cláusula. |
| **Consultas** | Q04: `RANK` pula posição no empate. Q07: `NOT EXISTS` (anti-join). Q09: `ROLLUP` gera subtotais. Q10: divisão relacional = "não existe categoria que ele não tenha alugado". |
| **`trg_item_locacao_valida`** | Roda **antes** de inserir em `item_locacao`; trava a linha do equipamento (`FOR UPDATE`), exige `DISPONIVEL` e marca `ALUGADO`. Vale para INSERT direto. Por que consulta `equipamento` e não `item_locacao` (tabela mutante no Oracle). |
| **`sp_registrar_locacao`** | Ordem das validações (prazo → cliente → multa → limite → equipamento); trava a linha do cliente para duas sessões não furarem o limite; não faz COMMIT. |
| **`sp_devolver_locacao`** | Fórmula: `10% × soma das diárias × dias de atraso`, teto `50% × soma × dias contratados`; avaria = 15% da reposição; atualiza 4 tabelas. |
| **Índices** | FK não é indexada sozinha; qual índice atende qual consulta; ler o plano (Seq Scan → Index Scan; `TABLE ACCESS FULL` → `INDEX RANGE SCAN`). |
| **Concorrência** | Sessão A segura o lock; B espera; A confirma; B vê `ALUGADO` e leva `EQL-005`. |
| **Apps** | Bind (`?`, `%s`, `:id`) evita SQL injection; `SAVEPOINT` porque no PostgreSQL o erro aborta a transação; `Decimal`/`BigDecimal` para dinheiro. |

## 4. Checkpoints do roteiro (Metodologia e Roteiro ao Longo do Curso)

Os checkpoints são com o **professor** e não valem nota própria (a nota é só a rubrica de 40 pts), mas o 1º é pedido
antes de se comprometerem com o tema. Como o projeto já está montado, dá para mostrar vários de uma vez:

| Checkpoint | O que mostrar | Pronto? |
|---|---|---|
| 1. Aprovação do tema (3 regras) | RN-01 a RN-06 do README (ex.: multa de 10% ao dia, limite de 3 itens, prazo de 15 dias) | **Falta perguntar ao professor** |
| 2. DER revisado | `der/equipaloc.puml` + diagrama do README | Pronto (gerar a imagem no plantuml.com) |
| 3. DDL rodando no PostgreSQL | `docker compose up -d --wait` | Depende da minha execução |
| 4. 5 consultas com resultado conferido | `docker compose run --rm testes -k consultas` | Depende da minha execução |
| 5. Procedures e trigger testados | `docker compose run --rm testes -k "procedures or triggers or concorrencia"` | Depende da minha execução |
| 6. Índices com tempos medidos | `docker compose run --rm perf` | Depende da minha execução |

### Revisão do DER com o checklist do enunciado (feita sobre o `.puml`)

- [x] 6+ entidades (são 8) com atributos, PK, UK e FK
- [x] Cardinalidades (mín., máx.) em todos os relacionamentos, notação Crow's Foot
- [x] N:M resolvido por entidade associativa com atributos próprios (`item_locacao`)
- [x] Decisões justificadas no README (PK artificial, entidades × atributos, normalização, `ON DELETE`)
- Ponto de atenção para a defesa: `auditoria_locacao` **não tem FK de propósito** (histórico sobrevive à exclusão da locação).

### Sobre `.agents/skills/`
O enunciado cita essa pasta para quem usa OpenCode com skills. Não usamos skills (declarado no README), então ela não existe.
Se eu passar a usar o OpenCode com alguma skill, crio a pasta e declaro a skill na seção "Uso de IA".

## 3. Entrega (checklist)

- [ ] README sem nenhum `⚠️ PREENCHER` (nome, tabela de performance, registro de IA com ≥ 2 erros reais, reflexões).
- [ ] `performance/explain_antes_depois.txt` gerado pelo `perf` (não escrito à mão).
- [ ] `docker compose down -v && docker compose up -d --wait && docker compose run --rm testes` passa numa cópia limpa.
- [ ] Commits em Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`), feitos em dias reais (trabalho individual aprovado pelo professor).
- [ ] Tag: `git tag v1.0.0` e hash do commit no README.
- [ ] Zip gerado **depois** da tag, com a pasta `.git`.

```bash
git init && git add . && git commit -m "feat: projeto EquipaLoc (A3)"
git tag v1.0.0
```

## 5. Entrega no Anima Hub (postar os 3 itens)

1. **Capa em PDF de 1 página:** nome do projeto, autor (nome e RA), link do repositório, tag e **hash do commit**.
2. **Zip do repositório COM a pasta `.git`** (o histórico é avaliado), sem `target`, `.venv` nem dados dos bancos.
3. **Link do repositório no GitHub** (público, ou o professor convidado como colaborador) no campo de texto.

Conferir antes de postar: zip descompactado em **outra pasta**, `docker compose down -v`, `up -d --wait` e `run --rm testes` passando; a tag aponta para o commit que está no zip; nenhuma senha real nem `.env`; todos os integrantes com commits (Conventional Commits). Mudanças depois do prazo não valem: **vale o commit da tag**.

## 6. Apresentação de 10 minutos (individual)

| Parte | Tempo | O que mostrar |
|---|---|---|
| O problema e o DER | 2 min | Domínio, regras com número, DER e **uma** decisão de modelagem justificada |
| Do zero ao banco pronto | 2 min | `docker compose up -d --wait` e `run --rm testes` no PostgreSQL |
| Uma regra de negócio ao vivo | 3 min | `tools/demo_postgresql.sql`: caminho feliz, erro e o que o trigger registrou; depois a mesma regra **pela aplicação** (`docker compose --profile apps run --rm app-python`). O `demo_oracle.sql` é do extra opcional |
| Índice e plano | 1 min | Plano antes e depois, com o tempo |
| Lições e IA | 2 min | O que o agente errou, o que eu corrigi e **por que escolhi PostgreSQL e Python** (sobe em segundos, usa pouca memória; Python tem driver psycopg, bind, `CALL` de procedure, transação e roda pelo compose) |
| Pergunta do professor | — | Explicar um trecho escolhido |

**Preparação:** bancos já iniciados (o Oracle demora), comandos já ensaiados, portas 5432 e 1521 livres e **uma gravação de tela de reserva** (Win+G abre a barra de jogos do Windows, que grava). Rodem os dois `demo_*.sql` antes: eles **não foram executados pelo agente**.

```
Get-Content tools\demo_postgresql.sql | docker compose exec -T postgres psql -U a3 -d a3
Get-Content tools\demo_oracle.sql | docker compose exec -T oracle sqlplus -s a3/a3lab@//localhost:1521/XEPDB1
```

## 7. Clientes SQL (opcional)
`psql` e `sqlplus` já vêm dentro dos containers (comandos acima), então não precisa instalar nada.
Para **ver as tabelas e tirar prints**, o enunciado recomenda o **DBeaver** (um só programa para os dois bancos). O programa do elefante é o pgAdmin, que serve só para PostgreSQL.
Conexões: PostgreSQL `localhost:5432`, banco `a3`, usuário `a3`, senha `a3lab`. Oracle `localhost:1521`, serviço `XEPDB1`, usuário `a3`, senha `a3lab`.

## 8. Pontos do enunciado atualizado (24/11)

- **O que estiver no repositório também é avaliado**, inclusive na pergunta do professor. Isso vale para o Oracle e o Java extras: se ficarem, é preciso saber explicar também esses arquivos.
- **Commits ao longo das semanas**, em Conventional Commits. Faça commits pequenos e reais nos próximos dias (prints, mutação, README), sem alterar datas.
- **Informar o SGBD e a linguagem ao professor** (PostgreSQL e Python). Se o e-mail com essa informação ainda não foi enviado, envie.
- **A imagem do DER precisa estar no README** (já está na seção 2).
- **Demonstração ao vivo "também pela aplicação":** rodar a regra pelo `app-python`, além do SQL.
- **Cópia limpa:** `docker compose down -v` antes de testar o zip descompactado em outra pasta.
