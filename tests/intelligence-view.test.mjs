import test from "node:test";
import assert from "node:assert/strict";
import {fetchPublicEarthquakes,renderIntelligenceCatalog} from "../src/intelligence-view.js";

test("public intelligence UI describes live state truthfully",()=>{
 const html=renderIntelligenceCatalog();
 assert.match(html,/not embedded/);
 assert.match(html,/loadPublicQuakes/);
 assert.match(html,/No network request yet/);
});

test("USGS data retrieval uses fixed open HTTPS source and omits user credentials",async()=>{
 let observed;
 const events=await fetchPublicEarthquakes(async(url,opts)=>{
  observed={url,opts};
  return {ok:true,json:async()=>({features:[
   {properties:{place:"Near Johannesburg",mag:3.3,time:1791744400000},
    geometry:{coordinates:[28.1,-26.1,8]}}
  ]})};
 });
 assert.match(observed.url,/^https:\/\/earthquake\.usgs\.gov\//);
 assert.equal(observed.opts.credentials,"omit");
 assert.equal(observed.opts.method,"GET");
 assert.equal(events.length,1);
 assert.equal(events[0].magnitude,3.3);
});

test("unavailable public feed fails and cannot be presented as verified data",async()=>{
 await assert.rejects(fetchPublicEarthquakes(async()=>({ok:false,status:503})),/HTTP 503/);
});
