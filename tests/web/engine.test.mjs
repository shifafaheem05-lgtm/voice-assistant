// Run with: node --test tests/web
import test from 'node:test';
import assert from 'node:assert/strict';
import { Assistant, MemoryStorage, calculate, formatNumber, parseDuration, parseClockTime, normalizePhone,
         splitRecipientAndText, parseContactDetails, toEnglish, splitCompound, findSite, searchUrl, parseConversion, convertUnits } from '../../docs/engine.js';

const NOW = new Date(2026, 10, 5, 15, 0, 0);
function make(opts = {}) {
  const scheduled = [];
  const a = new Assistant({ now: () => NOW, rng: () => 0, schedule: (s, fn) => { const h = { s, fn, cancelled: false, cancel() { this.cancelled = true; } }; scheduled.push(h); return h; }, ...opts });
  a.scheduled = scheduled;
  return a;
}
const say = async (a, t) => (await a.handle(t)).text;
const links = async (a, t) => (await a.handle(t)).links;

test('calculator', () => {
  assert.equal(calculate('twelve times 7'), 84);
  assert.equal(calculate('2 to the power of 10'), 1024);
  assert.equal(calculate('-2 ** 2'), -4);
  assert.equal(calculate('(1 + 2) * 3'), 9);
  assert.equal(calculate('10 divided by 4'), 2.5);
  assert.equal(calculate('seven mod 4'), 3);
  assert.throws(() => calculate('1 / 0'), /divide by zero/);
  assert.throws(() => calculate('9 ** 999'), /too large/);
  assert.throws(() => calculate('hello'), /not a calculation/);
  assert.throws(() => calculate('alert(1) + 2'), /not a calculation/);   // nothing is ever evaluated as code
  assert.equal(formatNumber(1234567), '1,234,567');
  assert.equal(formatNumber(6.213712), '6.21371');
});

test('durations and clock times', () => {
  assert.equal(parseDuration('5 minutes'), 300);
  assert.equal(parseDuration('an hour'), 3600);
  assert.equal(parseDuration('ten seconds'), 10);
  assert.equal(parseDuration('soon'), null);
  assert.equal(parseClockTime('5:30 pm', NOW)[0], 9000);
  assert.equal(parseClockTime('7 am', NOW)[0], 16 * 3600);
  assert.equal(parseClockTime('3 pm', NOW)[0], 24 * 3600);
  for (const bad of ['5', '13 pm', '25:00', 'soon']) assert.equal(parseClockTime(bad, NOW), null, bad);
});

test('phone numbers and recipient splitting', () => {
  assert.equal(normalizePhone('0300 1234567'), '923001234567');
  assert.equal(normalizePhone('+92 300 1234567'), '923001234567');
  assert.equal(normalizePhone('zero three zero zero one two three four five six seven'), '923001234567');
  assert.equal(normalizePhone('0300 1234567', '1'), '13001234567');
  for (const bad of ['ali', '', '12', '0300 abc']) assert.equal(normalizePhone(bad), null, bad);
  const names = ['ali', 'ahmed khan'];
  assert.deepEqual(splitRecipientAndText('ali saying hello there', names), ['ali', 'hello there']);
  assert.deepEqual(splitRecipientAndText('ahmed khan see you', names), ['ahmed khan', 'see you']);
  assert.deepEqual(splitRecipientAndText('0300 1234567 call me', names), ['0300 1234567', 'call me']);
  assert.deepEqual(splitRecipientAndText('sara hello', names), ['sara', 'hello']);
  assert.deepEqual(parseContactDetails('sara email sara at gmail dot com'), ['sara', null, 'sara@gmail.com']);
  assert.deepEqual(parseContactDetails('ali phone number is 0300 1234567'), ['ali', '0300 1234567', null]);
});

test('sites and site search', () => {
  assert.equal(findSite('claude'), 'https://claude.ai');
  assert.equal(findSite('you tube'), 'https://www.youtube.com');
  assert.equal(findSite('no such site'), null);
  assert.equal(searchUrl('amazon', 'usb cable'), 'https://www.amazon.com/s?k=usb+cable');
  assert.equal(searchUrl('wiki', 'a b', { wiki: 'https://w.example/s?q={q}' }), 'https://w.example/s?q=a+b');
});

