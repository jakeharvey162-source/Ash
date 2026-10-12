import test from "node:test";
import assert from "node:assert/strict";
import {prepareClientBuild, businessBuildState, renderBusinessDesk} from "../src/business-desk.js";

const brief={client:"A Coffee Shop",email:"owner@example.com",project:"Coffee Store",request:"A responsive menu and booking website with working enquiry form.",design_preset:"warm-commerce"};
test("client projects queue real desktop builder work but never grant external release",()=>{
 const job=prepareClientBuild(brief);
 assert.equal(job.kind,"builder");
 assert.equal(job.requires_confirmation,false);
 assert.equal(job.payload.source,"business_desk");
 assert.equal(job.payload.external_delivery_authorized,false);
 assert.match(job.payload.prompt,/Do not email, publish, purchase/);
 assert.equal(job.payload.business_client.email,brief.email);
});
test("bad and injection-like client input cannot create a job",()=>{
 for(const email of ["bad-address","some <script>@example.com","a@invalid"]){
   assert.throws(()=>prepareClientBuild({...brief,email}),/valid customer email/);
 }
 assert.throws(()=>prepareClientBuild({...brief,request:"short"}),/Describe/);
 assert.throws(()=>prepareClientBuild({...brief,design_preset:"made-up"}),/supported/);
});
test("a completed job requires genuine successful build evidence before it can be reviewed",()=>{
 assert.equal(businessBuildState({status:"completed",result:{}}).ready,false);
 assert.equal(businessBuildState({status:"completed",result:{verification:{build_passed:true}}}).ready,false);
 assert.equal(businessBuildState({status:"completed",result:{verification:{build_passed:true},quality_report:{verified_build:true}}}).ready,true);
 assert.equal(businessBuildState({status:"failed",result:{verification:{build_passed:true},quality_report:{verified_build:true}}}).ready,false);
});
test("business page never injects client details and never claims payment was made",()=>{
 const escape=s=>String(s).replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
 const html=renderBusinessDesk({jobs:[{kind:"builder",status:"completed",payload:{source:"business_desk",business_client:{name:"<script>boom</script>",email:"safe@example.com",project:"Website"}},result:{verification:{build_passed:true},quality_report:{verified_build:true}}}]},escape);
 assert.match(html,/&lt;script&gt;boom/);
 assert.doesNotMatch(html,/<script>/);
 assert.match(html,/Payment has not been verified/);
 assert.match(html,/phone number or calling service is active/i);
});
