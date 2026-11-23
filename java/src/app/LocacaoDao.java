package app;

import java.math.BigDecimal;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Savepoint;

/**
 * Acesso as locacoes. O que e IGUAL nos dois bancos fica aqui (consultas com bind, transacao);
 * o que muda de dialeto (chamada das procedures) fica nas subclasses.
 * A transacao e controlada pela aplicacao: autoCommit desligado, commit/rollback explicitos.
 */
public abstract class LocacaoDao implements AutoCloseable {
    protected final Connection c;

    protected LocacaoDao(Connection c) throws SQLException {
        this.c = c;
        c.setAutoCommit(false);
    }

    public abstract String banco();

    /** Chama sp_registrar_locacao e devolve o id da locacao criada. */
    public abstract int registrar(int clienteId, int equipamentoId, int dias) throws SQLException;

    /** Chama sp_devolver_locacao (devolucao hoje, sem avaria). */
    public abstract void devolver(int locacaoId) throws SQLException;

    // ---- consultas com BIND (?): nunca concatenar valores no SQL ----
    public String nomeDoCliente(int clienteId) throws SQLException {
        return umTexto("SELECT nome FROM cliente WHERE cliente_id = ?", clienteId);
    }

    public String statusDaLocacao(int locacaoId) throws SQLException {
        return umTexto("SELECT status FROM locacao WHERE locacao_id = ?", locacaoId);
    }

    /** NUMERIC vai como BigDecimal (nunca double) para nao perder precisao. */
    public int contarEquipamentosComDiaria(BigDecimal diaria) throws SQLException {
        try (PreparedStatement ps = c.prepareStatement("SELECT COUNT(*) FROM equipamento WHERE valor_diaria = ?")) {
            ps.setBigDecimal(1, diaria);
            try (ResultSet rs = ps.executeQuery()) {
                rs.next();
                return rs.getInt(1);
            }
        }
    }

    private String umTexto(String sql, int parametro) throws SQLException {
        try (PreparedStatement ps = c.prepareStatement(sql)) {
            ps.setInt(1, parametro);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? rs.getString(1) : null;
            }
        }
    }

    // ---- controle de transacao ----
    /** No PostgreSQL um erro ABORTA a transacao inteira; o SAVEPOINT permite tratar o erro e continuar. */
    public Savepoint marcarPonto() throws SQLException {
        return c.setSavepoint();
    }

    public void voltarAoPonto(Savepoint ponto) throws SQLException {
        c.rollback(ponto);
    }

    public void desfazer() throws SQLException {
        c.rollback();
    }

    public void confirmar() throws SQLException {
        c.commit();
    }

    @Override
    public void close() throws SQLException {
        c.close();
    }

    /** Primeira linha da mensagem do banco (contem o codigo EQL-00n do erro de negocio). */
    public static String mensagemDeNegocio(SQLException e) {
        String m = e.getMessage();
        return m == null ? "" : m.split("\n")[0];
    }
}
