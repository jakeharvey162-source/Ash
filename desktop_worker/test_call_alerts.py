import pathlib
import tempfile
import unittest
import urllib.parse

from call_alerts import OwnerCallAlerts

GOOD = {
    "ASH_CALL_ALERTS_ENABLED": "1",
    "ASH_OWNER_PHONE": "+27111234567",
    "TWILIO_FROM_NUMBER": "+27119876543",
    "TWILIO_ACCOUNT_SID": "AC" + "a"*32,
    "TWILIO_AUTH_TOKEN": "fictional-test-token",
    "ASH_CALL_ALERT_MAX_DAILY": "2",
}


class FakeResponse:
    status = 201
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass


class PhoneAlertsTests(unittest.TestCase):
    def test_no_real_call_without_explicit_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            called = []
            alerts = OwnerCallAlerts(environ={**GOOD, "ASH_CALL_ALERTS_ENABLED": "0"},
                                     ledger_path=pathlib.Path(directory)/"calls.json",
                                     opener=lambda *a, **kw: called.append(a))
            self.assertEqual(alerts.alert(job_id="job-1")["reason"], "not_configured")
            self.assertEqual(called, [])

    def test_only_owner_number_and_safe_fixed_message(self):
        with tempfile.TemporaryDirectory() as directory:
            requests=[]
            def opener(req, timeout=0):
                requests.append((req, timeout))
                return FakeResponse()
            alerts=OwnerCallAlerts(environ=GOOD,ledger_path=pathlib.Path(directory)/"calls.json",opener=opener)
            self.assertEqual(alerts.alert(job_id="job-1",category="approval_needed")["reason"],"carrier_accepted")
            self.assertEqual(len(requests),1)
            req,timeout=requests[0]
            self.assertEqual(timeout,12)
            self.assertTrue(req.full_url.startswith("https://api.twilio.com/"))
            form=urllib.parse.parse_qs(req.data.decode())
            self.assertEqual(form["To"],[GOOD["ASH_OWNER_PHONE"]])
            self.assertEqual(form["From"],[GOOD["TWILIO_FROM_NUMBER"]])
            self.assertIn("Sign in to Ash",form["Twiml"][0])
            self.assertNotIn("job-1",form["Twiml"][0])
            self.assertEqual(alerts.alert(job_id="job-1")["reason"],"already_attempted")
            self.assertEqual(len(requests),1)

    def test_throttled_on_daily_attempts_not_carrier_success(self):
        with tempfile.TemporaryDirectory() as directory:
            def failing(*_args, **_kw):
                raise RuntimeError("fake network outage")
            alerts=OwnerCallAlerts(environ=GOOD,ledger_path=pathlib.Path(directory)/"calls.json",opener=failing)
            self.assertEqual(alerts.alert(job_id="one")["reason"],"carrier_unavailable")
            self.assertEqual(alerts.alert(job_id="one")["reason"],"already_attempted")
            self.assertEqual(alerts.alert(job_id="two")["reason"],"carrier_unavailable")
            self.assertEqual(alerts.alert(job_id="three")["reason"],"daily_limit")

    def test_invalid_numbers_job_identifiers_and_categories_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            base=pathlib.Path(directory)/"calls.json"
            for phone in ["123","0111234567","+1;echo unsafe","+00000000"]:
                alerts=OwnerCallAlerts(environ={**GOOD,"ASH_OWNER_PHONE":phone},ledger_path=base)
                self.assertFalse(alerts.configured())
            a=OwnerCallAlerts(environ=GOOD,ledger_path=base,opener=lambda *args, **kw: FakeResponse())
            with self.assertRaises(ValueError):
                a.alert(job_id="../bad")
            with self.assertRaises(ValueError):
                a.alert(job_id="test",category="send_payment")
