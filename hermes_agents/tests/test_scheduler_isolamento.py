"""_worker() (core/scheduler.py) rodava os jobs em sequencia na mesma thread:
um sync Bling lento (NF-e pagina ate' 50 notas com backoff de ate' 7s cada em
rate limit) segurava o loop por minutos, e nesse meio tempo o job
shopee-renovar-tokens — que precisa rodar a cada 15min pra renovar token que
expira em 30min — nao rodava. Por isso os jobs Bling viviam comentados.
Agora cada job roda em thread propria, com trava por job pra nao sobrepor
execucoes do mesmo sync (o que multiplicaria chamadas a API do Bling)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scheduler import _deve_rodar, _run_job, add_job, JOBS


class TestDeveRodar(unittest.TestCase):
    def _job(self, **kw):
        base = {"fn": lambda: None, "name": "x", "interval": 300,
                "last_run": 0.0, "running": False}
        base.update(kw)
        return base

    def test_roda_quando_intervalo_passou_e_nao_esta_rodando(self):
        self.assertTrue(_deve_rodar(self._job(last_run=0.0), now=301.0))

    def test_nao_roda_antes_do_intervalo(self):
        self.assertFalse(_deve_rodar(self._job(last_run=100.0), now=200.0))

    def test_nao_roda_se_execucao_anterior_ainda_esta_em_andamento(self):
        """last_run e' marcado no INICIO da execucao. Sem essa trava, um job
        que demore mais que o proprio intervalo seria disparado de novo em
        paralelo consigo mesmo."""
        self.assertFalse(_deve_rodar(self._job(last_run=0.0, running=True), now=99999.0))


class TestRunJob(unittest.TestCase):
    def test_libera_a_trava_ao_terminar(self):
        job = {"fn": lambda: None, "name": "ok", "interval": 1, "last_run": 0.0, "running": True}
        _run_job(job)
        self.assertFalse(job["running"])

    def test_libera_a_trava_mesmo_com_excecao_e_nao_propaga(self):
        def explode():
            raise RuntimeError("falhou")
        job = {"fn": explode, "name": "ruim", "interval": 1, "last_run": 0.0, "running": True}
        _run_job(job)  # nao deve levantar
        self.assertFalse(job["running"])


class TestAddJob(unittest.TestCase):
    def test_job_novo_nasce_destravado(self):
        marcador = "job-teste-isolamento"
        add_job(lambda: None, marcador, 60)
        try:
            job = next(j for j in JOBS if j["name"] == marcador)
            self.assertFalse(job["running"])
            self.assertEqual(job["last_run"], 0.0)
        finally:
            JOBS[:] = [j for j in JOBS if j["name"] != marcador]


if __name__ == "__main__":
    unittest.main()
