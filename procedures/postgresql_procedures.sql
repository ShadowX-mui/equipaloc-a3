-- =====================================================================
-- EquipaLoc - Procedures e triggers (PL/pgSQL, PostgreSQL 17)
-- Codigos de erro de negocio (mensagem sempre comeca com o codigo):
--   EQL-001 prazo invalido (RN-05)        EQL-006 locacao inexistente
--   EQL-002 cliente inexistente           EQL-007 locacao ja devolvida
--   EQL-003 cliente com multa (RN-03)     EQL-008 equipamento nao pertence a locacao
--   EQL-004 limite do perfil (RN-02)      EQL-009 devolucao anterior a saida
--   EQL-005 equipamento indisponivel (RN-04)
-- Nenhuma procedure faz COMMIT: quem chama decide a transacao.
-- =====================================================================

-- ---------------------------------------------------------------------
-- TRIGGER 1 (validacao) - RN-04: um equipamento so pode estar em UMA locacao aberta.
-- Vale mesmo para INSERT direto em item_locacao. Trava a linha do equipamento
-- (FOR UPDATE) para duas sessoes concorrentes nao alugarem o mesmo item.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_item_locacao_valida() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_status equipamento.status%TYPE;
BEGIN
    SELECT status INTO v_status
      FROM equipamento
     WHERE equipamento_id = NEW.equipamento_id
       FOR UPDATE;

    IF NOT FOUND OR v_status <> 'DISPONIVEL' THEN
        RAISE EXCEPTION 'EQL-005: Equipamento % indisponivel (status atual: %)',
            NEW.equipamento_id, COALESCE(v_status, 'INEXISTENTE');
    END IF;

    UPDATE equipamento SET status = 'ALUGADO' WHERE equipamento_id = NEW.equipamento_id;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_item_locacao_valida
    BEFORE INSERT ON item_locacao
    FOR EACH ROW EXECUTE FUNCTION fn_item_locacao_valida();

-- ---------------------------------------------------------------------
-- TRIGGER 2 (auditoria) - registra criacao e mudanca de status da locacao.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_locacao_auditoria() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO auditoria_locacao (locacao_id, operacao, status_anterior, status_novo, usuario)
        VALUES (NEW.locacao_id, 'INSERT', NULL, NEW.status, current_user);
    ELSIF OLD.status <> NEW.status THEN
        INSERT INTO auditoria_locacao (locacao_id, operacao, status_anterior, status_novo, usuario)
        VALUES (NEW.locacao_id, 'UPDATE', OLD.status, NEW.status, current_user);
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_locacao_auditoria
    AFTER INSERT OR UPDATE OF status ON locacao
    FOR EACH ROW EXECUTE FUNCTION fn_locacao_auditoria();

-- ---------------------------------------------------------------------
-- PROCEDURE 1 - sp_registrar_locacao
-- Regras: RN-05 (1 a 15 dias), RN-03 (sem multa aberta), RN-02 (limite do perfil),
--         RN-04 (disponibilidade, garantida pelo trigger).
-- Altera: locacao, item_locacao e equipamento (via trigger).
-- Concorrencia: trava a linha do cliente, serializando o calculo do limite.
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_registrar_locacao(
    p_cliente_id     INTEGER,
    p_equipamento_id INTEGER,
    p_dias           INTEGER,
    INOUT p_locacao_id INTEGER)
LANGUAGE plpgsql AS $$
DECLARE
    v_max     INTEGER;
    v_multas  INTEGER;
    v_abertos INTEGER;
    v_diaria  NUMERIC(10,2);
BEGIN
    IF p_dias IS NULL OR p_dias < 1 OR p_dias > 15 THEN
        RAISE EXCEPTION 'EQL-001: Prazo invalido (%): informe de 1 a 15 dias', p_dias;
    END IF;

    SELECT p.max_itens_abertos INTO v_max
      FROM cliente c
      JOIN perfil_cliente p ON p.perfil_id = c.perfil_id
     WHERE c.cliente_id = p_cliente_id
       FOR UPDATE OF c;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'EQL-002: Cliente % nao existe', p_cliente_id;
    END IF;

    SELECT COUNT(*) INTO v_multas
      FROM multa m
      JOIN locacao l ON l.locacao_id = m.locacao_id
     WHERE l.cliente_id = p_cliente_id AND m.status = 'ABERTA';
    IF v_multas > 0 THEN
        RAISE EXCEPTION 'EQL-003: Cliente % possui multa em aberto', p_cliente_id;
    END IF;

    SELECT COUNT(*) INTO v_abertos
      FROM item_locacao i
      JOIN locacao l ON l.locacao_id = i.locacao_id
     WHERE l.cliente_id = p_cliente_id AND l.status = 'ABERTA';
    IF v_abertos >= v_max THEN
        RAISE EXCEPTION 'EQL-004: Limite de % itens em aberto atingido para o perfil do cliente %',
            v_max, p_cliente_id;
    END IF;

    SELECT valor_diaria INTO v_diaria FROM equipamento WHERE equipamento_id = p_equipamento_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'EQL-005: Equipamento % indisponivel (status atual: INEXISTENTE)', p_equipamento_id;
    END IF;

    INSERT INTO locacao (cliente_id, data_saida, data_prevista, status)
    VALUES (p_cliente_id, CURRENT_DATE, CURRENT_DATE + p_dias, 'ABERTA')
    RETURNING locacao_id INTO p_locacao_id;

    INSERT INTO item_locacao (locacao_id, equipamento_id, valor_diaria_cobrada)
    VALUES (p_locacao_id, p_equipamento_id, v_diaria);
