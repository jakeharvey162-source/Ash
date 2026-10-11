import json
import unittest
from trusted_sources import REPOSITORIES, _json_get, catalogue, earthquakes, github_project, USGS_URL

class Response:
    def __init__(self,obj): self.raw=json.dumps(obj).encode()
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n): return self.raw[:n]

class TrustedSourceTests(unittest.TestCase):
    def test_catalog_does_not_claim_external_services_installed(self):
        listed=catalogue()
        self.assertEqual(len(listed),2)
        self.assertEqual(listed[0]["status"],"call-to-check-live")

    def test_cannot_request_arbitrary_web_or_local_addresses(self):
        for address in ("https://127.0.0.1/admin","https://example.com",
                        "http://api.github.com/repos/obra/superpowers"):
            with self.assertRaises(ValueError): _json_get(address,opener=lambda req,timeout:Response({}))

    def test_usgs_earthquakes_normalized_and_capped(self):
        def transport(req,timeout):
            self.assertEqual(req.full_url,USGS_URL)
            features=[{"properties":{"place":"near test", "mag":3.5, "time":1700,
                                      "url":"https://earthquake.usgs.gov/test"},
                       "geometry":{"coordinates":[28.0,-26.0,4]}}]*3
            return Response({"features":features})
        result=earthquakes(opener=transport)
        self.assertEqual(result["event_count"],3)
        self.assertEqual(result["events"][0]["lat"],-26)
        self.assertTrue(result["data_delayed_or_incomplete"])

    def test_github_registry_only_known_repos(self):
        def transport(req,timeout):
            self.assertEqual(req.get_method(),"GET")
            self.assertIn("/repos/obra/superpowers",req.full_url)
            return Response({"full_name":"obra/superpowers","description":"Test",
                             "stargazers_count":200000,"license":{"spdx_id":"MIT"}})
        result=github_project("superpowers",opener=transport)
        self.assertTrue(result["not_installed"])
        self.assertEqual(result["license"],"MIT")
        with self.assertRaises(ValueError):
            github_project("https://github.com/unknown/private",opener=transport)

if __name__=="__main__":
    unittest.main()
