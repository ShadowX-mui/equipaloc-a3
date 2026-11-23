package app;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

/** Abre as conexoes JDBC. Hosts vem de variaveis de ambiente do compose; senhas sao de LABORATORIO. */
public final class Conexao {
    private Conexao() {}

    private static String env(String chave, String padrao) {
        String v = System.getenv(chave);
        return v == null ? padrao : v;
    }

    public static Connection postgres() throws SQLException {
        String url = "jdbc:postgresql://" + env("PG_HOST", "localhost") + ":5432/a3";
        return DriverManager.getConnection(url, "a3", "a3lab");
    }

    public static Connection oracle() throws SQLException {
        String url = "jdbc:oracle:thin:@//" + env("ORA_HOST", "localhost") + ":1521/XEPDB1";
        return DriverManager.getConnection(url, "a3", "a3lab");
    }
}
