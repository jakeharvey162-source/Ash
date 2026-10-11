"""Allowlisted public-data plugin adapters for the Ash desktop agent.

Unlike a general-purpose HTTP fetcher these tools have fixed destinations and
methods, cap responses, refuse redirects, and never send local credentials.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone

MAX_BYTES = 550_000
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
REPOSITORIES = {
    "gods-eye-view": "bilawalsidhu/gods-eye-view",
    "shadowbroker": "BigBodyCobain/Shadowbroker",
    "spiderfoot": "smicallef/spiderfoot",
    "strix": "usestrix/strix",
    "wazuh": "wazuh/wazuh",
    "openjarvis": "open-jarvis/OpenJarvis",
    "superpowers": "obra/superpowers",
    "shadcn-ui": "shadcn-ui/ui",
    "magicui": "magicuidesign/magicui",
}
class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("The public data plugin refused a redirect")

def _json_get(url: str, opener=None):
    if url != USGS_URL and url not in {
        "https://api.github.com/repos/" + repo for repo in REPOSITORIES.values()
    }:
        raise ValueError("Public plugin request must use a pinned HTTPS API")
    request = urllib.request.Request(url, headers={"Accept":"application/json",
                                                   "User-Agent":"AshDesktopPublicSources/1.0"}, method="GET")
    transport = opener or urllib.request.build_opener(_RefuseRedirects()).open
    with transport(request, timeout=8) as response:
        content = response.read(MAX_BYTES + 1)
    if len(content)>MAX_BYTES:
        raise ValueError("Public data plugin response exceeds configured limit")
    parsed=json.loads(content.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Unexpected public API response")
    return parsed

def catalogue():
    return [
        {"name":"world.usgs.earthquakes","kind":"public-geospatial",
         "source":"USGS GeoJSON", "requires_key":False, "status":"call-to-check-live",
         "method":"GET","permissions":["read public earthquake events"]},
        {"name":"plugins.github.repository","kind":"open-source-research",
         "source":"GitHub public repository API","requires_key":False,
         "status":"call-to-check-live","method":"GET",
         "permissions":["read metadata of listed third-party projects"]},
    ]

def earthquakes(opener=None):
    data=_json_get(USGS_URL,opener=opener)
    features=data.get("features")
    if not isinstance(features,list):
        raise ValueError("USGS features unavailable")
    items=[]
    for f in features[:100]:
        if not isinstance(f,dict):
            continue
        p=f.get("properties") or {}
        g=f.get("geometry") or {}
        coords=g.get("coordinates")
        if not isinstance(p,dict) or not isinstance(coords,list) or len(coords)<2:
            continue
        try:
            lon,lat=float(coords[0]),float(coords[1])
            magnitude=float(p.get("mag") or 0)
        except (ValueError,TypeError):
            continue
        if not (-180<=lon<=180 and -90<=lat<=90 and -1<=magnitude<=12):
            continue
        items.append({"title":str(p.get("place") or "Unspecified region")[:180],
                      "magnitude":magnitude,"lat":lat,"lon":lon,
                      "occurred_at_ms":p.get("time"),
                      "url":str(p.get("url") or "")[:220]})
    return {"source":"USGS daily public earthquake feed","received_at":datetime.now(timezone.utc).isoformat(),
            "data_delayed_or_incomplete":True,"event_count":len(items),"events":items[:50]}

def github_project(project: str, opener=None):
    if project not in REPOSITORIES:
        raise ValueError("Choose one of the reviewed third-party project IDs")
    repo=REPOSITORIES[project]
    data=_json_get("https://api.github.com/repos/"+repo,opener=opener)
    return {"source":"GitHub API","project":project,"full_name":str(data.get("full_name") or repo)[:180],
            "description":str(data.get("description") or "")[:380],
            "homepage":str(data.get("homepage") or "")[:220],
            "stars":data.get("stargazers_count"),"pushed_at":data.get("pushed_at"),
            "archived":bool(data.get("archived")),"license":(data.get("license") or {}).get("spdx_id"),
            "html_url":"https://github.com/"+repo,
            "metadata_only":True,"not_installed":True}