test('conversion', () => {
  assert.deepEqual(parseConversion('convert 10 km to miles'), [10, 'km', 'miles']);
  assert.deepEqual(parseConversion('how many miles in 10 km'), [10, 'km', 'miles']);
  assert.equal(parseConversion('what is 12 times 7'), null);
  assert.ok(Math.abs(convertUnits(10, 'km', 'miles')[0] - 6.2137) < 1e-3);
  assert.equal(convertUnits(100, 'celsius', 'fahrenheit')[0], 212);
  assert.equal(convertUnits(1, 'km', 'kg'), null);
});

test('roman urdu', () => {
  const cases = { 'youtube kholo': 'open youtube', 'ali ko hello bhejo': 'send whatsapp message to ali saying hello',
    'whatsapp kholo aur ali ko hi bhejo': 'send whatsapp message to ali saying hi', 'youtube kholo aur google kholo': 'open youtube and open google',
    'awaaz band karo': 'mute', 'notepad band karo': 'close notepad', 'ek mazaaq sunao': 'tell me a joke',
    '5 minute ka timer lagao': 'set a timer for 5 minutes', 'karachi ka mausam': 'weather in karachi' };
  for (const [roman, english] of Object.entries(cases)) assert.equal(toEnglish(roman), english, roman);
  assert.equal(toEnglish('send message to ali saying bring tea aur biscuits'), 'send message to ali saying bring tea aur biscuits');
});

test('compound commands', () => {
  assert.deepEqual(splitCompound('open youtube and open notepad'), ['open youtube', 'open notepad']);
  assert.deepEqual(splitCompound('search for salt and pepper'), ['search for salt and pepper']);
  assert.deepEqual(splitCompound('send message to ali saying hi and open youtube'), ['send message to ali saying hi and open youtube']);
});

