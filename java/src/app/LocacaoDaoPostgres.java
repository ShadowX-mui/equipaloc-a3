package app;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Types;

/** Dialeto PostgreSQL: procedures com INOUT sao chamadas com CALL, que devolve uma linha. */
public class LocacaoDaoPostgres extends LocacaoDao {
    public LocacaoDaoPostgres(Connection c) throws SQLException {
        super(c);
    }

    @Override
    public String banco() {
        return "PostgreSQL (JDBC)";
    }

    @Override
    public int registrar(int clienteId, int equipamentoId, int dias) throws SQLException {
        try (PreparedStatement ps = c.prepareStatement("CALL sp_registrar_locacao(?, ?, ?, ?)")) {
            ps.setInt(1, clienteId);
            ps.setInt(2, equipamentoId);
            ps.setInt(3, dias);
            ps.setNull(4, Types.INTEGER);          // parametro INOUT: entra nulo, sai com o id
            try (ResultSet rs = ps.executeQuery()) {
                rs.next();
                return rs.getInt(1);
            }
        }
    }

    @Override
    public void devolver(int locacaoId) throws SQLException {
        try (PreparedStatement ps = c.prepareStatement(
                "CALL sp_devolver_locacao(?, CAST(? AS DATE), CAST(? AS INTEGER))")) {
            ps.setInt(1, locacaoId);
            ps.setNull(2, Types.DATE);             // data nula = hoje
            ps.setNull(3, Types.INTEGER);          // sem avaria
            ps.execute();
        }
    }
}
