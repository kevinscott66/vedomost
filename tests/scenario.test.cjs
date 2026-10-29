const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function scenario() {
  const elements = new Map();
  for (const match of fs.readFileSync('app/static/try.html','utf8').matchAll(/id="([^"]+)"/g)) {
    elements.set(match[1], {textContent:'', hidden:false, disabled:false, attributes:{}, handlers:{},
      setAttribute(key,value){ this.attributes[key]=value; },
      addEventListener(event,handler){ this.handlers[event]=handler; },
      focus(){ this.focused=true; },
    });
  }
  const events = {};
  const context = { Intl, document:{title:'',getElementById:id=>elements.get(id)},
    window:{VEDOMOST_TRANSLATIONS:{ru:{currencyUnit:'сум'},en:{currencyUnit:'UZS'},uz:{currencyUnit:'so‘m'}},
      addEventListener:(event,handler)=>events[event]=handler},
    fetch(){ throw new Error('Teaching example must not request a ledger mutation'); },
  };
  vm.createContext(context);
  for(const file of ['scenario-data.js','scenario-copy.js']) vm.runInContext(fs.readFileSync('app/static/'+file,'utf8'),context);
  let language='ru';
  context.window.i18n={get locale(){return language==='ru'?'ru-RU':language==='uz'?'uz-UZ':'en-US';},
    t(key,values={}) {return (context.window.VEDOMOST_TRANSLATIONS[language][key]||key).replace(/\{(\w+)\}/g,(_,name)=>values[name]??'');}};
  vm.runInContext(fs.readFileSync('app/static/scenario.js','utf8'),context);
  return {get:id=>elements.get(id), click:id=>elements.get(id).handlers.click(),
    language(value){language=value;events.languagechange();},context};
}

test('guided payment and rate change preserve recorded money, reset only the example',()=>{
  const app=scenario();
  const initial=app.get('tour-debt').textContent;
  assert.equal(initial.replace(/\s/g,''),'400000сум');
  assert.equal(app.get('tour-payment').hidden,true);
  app.click('tour-next');
  const booked=app.get('tour-debt').textContent;
  const payment=app.get('tour-equivalent').textContent;
  assert.equal(booked.replace(/\s/g,''),'280000сум');
  assert.equal(payment.replace(/\s/g,''),'120000сум');
  assert.equal(app.get('tour-payment').hidden,false);
  assert.equal(app.get('tour-reference').hidden,true);
  app.click('tour-next');
  assert.equal(app.get('tour-debt').textContent,booked);
  assert.equal(app.get('tour-equivalent').textContent,payment);
  assert.equal(app.get('tour-reference').hidden,false);
  assert.equal(app.get('tour-next').hidden,true);
  assert.equal(app.get('tour-next').disabled,true);
  assert.equal(app.get('tour-open').hidden,false);
  assert.notEqual(app.get('tour-old-display').textContent,app.get('tour-new-display').textContent);
  app.click('tour-next'); // Even a stale/programmatic duplicate cannot move past the final step.
  assert.equal(app.get('tour-debt').textContent,booked);
  app.language('en');
  assert.match(app.get('tour-title').textContent,/record keeps/);
  assert.match(app.get('tour-status').textContent,/record keeps/);
  assert.doesNotMatch(app.get('tour-status').textContent,/[А-Яа-я]/);
  assert.equal(app.get('tour-debt').textContent.replace(/\s/g,''),'280,000UZS');
  assert.equal(app.get('tour-open').hidden,false);
  app.click('tour-reset');
  assert.equal(app.get('tour-next').hidden,false);
  assert.equal(app.get('tour-next').disabled,false);
  assert.equal(app.get('tour-payment').hidden,true);
  assert.equal(app.get('tour-reference').hidden,true);
  assert.equal(app.get('tour-debt').textContent.replace(/\s/g,''),'400,000UZS');
  assert.equal(app.get('tour-title').focused,true);
});

test('all scenario copy is present in three languages, including accessibility text',()=>{
  const app=scenario();
  const copy=app.context.window.VEDOMOST_TRANSLATIONS;
  assert.deepEqual(Object.keys(copy.ru).sort(),Object.keys(copy.en).sort());
  assert.deepEqual(Object.keys(copy.ru).sort(),Object.keys(copy.uz).sort());
  for(const language of ['ru','en','uz']) {
    app.language(language);
    assert.ok(app.context.document.title.length>12);
    assert.equal(app.get('tour-step-0').attributes['aria-current'],'step');
    assert.equal(app.get('tour-step-1').attributes['aria-current'],'false');
    assert.doesNotMatch(app.get('tour-description').textContent,/^tour/);
  }
});
