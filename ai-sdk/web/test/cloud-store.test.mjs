import test from 'node:test';
import assert from 'node:assert/strict';
import { createCloudStore } from '../cloud-store.mjs';
function fixture() {
  const objects = new Map(); let seq = 0;
  const request = async (url, options = {}) => {
    const u = new URL(url);
    const name = options.method === 'POST' ? u.searchParams.get('name') : decodeURIComponent(u.pathname.split('/o/')[1]);
    const old = objects.get(name);
    if (options.method !== 'POST') return old ? new Response(JSON.stringify(old.data), { headers: {'x-goog-generation':old.generation} }) : new Response('', {status:404});
    if (u.searchParams.get('ifGenerationMatch') !== (old?.generation || '0')) return new Response('', {status:412});
    objects.set(name, {data:JSON.parse(options.body),generation:String(++seq)});
    return new Response('{}');
  };
  return { objects, store:()=>createCloudStore({bucket:'test-bucket', fetch:request,token:async ()=>'test-token'}) };
}
test('concurrent revisions share an atomic cap and restart cannot reset it', async()=>{
  const f=fixture(); const a=f.store(), b=f.store();
  const results=await Promise.all([a.reserve('2026-10-26','a','1',1),b.reserve('2026-10-26','b','2',1)]);
  assert.deepEqual(results.sort(),[false,true]);
  assert.equal(await f.store().reserve('2026-10-26','c','3',1),false);
  assert.equal(f.objects.get('limits/2026-10-26.json').data.turns.length,1);
});
test('three daily turns per signed visitor; next day starts a fresh allowance',async()=>{
 const f=fixture();const s=f.store();
 for(let i=0;i<3;i++)assert.equal(await s.reserve('2026-10-26','visitor',String(i),100),true);
 assert.equal(await s.reserve('2026-10-26','visitor','4',100),false);
 assert.equal(await s.reserve('2026-10-27','visitor','5',100),true);
});
test('storage outages fail closed before authorizing a turn',async()=>{
 const s=createCloudStore({bucket:'test-bucket',token:async()=>'test',fetch:async()=>new Response('',{status:503})});
 await assert.rejects(s.reserve('2026-10-26','visitor','turn',100),/unavailable/);
});
test('session starts are bounded; event objects never overwrite one another',async()=>{
 const f=fixture();const s=f.store();
 for(let i=0;i<300;i++)assert.equal(await s.start('2026-10-26'),true);
 assert.equal(await s.start('2026-10-26'),false);
 await Promise.all([s.event({at:'2026-10-26T00:00:00Z',event:'one'}),s.event({at:'2026-10-26T00:00:00Z',event:'two'})]);
 assert.equal([...f.objects.keys()].filter(k=>k.startsWith('events/')).length,2);
});
