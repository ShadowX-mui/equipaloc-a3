-- =====================================================================
-- EquipaLoc - Procedures e triggers (PL/SQL, Oracle XE 21)
-- Codigos de erro de negocio: RAISE_APPLICATION_ERROR(-2000n, 'EQL-00n: ...')
--   -20001 EQL-001 prazo invalido (RN-05)     -20006 EQL-006 locacao inexistente
--   -20002 EQL-002 cliente inexistente        -20007 EQL-007 locacao ja devolvida
--   -20003 EQL-003 multa em aberto (RN-03)    -20008 EQL-008 equip. nao pertence a locacao
--   -20004 EQL-004 limite do perfil (RN-02)   -20009 EQL-009 devolucao anterior a saida
--   -20005 EQL-005 equipamento indisponivel (RN-04)
-- Nenhuma procedure faz COMMIT: quem chama decide a transacao.
-- =====================================================================

-- TRIGGER 1 (validacao) - RN-04: um equipamento so pode estar em UMA locacao aberta.
-- Vale para INSERT direto. Trava a linha do equipamento (FOR UPDATE) contra concorrencia.
-- Consulta so a tabela equipamento (nao a item_locacao), evitando ORA-04091 (tabela mutante).
CREATE OR REPLACE TRIGGER trg_item_locacao_valida
BEFORE INSERT ON item_locacao
FOR EACH ROW
DECLARE
    v_status equipamento.status%TYPE;
BEGIN
    BEGIN
        SELECT status INTO v_status
          FROM equipamento
         WHERE equipamento_id = :NEW.equipamento_id
           FOR UPDATE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            v_status := NULL;
    END;

    IF v_status IS NULL OR v_status <> 'DISPONIVEL' THEN
        RAISE_APPLICATION_ERROR(-20005, 'EQL-005: Equipamento ' || :NEW.equipamento_id ||
            ' indisponivel (status atual: ' || NVL(v_status, 'INEXISTENTE') || ')');
    END IF;

    UPDATE equipamento SET status = 'ALUGADO' WHERE equipamento_id = :NEW.equipamento_id;
END;
/

-- TRIGGER 2 (auditoria) - registra criacao e mudanca de status da locacao.
CREATE OR REPLACE TRIGGER trg_locacao_auditoria
AFTER INSERT OR UPDATE OF status ON locacao
FOR EACH ROW
BEGIN
    IF INSERTING THEN
        INSERT INTO auditoria_locacao (locacao_id, operacao, status_anterior, status_novo, usuario)
        VALUES (:NEW.locacao_id, 'INSERT', NULL, :NEW.status, USER);
    ELSIF :OLD.status <> :NEW.status THEN
        INSERT INTO auditoria_locacao (locacao_id, operacao, status_anterior, status_novo, usuario)
        VALUES (:NEW.locacao_id, 'UPDATE', :OLD.status, :NEW.status, USER);
    END IF;
END;
/

-- PROCEDURE 1 - sp_registrar_locacao
-- Regras: RN-05 (1 a 15 dias), RN-03 (sem multa aberta), RN-02 (limite do perfil),
--         RN-04 (disponibilidade, garantida pelo trigger).
-- Altera: locacao, item_locacao e equipamento (via trigger).
-- Concorrencia: trava a linha do cliente, serializando o calculo do limite.
CREATE OR REPLACE PROCEDURE sp_registrar_locacao(
    p_cliente_id     IN  NUMBER,
    p_equipamento_id IN  NUMBER,
    p_dias           IN  NUMBER,
    p_locacao_id     OUT NUMBER)
AS
    v_max     NUMBER;
    v_multas  NUMBER;
    v_abertos NUMBER;
    v_diaria  NUMBER;
