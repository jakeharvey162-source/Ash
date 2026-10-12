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


if __name__ == "__main__":
    unittest.main()
