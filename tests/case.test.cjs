const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('case example formats the same amounts and selects captions after language changes', () => {
  const amounts = ['800000','400000','400000'].map(value => ({dataset:{caseAmount:value},textContent:''}));
  const tracks = ['ru','en','uz'].map(language=>({language,mode:'disabled'}));
  const events = {};
  const video = {textTracks:tracks,addEventListener(){}};
  const context = {Intl,Number,document:{title:'',getElementById:()=>video,querySelectorAll:()=>amounts},
    window:{i18n:{locale:'ru-RU',language:'ru',t:key=>key},addEventListener:(name,fn)=>events[name]=fn}};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('app/static/case.js','utf8'),context);
  assert.equal(amounts[0].textContent,new Intl.NumberFormat('ru-RU').format(800000));
  for (const [language,locale] of [['en','en-US'],['uz','uz-UZ'],['ru','ru-RU']]) {
    context.window.i18n.language=language; context.window.i18n.locale=locale;
    events.languagechange();
    assert.deepEqual(amounts.map(x=>x.dataset.caseAmount),['800000','400000','400000']);
    assert.equal(amounts[0].textContent,new Intl.NumberFormat(locale).format(800000));
    assert.equal(tracks.find(x=>x.mode==='showing').language,language);
    assert.equal(tracks.filter(x=>x.mode==='showing').length,1);
  }
});