BEGIN
    IF p_dias IS NULL OR p_dias < 1 OR p_dias > 15 THEN
        RAISE_APPLICATION_ERROR(-20001, 'EQL-001: Prazo invalido (' || p_dias || '): informe de 1 a 15 dias');
    END IF;

    BEGIN
        SELECT p.max_itens_abertos INTO v_max
          FROM cliente c
          JOIN perfil_cliente p ON p.perfil_id = c.perfil_id
         WHERE c.cliente_id = p_cliente_id
           FOR UPDATE OF c.cliente_id;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE_APPLICATION_ERROR(-20002, 'EQL-002: Cliente ' || p_cliente_id || ' nao existe');
    END;

    SELECT COUNT(*) INTO v_multas
      FROM multa m
      JOIN locacao l ON l.locacao_id = m.locacao_id
     WHERE l.cliente_id = p_cliente_id AND m.status = 'ABERTA';
    IF v_multas > 0 THEN
        RAISE_APPLICATION_ERROR(-20003, 'EQL-003: Cliente ' || p_cliente_id || ' possui multa em aberto');
    END IF;

    SELECT COUNT(*) INTO v_abertos
      FROM item_locacao i
      JOIN locacao l ON l.locacao_id = i.locacao_id
     WHERE l.cliente_id = p_cliente_id AND l.status = 'ABERTA';
    IF v_abertos >= v_max THEN
        RAISE_APPLICATION_ERROR(-20004, 'EQL-004: Limite de ' || v_max ||
            ' itens em aberto atingido para o perfil do cliente ' || p_cliente_id);
    END IF;

    BEGIN
        SELECT valor_diaria INTO v_diaria FROM equipamento WHERE equipamento_id = p_equipamento_id;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE_APPLICATION_ERROR(-20005, 'EQL-005: Equipamento ' || p_equipamento_id ||
                ' indisponivel (status atual: INEXISTENTE)');
    END;

    INSERT INTO locacao (cliente_id, data_saida, data_prevista, status)
    VALUES (p_cliente_id, TRUNC(SYSDATE), TRUNC(SYSDATE) + p_dias, 'ABERTA')
    RETURNING locacao_id INTO p_locacao_id;

    INSERT INTO item_locacao (locacao_id, equipamento_id, valor_diaria_cobrada)
    VALUES (p_locacao_id, p_equipamento_id, v_diaria);
END sp_registrar_locacao;
/

-- PROCEDURE 2 - sp_devolver_locacao
-- Regras: RN-01 (multa 10% da soma das diarias por dia de atraso, teto de 50% do
--         valor contratado) e RN-06 (avaria = 15% do valor de reposicao).
-- Altera: multa, item_locacao, equipamento e locacao.
-- p_data_devolucao NULL = hoje. p_equipamento_avaria_id NULL = sem avaria.
CREATE OR REPLACE PROCEDURE sp_devolver_locacao(
    p_locacao_id            IN NUMBER,
    p_data_devolucao        IN DATE,
    p_equipamento_avaria_id IN NUMBER)
AS
    v_status      locacao.status%TYPE;
    v_saida       DATE;
    v_prevista    DATE;
    v_dev         DATE;
    v_soma        NUMBER;
    v_dias_contr  NUMBER;
    v_dias_atraso NUMBER;
    v_multa       NUMBER;
    v_teto        NUMBER;
    v_repo        NUMBER;
BEGIN
    BEGIN
        SELECT status, data_saida, data_prevista
          INTO v_status, v_saida, v_prevista
          FROM locacao
         WHERE locacao_id = p_locacao_id
           FOR UPDATE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE_APPLICATION_ERROR(-20006, 'EQL-006: Locacao ' || p_locacao_id || ' nao existe');
    END;
    IF v_status <> 'ABERTA' THEN
        RAISE_APPLICATION_ERROR(-20007, 'EQL-007: Locacao ' || p_locacao_id || ' ja foi devolvida');
    END IF;

    v_dev := TRUNC(NVL(p_data_devolucao, SYSDATE));
    IF v_dev < v_saida THEN
        RAISE_APPLICATION_ERROR(-20009, 'EQL-009: Data de devolucao anterior a data de saida');
    END IF;

    IF p_equipamento_avaria_id IS NOT NULL THEN
        BEGIN
            SELECT e.valor_reposicao INTO v_repo
              FROM item_locacao i
              JOIN equipamento e ON e.equipamento_id = i.equipamento_id
             WHERE i.locacao_id = p_locacao_id AND i.equipamento_id = p_equipamento_avaria_id;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(-20008, 'EQL-008: Equipamento ' || p_equipamento_avaria_id ||
                    ' nao pertence a locacao ' || p_locacao_id);
        END;
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
END sp_devolver_locacao;
/
