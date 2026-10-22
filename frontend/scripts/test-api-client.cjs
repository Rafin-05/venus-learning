#!/usr/bin/env node
// Tests the actual TypeScript API module with isolated HTTP responses; no test framework required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../lib/api.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2021}}).outputText;
let calls = [], replies = [];
const sandbox = {exports:{}, Headers, FormData, URL, fetch:async (url, options={}) => {
  calls.push({url, options});
  assert.ok(replies.length, `Unexpected fetch: ${url}`);
  const next = replies.shift();
  if (next instanceof Error) throw next;
  return next;
}};
vm.runInNewContext(compiled, sandbox, {filename:'api.ts'});
const {api,post,patch,list,all} = sandbox.exports;
const response = (body,status=200) => ({ok:status>=200 && status<300,status,json:async()=>body});
let passed = 0;
async function test(name, fn) { calls=[]; replies=[]; await fn(); assert.equal(replies.length,0); passed++; console.log(`PASS: ${name}`); }
(async()=>{
  await test('GET uses the shared /api origin, cookies and no-store',async()=>{
    replies=[response({id:1})]; assert.equal((await api('/auth/me/')).id,1);
    assert.equal(calls[0].url,'/api/auth/me/'); assert.equal(calls[0].options.credentials,'same-origin'); assert.equal(calls[0].options.cache,'no-store');
  });
  await test('Every mutation fetches a fresh CSRF token, including after login rotation',async()=>{
    replies=[response({csrfToken:'before-login'}),response({ok:true}),response({csrfToken:'after-login'}),response({ok:true})];
    await post('/auth/login/',{email:'test@example.test',password:'test-only'}); await patch('/profile/',{full_name:'Updated'});
    assert.equal(calls[1].options.headers.get('X-CSRFToken'),'before-login'); assert.equal(calls[3].options.headers.get('X-CSRFToken'),'after-login');
    assert.equal(calls[3].options.headers.get('Content-Type'),'application/json');
  });
  await test('Multipart uploads retain the browser-generated content boundary',async()=>{
    replies=[response({csrfToken:'upload-token'}),response({url:'/api/uploads/test/content/'})];
    const body=new FormData(); body.append('purpose','avatar'); await api('/uploads/',{method:'POST',body});
    assert.equal(calls[1].options.body,body); assert.equal(calls[1].options.headers.has('Content-Type'),false); assert.equal(calls[1].options.headers.get('X-CSRFToken'),'upload-token');
  });
  await test('Missing CSRF prevents a mutation',async()=>{
    replies=[response({})]; await assert.rejects(()=>post('/issues/',{}),/security token is missing/); assert.equal(calls.length,1);
  });
  await test('All pagination pages are combined without following an external host',async()=>{
    replies=[response({results:[{id:1}],next:'https://backend.internal/api/courses/?page=2'}),response({results:[{id:2}],next:null})];
    const data=await all('/courses/'); assert.equal(data.length,2); assert.equal(calls[1].url,'/api/courses/?page=2');
  });
  await test('Pagination cannot redirect to another API resource',async()=>{
    replies=[response({results:[],next:'/api/staff/users/?page=2'})]; await assert.rejects(()=>api('/courses/'),/invalid pagination link/);
  });
  await test('DRF nested validation errors are displayed as plain readable text',async()=>{
    replies=[response({csrfToken:'token'}),response({questions:[{correct_answer:['Choose a valid answer.']}]},400)];
    await assert.rejects(()=>post('/quizzes/',{}),/400: correct answer: Choose a valid answer/);
  });
  await test('Rate-limit, network and empty-delete responses are handled',async()=>{
    replies=[response({},429)]; await assert.rejects(()=>api('/courses/'),/Too many attempts/);
    replies=[new Error('offline')]; await assert.rejects(()=>api('/courses/'),/could not be reached/);
    replies=[response({csrfToken:'token'}),response(null,204)]; assert.equal(await api('/issues/1/',{method:'DELETE'}),undefined);
  });
  await test('External API paths are rejected before a request',async()=>{
    await assert.rejects(()=>api('https://other.example/api/'),/Invalid API path/); await assert.rejects(()=>api('//other.example/api/'),/Invalid API path/); assert.equal(calls.length,0);
    assert.equal(list({results:[1,2]}).length,2);
  });
  console.log(`Completed ${passed} shared API client tests.`);
})().catch(error=>{console.error(error);process.exitCode=1;});
