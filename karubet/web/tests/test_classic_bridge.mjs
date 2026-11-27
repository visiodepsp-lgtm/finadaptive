/* Integración cliente: plantilla clásica recibe probabilidades originales.
   Sin red, sin credenciales y sin paquetes npm externos. */
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const source=fs.readFileSync('karubet/web/app.js','utf8');
const env={
  sessionStorage:{getItem:()=>null}, 
  window:{addEventListener:()=>{},KARUBET_ORIGINAL_LOGO:''},
  document:{addEventListener:()=>{}},
  location:{origin:'https://example.test'},
  Intl,Date,Number,Object,Array,String,JSON,console,URLSearchParams
};
vm.createContext(env);
vm.runInContext(source,env);
vm.runInContext("globalThis.testClassicPayload=classicPayload;globalThis.testState=state;",env);
env.testState.fixtures=[{
  fixture_id:12345,competition:'serie-a',home_team:'Napoli',away_team:'Inter',
  kickoff_at:'2026-11-29T14:00:00+00:00',
  model:{generated_at:'2026-11-27T14:00:00+00:00',
    metrics:{lambda_home:1.75,lambda_away:1.3,h2h_count:7,h2h_evidence:2.1},
    probabilities:{
      pa:.52,qpa:.18,dpa:.08,rem:.02,
      original_pa:.50,original_qpa:.15,original_dpa:.06,original_rem:.015,
      ewma:{pa:.48,qpa:.16,dpa:.07,rem:.018},
      h2h:{pa:.54,qpa:.20,dpa:.09,rem:.025}
    }
  }
}];
env.testState.lastModelDate='2026-11-27T14:00:00+00:00';
const p=env.testClassicPayload();
assert.equal(p.rows.length,1);
const r=p.rows[0];
assert.equal(r.home,'Napoli');
assert.equal(r.away,'Inter');
assert.equal(r.fixture_id,12345);
assert.equal(r.ewma_pa,.48);
assert.equal(r.h2h_dpa,.09);
assert.equal(r.original_pa,.50);
assert.equal(r.lambda_h,1.75);
assert.equal(r.h2h_count,7);
assert.equal(r.dia,'2026-11-29');
assert.equal(r.hora,'09:00');
assert.equal(r.h2h_matches.length,0);
assert.equal('SUPABASE_SECRET_KEY' in p,false);
assert.equal('token' in p,false);
console.log('KARUBET: puente probabilidad -> plantilla original, correcto.');