END;
$$;

-- ---------------------------------------------------------------------
-- PROCEDURE 2 - sp_devolver_locacao
-- Regras: RN-01 (multa 10% da soma das diarias por dia de atraso, teto de 50% do
--         valor contratado) e RN-06 (avaria = 15% do valor de reposicao).
-- Altera: multa, item_locacao, equipamento e locacao.
-- p_data_devolucao NULL = hoje. p_equipamento_avaria_id NULL = sem avaria.
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_devolver_locacao(
    p_locacao_id           INTEGER,
    p_data_devolucao       DATE,
    p_equipamento_avaria_id INTEGER)
LANGUAGE plpgsql AS $$
DECLARE
    v_status      locacao.status%TYPE;
    v_saida       DATE;
    v_prevista    DATE;
    v_dev         DATE;
    v_soma        NUMERIC(12,2);
    v_dias_contr  INTEGER;
    v_dias_atraso INTEGER;
    v_multa       NUMERIC(12,2);
    v_teto        NUMERIC(12,2);
    v_repo        NUMERIC(10,2);
BEGIN
    SELECT status, data_saida, data_prevista
      INTO v_status, v_saida, v_prevista
      FROM locacao
     WHERE locacao_id = p_locacao_id
       FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'EQL-006: Locacao % nao existe', p_locacao_id;
    END IF;
    IF v_status <> 'ABERTA' THEN
        RAISE EXCEPTION 'EQL-007: Locacao % ja foi devolvida', p_locacao_id;
    END IF;

    v_dev := COALESCE(p_data_devolucao, CURRENT_DATE);
    IF v_dev < v_saida THEN
        RAISE EXCEPTION 'EQL-009: Data de devolucao anterior a data de saida';
    END IF;

    IF p_equipamento_avaria_id IS NOT NULL THEN
        SELECT e.valor_reposicao INTO v_repo
          FROM item_locacao i
          JOIN equipamento e ON e.equipamento_id = i.equipamento_id
         WHERE i.locacao_id = p_locacao_id AND i.equipamento_id = p_equipamento_avaria_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'EQL-008: Equipamento % nao pertence a locacao %',
                p_equipamento_avaria_id, p_locacao_id;
        END IF;
    END IF;

    SELECT SUM(valor_diaria_cobrada) INTO v_soma FROM item_locacao WHERE locacao_id = p_locacao_id;
    v_dias_contr  := v_prevista - v_saida;
    v_dias_atraso := GREATEST(v_dev - v_prevista, 0);

    IF v_dias_atraso > 0 THEN
        v_multa := ROUND(0.10 * v_soma * v_dias_atraso, 2);
        v_teto  := ROUND(0.50 * v_soma * v_dias_contr, 2);
        IF v_multa > v_teto THEN v_multa := v_teto; END IF;
        INSERT INTO multa (locacao_id, tipo, valor, status, data_geracao)
        VALUES (p_locacao_id, 'ATRASO', v_multa, 'ABERTA', v_dev);
    END IF;

    IF p_equipamento_avaria_id IS NOT NULL THEN
        UPDATE item_locacao SET avaria = 'S'
         WHERE locacao_id = p_locacao_id AND equipamento_id = p_equipamento_avaria_id;
        INSERT INTO multa (locacao_id, tipo, valor, status, data_geracao)
        VALUES (p_locacao_id, 'AVARIA', ROUND(0.15 * v_repo, 2), 'ABERTA', v_dev);
    END IF;

    UPDATE equipamento
       SET status = CASE WHEN equipamento_id = p_equipamento_avaria_id
                         THEN 'MANUTENCAO' ELSE 'DISPONIVEL' END
     WHERE equipamento_id IN (SELECT equipamento_id FROM item_locacao WHERE locacao_id = p_locacao_id);

    UPDATE locacao SET status = 'DEVOLVIDA', data_devolucao = v_dev
     WHERE locacao_id = p_locacao_id;
END;
$$;
