import pathlib
import tempfile
import unittest
from free_owner_alerts import FreeOwnerAlerts

TOPIC = "i8rY56QZLk9d2eS4Gva1CBnHwP7t3fx0"
ENV = {
    "ASH_PUSH_ENABLED": "1",
    "ASH_NTFY_TOPIC": TOPIC,
    "ASH_PUSH_MAX_DAILY": "2",
}

class Reply:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *_args): return False


class FreePushAlertsTests(unittest.TestCase):
    def test_no_push_without_owner_opt_in(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            p=FreeOwnerAlerts(environ={**ENV, "ASH_PUSH_ENABLED":"0"},
                ledger_path=pathlib.Path(folder)/"ledger.json", opener=lambda *x, **y: calls.append(x))
            self.assertFalse(p.configured())
            self.assertEqual(p.alert(job_id="job-1")["reason"], "not_configured")
            self.assertEqual(calls, [])

    def test_rejects_weak_topics_and_fake_categories(self):
        with tempfile.TemporaryDirectory() as folder:
            for topic in ("ash", "a"*42, "shortpassword", "space in topic", "../etc/passwd", "x"*81):
                p=FreeOwnerAlerts(environ={**ENV,"ASH_NTFY_TOPIC":topic},
                    ledger_path=pathlib.Path(folder)/"ledger.json")
                self.assertFalse(p.configured(),topic)
            p=FreeOwnerAlerts(environ=ENV,ledger_path=pathlib.Path(folder)/"ledger.json")
            with self.assertRaises(ValueError):p.alert(job_id="paid?money")
            with self.assertRaises(ValueError):p.alert(job_id="task-1", category="transfer_money")

    def test_provider_gets_only_generic_owner_message(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            def opener(req,timeout):
                calls.append((req,timeout))
                return Reply()
            p=FreeOwnerAlerts(environ=ENV,ledger_path=pathlib.Path(folder)/"ledger.json",opener=opener)
            self.assertEqual(p.alert(job_id="secret-customer-id",category="website_ready")["reason"],"notification_accepted")
            self.assertEqual(len(calls),1)
            req,timeout=calls[0]
            self.assertEqual(req.full_url,"https://ntfy.sh/"+TOPIC)
            self.assertEqual(req.get_method(),"POST")
            self.assertEqual(timeout,12)
            body=req.data.decode()
            self.assertIn("review",body)
            self.assertNotIn("secret-customer-id",body)
            self.assertNotIn("client@example.com",body)
            self.assertEqual(req.headers["Click"],"https://ash-f4.vercel.app/")
            self.assertEqual(p.alert(job_id="secret-customer-id",category="website_ready")["reason"],"already_attempted")
            self.assertEqual(len(calls),1)

    def test_limits_requests_even_on_network_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            n=[0]
            def failing(*_args,**_kwargs):
                n[0]+=1
                raise OSError("connection error")
            p=FreeOwnerAlerts(environ=ENV,ledger_path=pathlib.Path(folder)/"ledger.json",opener=failing)
            self.assertEqual(p.alert(job_id="one")["reason"],"network_unavailable")
            self.assertEqual(p.alert(job_id="one")["reason"],"already_attempted")
            self.assertEqual(p.alert(job_id="two")["reason"],"network_unavailable")
            self.assertEqual(p.alert(job_id="three")["reason"],"daily_limit")
            self.assertEqual(n[0],2)



class WorkerNotificationIntegrationTests(unittest.TestCase):
    def _worker(self, folder, *, build_ok=True, verified=True):
        from remote_worker import AshRemoteWorker
        from types import SimpleNamespace

        class BuilderAgent:
            def build_fullstack(self, _prompt, workspace):
                path=pathlib.Path(workspace)
                path.mkdir(parents=True,exist_ok=True)
                (path/"index.html").write_text("<main>Client demo</main>",encoding="utf-8")
                return SimpleNamespace(
                    ok=build_ok,
                    output="Built" if build_ok else "Build failed",
                    details={
                        "verification":{"build_passed":verified},
                        "generation_mode":"test",
                        "degraded":False,
                        "generated_files":["index.html"],
                    },
                )
        worker=AshRemoteWorker.__new__(AshRemoteWorker)
        worker.workspace_root=pathlib.Path(folder)
        worker.device_name="Test Computer"
        worker.agent=BuilderAgent()
        worker._builder_prompt=lambda prompt,payload:(prompt,{"preset":"test"})
        worker._start_local_preview=lambda *args:""
        worker.finished=[]
        worker.notifications=[]
        worker.finish=lambda job_id,**kwargs:worker.finished.append((job_id,kwargs))
        worker._notify_owner_review=lambda job_id,category="approval_needed":worker.notifications.append((job_id,category))
        worker.emit=lambda *args,**kwargs:None
        return worker

    def test_verified_client_build_sends_owner_only_review_notice(self):
        with tempfile.TemporaryDirectory() as folder:
            w=self._worker(folder)
            w.process({"id":"job-verified","kind":"builder","payload":{"prompt":"Build a client site","builder":True,"source":"business_desk"}})
            self.assertTrue(w.finished[0][1]["ok"])
            self.assertEqual(w.notifications,[("job-verified","website_ready")])

    def test_failed_or_unverified_client_build_sends_attention_not_success(self):
        with tempfile.TemporaryDirectory() as folder:
            w=self._worker(folder,build_ok=True,verified=False)
            w.process({"id":"job-no-proof","kind":"builder","payload":{"prompt":"Build a client site","builder":True,"source":"business_desk"}})
            self.assertEqual(w.notifications,[("job-no-proof","job_failed")])

    def test_non_client_build_never_spams_owner(self):
        with tempfile.TemporaryDirectory() as folder:
            w=self._worker(folder)
            w.process({"id":"job-private","kind":"builder","payload":{"prompt":"Build my own app","builder":True,"source":"user"}})
            self.assertEqual(w.notifications,[])


class AlertCliTests(unittest.TestCase):
    def test_cli_checks_configuration_without_sending(self):
        from owner_alert_cli import main
        class Stub:
            def configured(self): return True
            def alert(self,**kwargs): raise AssertionError("check must not send")
        self.assertEqual(main(["check"], notifier=Stub()),0)

    def test_cli_never_claims_actual_phone_delivery(self):
        from owner_alert_cli import main
        class Stub:
            def configured(self): return True
            def alert(self,**kwargs):
                self.args=kwargs
                return {"sent":True,"reason":"notification_accepted"}
        n=Stub()
        self.assertEqual(main(["test"], notifier=n),0)
        self.assertEqual(n.args["category"],"test")
        self.assertRegex(n.args["job_id"],r"^test-[a-f0-9]{16}$")

    def test_cli_does_not_send_until_configured(self):
        from owner_alert_cli import main
        class Stub:
            def configured(self): return False
            def alert(self,**kwargs): raise AssertionError("must not send")
        self.assertEqual(main(["test"], notifier=Stub()),2)


if __name__ == "__main__":
    unittest.main()