test('opening sites and searching', async () => {
  const a = make();
  assert.equal(await say(a, 'open claude'), 'Opening claude.');
  assert.deepEqual(await links(a, 'open claude'), ['https://claude.ai']);
  assert.deepEqual(await links(a, 'open youtube, google and github'), ['https://www.youtube.com', 'https://www.google.com', 'https://github.com']);
  assert.deepEqual(await links(a, 'search amazon for usb cable'), ['https://www.amazon.com/s?k=usb+cable']);
  assert.deepEqual(await links(a, 'open github and search for voice assistant'), ['https://github.com/search?q=voice+assistant']);
  assert.deepEqual(await links(a, 'search for tips on python'), ['https://www.google.com/search?q=tips+on+python']);
  assert.deepEqual(await links(a, 'open youtube and open github'), ['https://www.youtube.com', 'https://github.com']);
  assert.match(await say(a, 'open my secret files'), /don't know the website/);
  assert.match(await say(a, 'open notepad'), /desktop version/);
  assert.match(await say(a, 'shut down'), /desktop version/);
});

test('whatsapp flow', async () => {
  const a = make();
  assert.equal(await say(a, 'add contact ali 0300 1234567'), 'Saved Ali with number +923001234567.');
  const r = await a.handle("send a message to ali saying Hello Ali, I'll be late");
  assert.deepEqual(r.links, ["https://wa.me/923001234567?text=Hello%20Ali%2C%20I'll%20be%20late"]);   // capital letters kept
  for (const phrase of ['send hi to ali on whatsapp', 'whatsapp ali hi', 'text ali hi', 'open whatsapp and send message to ali saying hi', 'send hi to ali', 'Ali ko hi bhejo'])
    assert.deepEqual(await links(a, phrase), ['https://wa.me/923001234567?text=hi'], phrase);
  assert.deepEqual(await links(a, 'message 0300 5551234 call me'), ['https://wa.me/923005551234?text=call%20me']);
  assert.match(await say(a, 'send message to bob saying hi'), /don't have a contact called bob/);
  assert.match(await say(a, 'send the report to my printer'), /don't know/);   // 'send X to Y' only for known people
  assert.match(await say(a, 'open whatsapp and send message to ali saying bring tea and biscuits'), /Opening WhatsApp/);
  assert.equal((await links(a, 'open whatsapp and send message to ali saying bring tea and biscuits'))[0], 'https://wa.me/923001234567?text=bring%20tea%20and%20biscuits');
});

test('whatsapp asks what to say, and can confirm first', async () => {
  const a = make();
  await say(a, 'add contact ali 0300 1234567');
  assert.equal(await say(a, 'send a whatsapp message to ali'), 'What should I say to Ali?');
  assert.ok(a.awaitingAnswer);
  assert.match(await say(a, 'How are you'), /^Send 'How are you' to Ali/);    // free speech is always checked first
  assert.deepEqual(await links(a, 'yes'), ['https://wa.me/923001234567?text=How%20are%20you']);
  await say(a, 'message ali');
  assert.equal(await say(a, 'cancel'), 'Okay, cancelled.');

  const c = make({ confirmMessages: true });
  await say(c, 'add contact ali 0300 1234567');
  assert.equal(await say(c, 'message ali hello'), "Send 'hello' to Ali on WhatsApp? Say yes to confirm.");
  assert.deepEqual(await links(c, 'no'), []);
  await say(c, 'message ali hello');
  assert.deepEqual(await links(c, 'what time is it'), []);                        // changing the subject drops the message
  assert.equal(c.awaitingAnswer, false);
});

test('contacts and email', async () => {
  const a = make();
  await say(a, 'add contact sara email sara at gmail dot com');
  await say(a, 'add contact ali 0300 1234567');
  assert.equal(await say(a, 'list contacts'), 'You have 2 contacts: Ali, Sara.');
  assert.equal(await say(a, "what's the email of sara"), "Sara's email is sara@gmail.com.");
  assert.equal(await say(a, 'delete contact ali'), 'Deleted the contact Ali.');
  assert.deepEqual(await links(a, 'send an email to sara about the Project report'),
    ['https://mail.google.com/mail/?view=cm&fs=1&to=sara%40gmail.com&su=the+Project+report&body=']);
  assert.match(await say(a, 'send email to bob'), /don't have an email address for bob/);
  assert.match(await say(a, 'add contact ali 12'), /doesn't look like a phone number/);
  assert.equal(a.contacts.find('sarah')[0], 'sara');                              // close spelling
});

test('timers, alarms, reminders', async () => {
  const a = make();
  const alerts = [];
  a.alertSink = (m) => alerts.push(m);
  assert.match(await say(a, 'set a timer for 5 minutes'), /timer set for 5 minutes/);
  assert.equal(a.scheduled[0].s, 300);
  a.scheduled[0].fn();
  assert.deepEqual(alerts, ["Time's up! Your timer for 5 minutes is done."]);
  assert.match(await say(a, 'set an alarm for 7 am'), /alarm set for 7:00 AM/);
  assert.equal(a.scheduled[1].s, 16 * 3600);
  assert.match(await say(a, 'remind me at 5 pm to Call Mom'), /remind you at 5:00 PM: Call Mom/);
  assert.match(await say(a, 'remind me to drink water in 10 minutes'), /in 10 minutes: drink water/);
  assert.match(await say(a, '5 minute ka timer lagao'), /timer set for 5 minutes/);
  assert.match(await say(a, 'set a timer for soon'), /How long/);
  assert.equal(await say(a, 'cancel my timers'), 'Cancelled 4 timers.');
  assert.ok(a.scheduled.slice(1).every((h) => h.cancelled));
});

test('notes', async () => {
  const a = make();
  await say(a, 'take a note Buy Milk');
  assert.equal(await say(a, 'read my notes'), 'You have 1 note: 1. Buy Milk');
  assert.equal(await say(a, 'delete note 1'), 'Deleted note 1: Buy Milk.');
  assert.equal(await say(a, 'read my notes'), 'You have no notes.');
});

test('maths, units, small talk, time', async () => {
  const a = make();
  assert.equal(await say(a, 'what is 12 times 7'), 'The answer is 84.');
  assert.equal(await say(a, 'convert 10 km to miles'), '10 km is 6.2137 miles.');
  assert.equal(await say(a, 'how many cm in 2 inches'), '2 inches is 5.08 cm.');
  assert.equal(await say(a, "what's the time"), "It's 3:00 PM.");
  assert.equal(await say(a, 'what is the date today'), 'Today is Thursday, 05 November 2026.');
  assert.equal(await say(a, 'say Hello There'), 'Hello There');
  assert.match(await say(a, 'flip a coin'), /heads|tails/);
  assert.match(await say(a, 'tell me a joke'), /./);
  assert.match(await say(a, 'blah blah'), /don't know how/);
});

test('translate, news, maps, spotify', async () => {
  const a = make();
  assert.deepEqual(await links(a, 'translate Good Morning to urdu'), ['https://translate.google.com/?sl=auto&tl=ur&text=Good+Morning&op=translate']);
  assert.match(await say(a, 'translate hello to klingon'), /don't know the language/);
  assert.deepEqual(await links(a, 'latest news about cricket'), ['https://news.google.com/search?q=cricket']);
  assert.deepEqual(await links(a, 'navigate to Islamabad Airport'), ['https://www.google.com/maps/dir/?api=1&destination=Islamabad+Airport']);
  assert.deepEqual(await links(a, 'find pharmacy near me'), ['https://www.google.com/maps/search/pharmacy+near+me']);
  assert.deepEqual(await links(a, 'play tum hi ho on spotify'), ['https://open.spotify.com/search/tum%20hi%20ho']);
  assert.deepEqual(await links(a, 'play lofi'), ['https://www.youtube.com/results?search_query=lofi']);
});

test('online lookups use the injected fetcher and fail gracefully', async () => {
  const calls = [];
  const fetchJson = async (url) => {
    calls.push(url);
    if (url.includes('geocoding')) return { results: [{ name: 'Karachi', latitude: 24.8, longitude: 67 }] };
    if (url.includes('open-meteo')) return { current: { temperature_2m: 31.4, weather_code: 0, wind_speed_10m: 12 } };
    if (url.includes('wikipedia')) return { type: 'standard', extract: 'Ada Lovelace was an English mathematician. She wrote the first program. More text here.' };
    if (url.includes('er-api')) return { result: 'success', rates: { PKR: 280 } };
    throw new Error('unexpected ' + url);
  };
  const a = make({ fetchJson });
  assert.equal(await say(a, 'weather in Karachi'), 'In Karachi it is 31 degrees Celsius with clear sky. Wind 12 kilometres per hour.');
  assert.equal(await say(a, 'who is ada lovelace'), 'Ada Lovelace was an English mathematician. She wrote the first program.');
  assert.equal(await say(a, 'convert 100 dollars to rupees'), '100 dollars is about 28,000.00 rupees.');
  assert.equal(await say(a, 'weather'), 'Which city?');
  assert.match(await say(a, 'karachi'), /In Karachi it is/);

  const offline = make({ fetchJson: async () => { throw new Error('offline'); } });
  const r = await offline.handle('weather in Karachi');
  assert.match(r.text, /Showing the weather/);
  assert.deepEqual(r.links, ['https://www.google.com/search?q=weather+Karachi']);
  assert.match(await say(offline, 'who is ada lovelace'), /couldn't find anything/);
  assert.match(await say(offline, '100 euros to rupees'), /showing it on Google/);
});

test('storage survives a new assistant (like a page reload)', async () => {
  const storage = new MemoryStorage();
  await say(new Assistant({ storage }), 'add contact ali 0300 1234567');
  assert.equal(await say(new Assistant({ storage }), 'list contacts'), 'You have 1 contact: Ali.');
  storage.setItem('va_contacts', '{broken');                                       // corrupt data must not crash anything
  assert.equal(await say(new Assistant({ storage }), 'list contacts'), 'You have no contacts yet. Say: add contact ali 0300 1234567.');
});
