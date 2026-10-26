import assert from 'node:assert/strict';
import test from 'node:test';
import { createAnswer } from '../llm.mjs';
test('optional LLM uses server credentials and bounded output through AI SDK',async()=>{
 let calls=0;
 const answer=createAnswer({apiKey:'offline-test',model:'gpt-4o-mini',fetch:async(url,options)=>{
  calls++;assert.equal(new Headers(options.headers).get('authorization'),'Bearer offline-test');
  const body=JSON.parse(options.body);assert.equal(body.model,'gpt-4o-mini');assert.ok(body.max_tokens===200||body.max_completion_tokens===200);
  return Response.json({id:'test',created:1,model:'gpt-4o-mini',choices:[{index:0,message:{role:'assistant',content:'Hello from your assistant.'},finish_reason:'stop'}],usage:{prompt_tokens:4,completion_tokens:5,total_tokens:9}});
 }});
 assert.equal(await answer('Hello',{abortSignal:new AbortController().signal}),'Hello from your assistant.');assert.equal(calls,1);
});
test('LLM failure never retries',async()=>{
 let calls=0;const answer=createAnswer({apiKey:'offline-test',model:'gpt-4o-mini',fetch:async()=>{calls++;return Response.json({error:{message:'Busy'}},{status:429});}});
 await assert.rejects(answer('Hello',{abortSignal:new AbortController().signal}));assert.equal(calls,1);
});
