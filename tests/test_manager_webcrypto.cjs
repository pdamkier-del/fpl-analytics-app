'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const context={crypto:require('node:crypto').webcrypto,TextEncoder,TextDecoder,Uint8Array,JSON,atob,window:{},document:{getElementById:()=>({})}};
vm.createContext(context);vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../app/manager-online.js'),'utf8'),context);
(async()=>{const key=await context.crypto.subtle.importKey('pkcs8',Buffer.from(input.private_key,'base64'),{name:'RSA-OAEP',hash:'SHA-256'},false,['decrypt']);const result=await context.window.FplEncryptedManagerResult.open(input.envelope,key);await assert.rejects(()=>context.window.FplEncryptedManagerResult.open({...input.envelope,version:2},key));console.log(JSON.stringify(result));})().catch(e=>{console.error(e.message);process.exitCode=1});
