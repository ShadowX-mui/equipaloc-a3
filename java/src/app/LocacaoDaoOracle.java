package app;

import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Types;

/** Dialeto Oracle: procedures sao chamadas com CallableStatement e parametro OUT registrado. */
public class LocacaoDaoOracle extends LocacaoDao {
    public LocacaoDaoOracle(Connection c) throws SQLException {
        super(c);
    }

    @Override
    public String banco() {
        return "Oracle (JDBC thin)";
    }

    @Override
    public int registrar(int clienteId, int equipamentoId, int dias) throws SQLException {
        try (CallableStatement cs = c.prepareCall("{call sp_registrar_locacao(?, ?, ?, ?)}")) {
            cs.setInt(1, clienteId);
            cs.setInt(2, equipamentoId);
            cs.setInt(3, dias);
            cs.registerOutParameter(4, Types.NUMERIC);
            cs.execute();
            return cs.getInt(4);
        }
    }

    @Override
    public void devolver(int locacaoId) throws SQLException {
        try (CallableStatement cs = c.prepareCall("{call sp_devolver_locacao(?, ?, ?)}")) {
            cs.setInt(1, locacaoId);
            cs.setNull(2, Types.DATE);             // data nula = hoje
            cs.setNull(3, Types.NUMERIC);          // sem avaria
            cs.execute();
        }
    }
}
