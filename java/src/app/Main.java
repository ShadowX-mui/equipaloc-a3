package app;

import java.math.BigDecimal;
import java.sql.SQLException;
import java.sql.Savepoint;

/**
 * Demo JDBC: o MESMO fluxo roda nos dois bancos (consulta com bind, procedure, erro de negocio tratado,
 * transacao controlada pela aplicacao). Termina com ROLLBACK para nao alterar os dados de exemplo.
 * Rodar: docker compose --profile apps run --rm app-java
 */
public class Main {
    static final int CLIENTE_OK = 5, CLIENTE_COM_MULTA = 4, EQUIPAMENTO_LIVRE = 12;

    public static void main(String[] args) throws Exception {
        try (LocacaoDao dao = new LocacaoDaoPostgres(Conexao.postgres())) {
            demo(dao);
        }
        try (LocacaoDao dao = new LocacaoDaoOracle(Conexao.oracle())) {
            demo(dao);
        }
    }

    static void demo(LocacaoDao dao) throws SQLException {
        System.out.println("\n=== " + dao.banco() + " ===");
        System.out.println("cliente: " + dao.nomeDoCliente(CLIENTE_OK));

        int locacaoId = dao.registrar(CLIENTE_OK, EQUIPAMENTO_LIVRE, 3);
        System.out.println("locacao criada: " + locacaoId);

        // Erro de negocio (EQL-003: cliente com multa em aberto) tratado sem derrubar a transacao.
        Savepoint ponto = dao.marcarPonto();
        try {
            dao.registrar(CLIENTE_COM_MULTA, EQUIPAMENTO_LIVRE, 3);
        } catch (SQLException e) {
            System.out.println("erro de negocio tratado: " + LocacaoDao.mensagemDeNegocio(e));
            dao.voltarAoPonto(ponto);
        }

        System.out.println("equipamentos com diaria 45.00: " + dao.contarEquipamentosComDiaria(new BigDecimal("45.00")));

        dao.devolver(locacaoId);
        System.out.println("status apos devolver: " + dao.statusDaLocacao(locacaoId));

        dao.desfazer();
        System.out.println("ROLLBACK feito: nada foi gravado");
    }
}
