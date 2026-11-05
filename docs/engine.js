// Command engine for the web version. Same ideas as the Python engine: a list of routes, each a pattern + handler.
// It never touches the page itself: links to open are collected in `reply.links`, so it is easy to test in Node.
import { SITES, SEARCH_URLS, ALIASES, UNITS, CURRENCIES, LANGUAGES, JOKES, QUOTES,
         URDU_RULES, URDU_CONJ, URDU_WA_PREFIX, URDU_HOURS, URDU_MINUTES } from './data.js';

const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const enc = encodeURIComponent;
const plus = (s) => enc(s).replace(/%20/g, '+');           // like Python's quote_plus
const pad = (n) => String(n).padStart(2, '0');

// ---------------------------------------------------------------- calculator (no eval)
const NUM_UNITS = Object.fromEntries('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(' ').map((w, i) => [w, i]));
const NUM_TENS = { twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90 };
const PHRASES = [[/\bto the power of\b/g, ' ** '], [/\braised to\b/g, ' ** '], [/\bmultiplied by\b/g, ' * '],
  [/\bdivided by\b/g, ' / '], [/\bplus\b/g, ' + '], [/\bminus\b/g, ' - '], [/\btimes\b/g, ' * '], [/\bover\b/g, ' / '],
  [/\bmod\b/g, ' % '], [/(?<=\d)\s*x\s*(?=\d)/g, ' * '], [/\^/g, ' ** ']];

export class CalcError extends Error {}

export function numberWords(text) {
  const tens = Object.keys(NUM_TENS).join('|');
  const ones = Object.keys(NUM_UNITS).filter((k) => NUM_UNITS[k] > 0 && NUM_UNITS[k] < 10).join('|');
  text = text.replace(new RegExp(`\\b(${tens})[ -](${ones})\\b`, 'g'), (_, t, u) => String(NUM_TENS[t] + NUM_UNITS[u]));
  for (const [word, value] of Object.entries({ ...NUM_UNITS, ...NUM_TENS })) text = text.replace(new RegExp(`\\b${word}\\b`, 'g'), String(value));
  return text;
}

function toExpression(text) {
  let expr = numberWords(text.toLowerCase().replace(/,/g, ''));
  for (const [pattern, repl] of PHRASES) expr = expr.replace(pattern, repl);
  return expr.replace(/\s+/g, ' ').trim();
}

export function calculate(text) {
  const expr = toExpression(text);
  if (!/\d/.test(expr) || !/[-+*/%]/.test(expr) || /[^\d\s.+\-*/%()]/.test(expr)) throw new CalcError('not a calculation');
  const tokens = expr.match(/\d+(?:\.\d+)?|\.\d+|\*\*|[-+*/%()]/g) || [];
  let i = 0;
  const bad = () => new CalcError("I couldn't understand that calculation");
  const peek = () => tokens[i];
  const check = (v) => {
    if (Math.abs(v) > 1e15) throw new CalcError('that number is too large');
    return v;
  };
  function expression() {
    let v = term();
    while (peek() === '+' || peek() === '-') v = check(tokens[i++] === '+' ? v + term() : v - term());
    return v;
  }
  function term() {
    let v = unary();
    while (peek() === '*' || peek() === '/' || peek() === '%') {
      const op = tokens[i++], r = unary();
      if ((op === '/' || op === '%') && r === 0) throw new CalcError("I can't divide by zero");
      v = check(op === '*' ? v * r : op === '/' ? v / r : ((v % r) + r) % r);
    }
    return v;
  }
  function unary() {
    if (peek() === '+') { i++; return unary(); }
    if (peek() === '-') { i++; return -unary(); }
    return power();
  }
  function power() {
    const base = atom();
    if (peek() === '**') {
      i++;
      const exponent = unary();
      if (Math.abs(exponent) > 100) throw new CalcError('that exponent is too large');
      return check(base ** exponent);
    }
    return base;
  }
  function atom() {
    const t = tokens[i++];
    if (t === undefined) throw bad();
    if (t === '(') {
      const v = expression();
      if (tokens[i++] !== ')') throw bad();
      return v;
    }
    if (/^[\d.]/.test(t)) return parseFloat(t);
    throw bad();
  }
  const value = expression();
  if (i !== tokens.length) throw bad();
  return Math.round(value * 1e6) / 1e6;
}

export function formatNumber(v) {
  if (Number.isInteger(v)) return v.toLocaleString('en-US');
  return String(Number(v.toPrecision(6)));
}

// ---------------------------------------------------------------- timers
const DURATION = /(?:\b(an?)\b|(\d+(?:\.\d+)?))\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b/;
const UNIT_SECONDS = { s: 1, m: 60, h: 3600 };
export const MAX_SECONDS = 24 * 3600;

export function parseDuration(text) {
  const m = DURATION.exec(numberWords(text.toLowerCase()));
  if (!m) return null;
  return (m[1] ? 1 : parseFloat(m[2])) * UNIT_SECONDS[m[3][0]];
}

const CLOCK = /\b(?:at |for )?(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?(?![\d:])/;
export function parseClockTime(text, now) {
  text = numberWords(text.toLowerCase().trim());
  const m = CLOCK.exec(text);
  if (!m) return null;
  let hour = parseInt(m[1], 10);
  const minute = parseInt(m[2] || '0', 10);
  const meridiem = (m[3] || '').replace(/\./g, '');
  if (!meridiem && !m[2]) return null;
  if (meridiem) {
    if (hour < 1 || hour > 12) return null;
    hour = (hour % 12) + (meridiem === 'pm' ? 12 : 0);
  }
  if (hour > 23 || minute > 59) return null;
  const target = new Date(now);
  target.setHours(hour, minute, 0, 0);
  if (target <= now) target.setDate(target.getDate() + 1);
  return [(target - now) / 1000, target];
}

export function formatDuration(seconds) {
  seconds = Math.round(seconds);
  for (const [unit, size] of [['hour', 3600], ['minute', 60], ['second', 1]]) {
    if (seconds >= size && (seconds % size === 0 || size === 1)) {
      const n = Math.floor(seconds / size);
      return `${n} ${unit}${n === 1 ? '' : 's'}`;
    }
  }
  return `${seconds} seconds`;
}

export const clockLabel = (d) => `${d.getHours() % 12 || 12}:${pad(d.getMinutes())} ${d.getHours() < 12 ? 'AM' : 'PM'}`;
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

// ---------------------------------------------------------------- sites
const compact = (s) => s.toLowerCase().replace(/[^a-z0-9]/g, '');

function lookup(table, name) {
  name = name.trim().toLowerCase();
  const keys = [compact(name), ...(ALIASES[name] ? [compact(ALIASES[name])] : [])];
  for (const key of keys) for (const [known, value] of Object.entries(table)) if (compact(known) === key) return value;
  return null;
}
export function findSite(name, custom = {}) {
  if (!name.trim()) return null;
  return lookup(custom, name) || lookup(SITES, name);
}
export function searchUrl(site, query, custom = {}) {
  let template = null;
  const own = lookup(custom, site);
  if (own && own.includes('{q}')) template = own;
  template = template || lookup(SEARCH_URLS, site);
  return template ? template.replace('{q}', plus(query)) : null;
}

// ---------------------------------------------------------------- conversion
const TEMP = { celsius: 'c', centigrade: 'c', c: 'c', fahrenheit: 'f', f: 'f', kelvin: 'k', k: 'k' };
const TEMP_NAMES = { c: 'degrees Celsius', f: 'degrees Fahrenheit', k: 'kelvin' };
const NUMBER = '-?\\d+(?:\\.\\d+)?';
const FORWARD = new RegExp(`^(?:convert |what(?:'s| is) )?(${NUMBER})\\s*([a-z\\/ ]+?)\\s+(?:to|in|into|equals? in|is how many)\\s+([a-z\\/ ]+)$`);
const HOW_MANY = new RegExp(`^how (?:many|much) ([a-z\\/ ]+?) (?:are |is |do i get )?(?:in|from) (${NUMBER})\\s*([a-z\\/ ]+)$`);

export function parseConversion(command) {
  const text = numberWords(command.toLowerCase().replace(/,/g, ''));
  let m = FORWARD.exec(text);
  if (m) return [parseFloat(m[1]), m[2].trim(), m[3].trim()];
  m = HOW_MANY.exec(text);
  if (m) return [parseFloat(m[2]), m[3].trim(), m[1].trim()];
  return null;
}
export function convertUnits(amount, src, dst) {
  if (TEMP[src] && TEMP[dst]) {
    const a = TEMP[src], b = TEMP[dst];
    const c = { c: amount, f: ((amount - 32) * 5) / 9, k: amount - 273.15 }[a];
    return [{ c, f: (c * 9) / 5 + 32, k: c + 273.15 }[b], TEMP_NAMES[a], TEMP_NAMES[b]];
  }
  const s = UNITS[src], d = UNITS[dst];
  if (!s || !d || s[0] !== d[0]) return null;
  return [(amount * s[1]) / d[1], src, dst];
}
const currencyCode = (name) => CURRENCIES[name.trim().toLowerCase()] || null;

// ---------------------------------------------------------------- phone numbers and messages
const DIGIT_WORDS = { zero: '0', oh: '0', one: '1', two: '2', three: '3', four: '4', five: '5', six: '6', seven: '7', eight: '8', nine: '9' };
const REPEAT = { double: 2, triple: 3 };
const EMAIL = /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/;
const EMAIL_FULL = /^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$/;
const FILLER = new Set(['phone', 'number', 'no', 'mobile', 'cell', 'whatsapp', 'is', 'with', 'at', 'contact', 'has', 'its']);

export function spokenToDigits(text) {
  const out = [];
  let repeat = 1;
  for (const token of text.toLowerCase().split(/\s+/).filter(Boolean)) {
    if (REPEAT[token]) repeat = REPEAT[token];
    else if (DIGIT_WORDS[token] !== undefined) { out.push(DIGIT_WORDS[token].repeat(repeat)); repeat = 1; }
    else if (token === 'plus') out.push('+');
    else { repeat = 1; out.push(token); }
  }
  return out.join(' ');
}

export function normalizePhone(raw, countryCode = '92') {
  const text = spokenToDigits(raw).trim();
  if (!/^\+?[\d\s().-]+$/.test(text)) return null;
  const digits = text.replace(/\D/g, '');
  if (!digits) return null;
  let number;
  if (text.startsWith('+')) number = digits;
  else if (digits.startsWith('00')) number = digits.slice(2);
  else if (digits.startsWith('0')) number = countryCode + digits.slice(1);
  else if (digits.length <= 10 && countryCode) number = countryCode + digits;
  else number = digits;
  return number.length >= 8 && number.length <= 15 ? number : null;
}
const digitish = (t) => /^\+?[\d-]+$/.test(t) || DIGIT_WORDS[t] !== undefined || REPEAT[t] !== undefined || t === 'plus';

const SEPARATOR = /\s*(?:\bsaying(?: that)?\b|\bsay\b|\bthat says\b|\bwith (?:the )?message\b|\bmessage is\b|\bmessage\b|\btelling (?:him|her|them)(?: that)?\b|\bto tell (?:him|her|them)(?: that)?\b)\s+|\s*:\s*/i;

export function splitRecipientAndText(rest, knownNames = []) {
  rest = rest.trim();
  const m = SEPARATOR.exec(rest);
  if (m && rest.slice(0, m.index).trim()) return [rest.slice(0, m.index).trim(), rest.slice(m.index + m[0].length).trim()];
  const tokens = rest.split(/\s+/).filter(Boolean);
  let i = 0;
  while (i < tokens.length && digitish(tokens[i])) i++;
  if (i && spokenToDigits(tokens.slice(0, i).join(' ')).replace(/\D/g, '').length >= 7) return [tokens.slice(0, i).join(' '), tokens.slice(i).join(' ')];
  const lowered = rest.toLowerCase();
  for (const name of [...knownNames].sort((a, b) => b.length - a.length)) {
    if (lowered === name || lowered.startsWith(name + ' ')) return [rest.slice(0, name.length), rest.slice(name.length).trim()];
  }
  if (!tokens.length) return ['', ''];
  return [tokens[0], tokens.slice(1).join(' ')];
}

export function parseContactDetails(text) {
  text = text.trim();
  let email = null;
  const m = /\b(?:e-?mail|mail)(?: address)?(?: is)?\s+(.+)$/.exec(text);
  if (m) {
    const spoken = ' ' + m[1] + ' ';
    const candidate = spoken.replace(/ at the rate /g, '@').replace(/ at /g, '@').replace(/ dot /g, '.').replace(/\s+/g, '');
    if (EMAIL_FULL.test(candidate)) email = candidate;
    text = text.slice(0, m.index).trim();
  }
  const inline = EMAIL.exec(text);
  if (inline) {
    email = inline[0];
    text = (text.slice(0, inline.index) + ' ' + text.slice(inline.index + inline[0].length)).trim();
  }
  const tokens = text.split(/\s+/).filter(Boolean);
  let j = tokens.length;
  while (j > 0 && digitish(tokens[j - 1])) j--;
  const phone = tokens.slice(j).join(' ') || null;
  const nameTokens = tokens.slice(0, j);
  while (nameTokens.length && FILLER.has(nameTokens[nameTokens.length - 1])) nameTokens.pop();
  return [nameTokens.join(' ').trim(), phone, email];
}

const whatsappUrl = (phone, text) => `https://wa.me/${phone}?text=${enc(text)}`;
const gmailUrl = (to = '', subject = '', body = '') => `https://mail.google.com/mail/?view=cm&fs=1&to=${plus(to)}&su=${plus(subject)}&body=${plus(body)}`;

// ---------------------------------------------------------------- storage (localStorage in the browser)
export class MemoryStorage {
  constructor() { this.d = {}; }
  getItem(k) { return k in this.d ? this.d[k] : null; }
  setItem(k, v) { this.d[k] = String(v); }
}

function readJson(storage, key, fallback) {
  try { const v = JSON.parse(storage.getItem(key)); return v ?? fallback; } catch { return fallback; }
}

// Ratcliff/Obershelp similarity, the same measure Python's difflib uses (so spelling guesses behave alike)
function ratio(a, b) {
  const matches = (x, y) => {
    let best = [0, 0, 0];
    for (let i = 0; i < x.length; i++) for (let j = 0; j < y.length; j++) {
      let k = 0;
      while (i + k < x.length && j + k < y.length && x[i + k] === y[j + k]) k++;
      if (k > best[2]) best = [i, j, k];
    }
    const [i, j, k] = best;
    if (!k) return 0;
    return k + matches(x.slice(0, i), y.slice(0, j)) + matches(x.slice(i + k), y.slice(j + k));
  };
  return a.length + b.length ? (2 * matches(a, b)) / (a.length + b.length) : 1;
}

export class ContactStore {
  constructor(storage, countryCode = '92') { this.storage = storage; this.countryCode = countryCode; }
  all() { const d = readJson(this.storage, 'va_contacts', {}); return d && typeof d === 'object' && !Array.isArray(d) ? d : {}; }
  save(d) { this.storage.setItem('va_contacts', JSON.stringify(d)); }
  names() { return Object.keys(this.all()).sort(); }
  add(name, phone, email) {
    const d = this.all(), key = name.trim().toLowerCase();
    const entry = d[key] || {};
    if (phone) entry.phone = phone;
    if (email) entry.email = email;
    d[key] = entry;
    this.save(d);
  }
  remove(name) {
    const found = this.find(name);
    if (!found) return null;
    const d = this.all();
    delete d[found[0]];
    this.save(d);
    return found[0];
  }
  find(name) {
    const key = name.trim().toLowerCase();
    if (!key) return null;
    const d = this.all();
    if (d[key]) return [key, d[key]];
    const starts = Object.keys(d).filter((n) => n.startsWith(key) || key.startsWith(n));
    if (starts.length === 1) return [starts[0], d[starts[0]]];
    let best = null, bestScore = 0.75;
    for (const n of Object.keys(d)) { const r = ratio(key, n); if (r >= bestScore) { best = n; bestScore = r; } }
    return best ? [best, d[best]] : null;
  }
}

export class NoteStore {
  constructor(storage) { this.storage = storage; }
  all() { const d = readJson(this.storage, 'va_notes', []); return Array.isArray(d) ? d : []; }
  save(d) { this.storage.setItem('va_notes', JSON.stringify(d)); }
  add(text, now) { const d = this.all(); d.push({ text, created: now.toISOString() }); this.save(d); }
  clear() { const n = this.all().length; this.save([]); return n; }
  remove(number) { const d = this.all(); if (number < 1 || number > d.length) return null; const [r] = d.splice(number - 1, 1); this.save(d); return r.text; }
}

// ---------------------------------------------------------------- roman urdu
const URDU = URDU_RULES.map(([p, t]) => [new RegExp(p), t]);
const URDU_CONJ_RE = new RegExp(URDU_CONJ);
const URDU_WA_RE = new RegExp(URDU_WA_PREFIX);
function urduRewrite(command) {
  for (const [pattern, template] of URDU) {
    if (pattern.test(command)) {
      const result = command.replace(pattern, template);
      return /timer|remind/.test(result) ? result.replace(new RegExp(URDU_HOURS, 'g'), 'hours').replace(new RegExp(URDU_MINUTES, 'g'), 'minutes') : result;
    }
  }
  return command;
}
export function toEnglish(command) {
  command = command.replace(URDU_WA_RE, '');
  const parts = command.split(URDU_CONJ_RE);
  if (parts.length > 1) {
    const rewritten = parts.map(urduRewrite);
    if (rewritten.every((n, i) => n !== parts[i]) && !rewritten.some((r) => r.startsWith('send '))) return rewritten.join(' and ');
  }
  return urduRewrite(command);
}

// ---------------------------------------------------------------- misc text helpers
export const normalize = (text) => text.toLowerCase().trim().replace(/[?!.,;]+$/, '').replace(/\s+/g, ' ');
const POLITE = /^(?:(?:please|can you|could you|would you|will you)\s+)+/;
export const stripPoliteness = (c) => c.replace(POLITE, '').replace(/\s+please$/, '');

const CONJUNCTION = /\s+(?:and then|and also|then|and)\s+(?=(?:open|search|play|go to|launch|visit|start|set|turn|show|read|type|send|message|whatsapp|flip|roll|convert|email|navigate|translate|what|tell|remind)\b)/;
const UNSPLITTABLE = /^(?:open whats ?app(?: and| then)? )?(?:send|message|msg|text|whats ?app|email|e-mail|type|dictate|say|translate|remind|(?:take|add|make|write|save)(?: a| me a| new)? (?:note|contact)|note\b|set (?:a |an )?(?:timer|alarm))|^open .+? and (?:search|look up|find)\b/;
export function splitCompound(command) {
  if (UNSPLITTABLE.test(command)) return [command];
  const parts = command.split(CONJUNCTION).filter((p) => p.trim());
  return parts.length ? parts : [command];
}

const YES = new Set(['yes', 'yeah', 'yep', 'sure', 'confirm', 'do it', 'go ahead', 'yes do it', 'send it', 'send', 'yes send it', 'haan', 'ji', 'ji haan']);
const NO = new Set(['no', 'nope', 'cancel', 'never mind', 'nevermind', "don't", 'stop', 'nahi', 'nahin', 'ruko']);
const DOMAIN = /^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$/;
const DESKTOP_ONLY = 'That needs the desktop version (the Python app for Windows). In the browser I can open websites, message people on WhatsApp, search, convert, set alarms and more. Say "help" to see everything.';
const WEATHER_CODES = { 0: 'clear sky', 1: 'mostly clear', 2: 'partly cloudy', 3: 'overcast', 45: 'foggy', 48: 'foggy', 51: 'light drizzle', 53: 'drizzle', 55: 'heavy drizzle',
  61: 'light rain', 63: 'rain', 65: 'heavy rain', 71: 'light snow', 73: 'snow', 75: 'heavy snow', 80: 'rain showers', 81: 'rain showers', 82: 'heavy rain showers', 95: 'a thunderstorm', 96: 'a thunderstorm with hail', 99: 'a thunderstorm with hail' };

export const HELP = 'I can tell the time and date, open websites ("open youtube", "open claude"), search the web or one site ("search amazon for headphones"), ' +
  'send WhatsApp messages ("send a message to Ali saying I\'ll be late") and emails, keep a contact book ("add contact Ali 0300 1234567"), ' +
  'translate ("translate good morning to urdu"), convert units and currency ("convert 10 km to miles", "100 dollars to rupees"), ' +
  'give directions, tell the weather, do maths, take notes, set timers, alarms and reminders ("remind me at 5 pm to call mom"), ' +
  'look things up ("who is Ada Lovelace"), tell a joke or a quote. You can also type in Roman Urdu, like "youtube kholo".';

export class Assistant {
  constructor({ now = () => new Date(), storage = new MemoryStorage(), schedule = () => ({ cancel() {} }), fetchJson = null,
    rng = Math.random, status = async () => null, countryCode = '92', confirmMessages = false, customSites = {} } = {}) {
    this.now = now; this.rng = rng; this.schedule = schedule; this.fetchJson = fetchJson; this.status = status;
    this.confirmMessages = confirmMessages; this.customSites = customSites;
    this.contacts = new ContactStore(storage, countryCode);
    this.notes = new NoteStore(storage);
    this.raw = ''; this.links = []; this.followup = null; this.timers = [];
    this.alertSink = null; this.alerts = [];
    this.routes = this.buildRoutes();
  }

  get awaitingAnswer() { return this.followup !== null; }
  open(url) { this.links.push(url); }
  restore(text) {
    if (!text) return text;
    const found = [...this.raw.matchAll(new RegExp('(?<!\\w)' + esc(text) + '(?!\\w)', 'gi'))];
    return found.length ? found[found.length - 1][0] : text;
  }
  say(text) { return { text }; }
  pick(list) { return list[Math.floor(this.rng() * list.length)]; }

  async handle(text) {
    this.raw = text.trim().replace(/\s+/g, ' ');
    this.links = [];
    const command = stripPoliteness(normalize(text));
    if (!command) return { text: "I didn't catch that.", links: [] };
    if (this.followup) {
      const f = this.followup;
      this.followup = null;
      const reply = await f(command);
      if (reply) return { ...reply, links: this.links };
    }
    const texts = [];
    for (const part of splitCompound(toEnglish(command))) {
      texts.push((await this.handleOne(part)).text);
      if (this.followup) break;
    }
    return { text: texts.join(' '), links: this.links };
  }

  async handleOne(command) {
    for (const [pattern, handler] of this.routes) {
      const m = pattern.exec(command);
      if (m) {
        const reply = await handler(m);
        if (reply) return reply;
      }
    }
    const reply = (await this.convert(command)) || this.maths(command) || (await this.knowledge(command));
    return reply || this.say("Sorry, I don't know how to do that yet. Say 'help' to hear what I can do.");
  }

  popAlerts() { const a = this.alerts; this.alerts = []; return a; }

  buildRoutes() {
    const desktop = () => this.say(DESKTOP_ONLY);
    const R = (re, fn) => [re, fn];
    return [
      R(/^(?:cancel|stop|clear|delete)(?: all| my)? (?:timers?|reminders?|alarms?)$/, () => this.cancelTimers()),
      R(/^(?:shut ?down|power off|restart|reboot|lock|log ?off|log out|sign out|sleep)(?: the| my)?(?: computer| pc| laptop| system| windows| screen)?$|^(?:turn )?(?:the )?volume (?:up|down)$|^(?:set )?(?:the )?volume |^(?:un)?mute\b|^(?:set )?(?:the )?(?:screen )?brightness|^(?:take a )?screenshot$|^(?:refresh|go back|new tab|close tab|scroll (?:up|down)|zoom (?:in|out)|copy|paste)$|^(?:type|dictate)[: ]|^open (?:my |the )?(?:downloads|documents|desktop|pictures|music|videos)(?: folder)?$|^close (?:notepad|chrome|calculator|word|excel|vlc|spotify|discord)$/, desktop),
      R(/^(?:exit|quit|stop|goodbye|good bye|bye)\b/, () => this.say("Goodbye! I'll be here when you need me.")),
      R(/^(?:help|what can you do)\b/, () => this.say(HELP)),
      R(/^(?:take|add|make|write|save)(?: a| me a)? note(?: that| to)?[: ]*(.+)$/, (m) => this.addNote(m)),
      R(/^note[: ]+(.+)$/, (m) => this.addNote(m)),
      R(/^(?:read|show|list|what are)(?: me)?(?: my| all)? notes$/, () => this.readNotes()),
      R(/^(?:clear|delete|erase)(?: all)?(?: my)? notes$/, () => this.say(`Deleted ${this.countNotes()}.`)),
      R(/^(?:delete|remove|erase) note (.+)$/, (m) => this.deleteNote(m)),
      // contacts and messages
      R(/^(?:add|save|create)(?: a| new)?(?: new)? contact (.+)$/, (m) => this.addContact(m)),
      R(/^(?:list|show|read)(?: me)?(?: my| all)? contacts$/, () => this.listContacts()),
      R(/^(?:delete|remove|erase) (?:the )?contact (.+)$/, (m) => this.deleteContact(m)),
      R(/^(?:what(?:'s| is)|show|tell me)(?: me)?(?: the)?(?: phone| mobile)? (number|e-?mail|mail)(?: address)? (?:of|for) (.+)$/, (m) => this.contactInfo(m)),
      R(/^send (?:an? )?(?:whats ?app )?(?:message |msg |text )?(.+?) to (.+?) (?:on|via|in|using|through) whats ?app$/, (m) => this.whatsappTextFirst(m)),
      R(/^(?:open whats ?app(?: and| then)? )?(?:send|write|drop|shoot)(?: an?)?(?: whats ?app)?(?: message| msg| text)?(?: (?:on|via|in|using|through) whats ?app)? to (.+)$/, (m) => this.whatsappTo(m)),
      R(/^(?:open whats ?app(?: and| then)? )?(?:whats ?app|message|msg|text) (.+)$/, (m) => this.whatsappTo(m)),
      R(/^(?:send|write|compose|draft)(?: an?)? (?:e-?mail|mail)(?: to (.+?))?(?: (saying|about|regarding|with subject|subject) (.+))?$/, (m) => this.emailTo(m[1], m[2], m[3])),
      R(/^e-?mail (.+?)(?: (saying|about|regarding|with subject|subject) (.+))?$/, (m) => this.emailTo(m[1], m[2], m[3])),
      R(/^send (.+?) to (.+)$/, (m) => this.sendKnown(m)),
      // timers, alarms, reminders
      R(/^(?:set (?:a |an )?)?(?:timer|alarm) (?:for|of|at) (.+)$|^wake me(?: up)? at (.+)$/, (m) => this.timer(m)),
      R(/^remind me (?:in|at) (.+?) to (.+)$/, (m) => this.reminder(m[2], m[1])),
      R(/^remind me to (.+?) (?:in|at) (.+)$/, (m) => this.reminder(m[1], m[2])),
      R(/^(?:(?:what(?:'s| is)|how(?:'s| is)) the )?weather(?: like)?(?:(?: in| for| at| of)? (.+))?$/, (m) => this.weather(m)),
      R(/^(?:(?:what(?:'s| is)|check|show|tell me|how(?:'s| is))(?: me)?(?: the| my)? )?battery(?: percentage| level| status| life| charge)?$|^how much battery(?: is)?(?: left| remaining)?(?: do i have)?$/, () => this.systemStatus('battery')),
      R(/^(?:am i|are we) (?:online|connected)(?: to the internet)?$|^(?:check )?(?:my |the )?(?:internet|wi-?fi)(?: connection| status)?$|^is (?:the )?internet (?:working|on|connected)$/, () => this.systemStatus('internet')),
      R(/^(?:hello|hi|hey|salam|assalam[a-z ]*)\b/, () => this.say('Hello! How can I help you?')),
      R(/^(?:what(?:'s| is) your name|who are you)$/, () => this.say("I'm your voice assistant, written in Python and JavaScript.")),
      // the web
      R(/^translate (.+?) (?:to|into|in) ([a-z]+)$|^how (?:do you|do i|to) say (.+?) in ([a-z]+)$/, (m) => this.translate(m)),
      R(/^(?:(?:open|show|get|give|read|tell) (?:me )?)?(?:the )?(?:latest |top |breaking |today's )?(?:news|headlines)(?: (?:about|on|for|of) (.+))?$/, (m) => this.news(m)),
      R(/^(?:navigate|get directions|give me directions|directions|take me)(?: to)? (.+)$/, (m) => this.directions(m)),
      R(/^(?:find|show|search for|look for)(?: me)? (.+?) (?:near me|nearby|near by|around me)$/, (m) => this.maps(`${m[1]} near me`)),
      R(/^(?:where(?:'s| is)|locate) (.+)$|^(?:show|find)(?: me)? (.+?) on (?:the |google )?maps?$/, (m) => this.maps(m[1] || m[2])),
      R(/^play (.+?) on spotify$/, (m) => this.go(`https://open.spotify.com/search/${enc(m[1].trim())}`, `Searching Spotify for ${m[1].trim()}.`)),
      R(/^play (.+?)(?: on youtube)?$/, (m) => this.go(`https://www.youtube.com/results?search_query=${plus(m[1].trim())}`, `Showing YouTube results for ${m[1].trim()}. Pick a video to play.`)),
      R(/^(?:search youtube for|youtube) (.+)$/, (m) => this.go(`https://www.youtube.com/results?search_query=${plus(m[1].trim())}`, `Searching YouTube for ${m[1].trim()}.`)),
      R(/^open (.+?) and (?:search|look up|find)(?: for)? (.+)$/, (m) => this.searchOn(m[2], m[1])),
      R(/^(?:search|find|look up|look for)(?: for)? (.+?) (?:on|in|at|using|from) (.+)$/, (m) => this.searchOn(m[1], m[2])),
      R(/^(?:search|find|look up) (.+?) for (.+)$/, (m) => this.searchOn(m[2], m[1])),
      R(/^(?:search for|search|google|look up) (.+)$/, (m) => this.go(`https://www.google.com/search?q=${plus(m[1].trim())}`, `Searching the web for ${m[1].trim()}.`)),
      R(/^(?:open|go to|launch|visit|start|run) (.+)$/, (m) => this.openTarget(m)),
      // small talk
      R(/^say (.+)$/, (m) => this.say(this.restore(m[1]))),
      R(/^(?:tell me |give me )?(?:a |an )?(?:quote|motivational quote|inspirational quote|some motivation)$|^(?:motivate|inspire) me$/, () => this.say(this.pick(QUOTES))),
      R(/^(?:flip|toss) a coin$/, () => this.say(`It's ${this.pick(['heads', 'tails'])}.`)),
      R(/^roll a (?:dice|die)$/, () => this.say(`You rolled a ${1 + Math.floor(this.rng() * 6)}.`)),
      R(/\bjoke\b/, () => this.say(this.pick(JOKES))),
      R(/\btime\b/, () => { const d = this.now(); return this.say(`It's ${clockLabel(d)}.`); }),
      R(/\b(?:date|today|day is it)\b/, () => { const d = this.now(); return this.say(`Today is ${DAYS[d.getDay()]}, ${pad(d.getDate())} ${MONTHS[d.getMonth()]} ${d.getFullYear()}.`); }),
    ];
  }

  go(url, text) { this.open(url); return this.say(text); }

  // ---- notes
  addNote(m) {
    const text = this.restore(m[1].trim());
    if (!text) return this.say('What should I write in the note?');
    this.notes.add(text, this.now());
    return this.say(`Okay, I saved your note: ${text}.`);
  }
  readNotes() {
    const notes = this.notes.all();
    if (!notes.length) return this.say('You have no notes.');
    return this.say(`You have ${notes.length} note${notes.length !== 1 ? 's' : ''}: ` + notes.map((n, i) => `${i + 1}. ${n.text}`).join('; '));
  }
  countNotes() { const n = this.notes.clear(); return `${n} note${n !== 1 ? 's' : ''}`; }
  deleteNote(m) {
    const number = parseInt(numberWords(m[1].trim()), 10);
    if (Number.isNaN(number)) return this.say('Which note number should I delete?');
    const removed = this.notes.remove(number);
    return this.say(removed === null ? `I can't find note ${number}.` : `Deleted note ${number}: ${removed}.`);
  }

  // ---- contacts
  addContact(m) {
    const [name, phoneWords, email] = parseContactDetails(m[1]);
    if (!name) return this.say('Whose contact should I save? For example: add contact ali 0300 1234567.');
    let phone = null;
    if (phoneWords) {
      phone = normalizePhone(phoneWords, this.contacts.countryCode);
      if (!phone) return this.say("That doesn't look like a phone number. Try something like 0300 1234567.");
    }
    if (!phone && !email) return this.say(`What is ${name}'s phone number? Say: add contact ${name} 0300 1234567.`);
    this.contacts.add(name, phone, email);
    const saved = [phone ? `number +${phone}` : '', email ? `email ${email}` : ''].filter(Boolean).join(' and ');
    return this.say(`Saved ${title(name)} with ${saved}.`);
  }
  listContacts() {
    const names = this.contacts.names();
    if (!names.length) return this.say('You have no contacts yet. Say: add contact ali 0300 1234567.');
    return this.say(`You have ${names.length} contact${names.length !== 1 ? 's' : ''}: ${names.map(title).join(', ')}.`);
  }
  deleteContact(m) {
    const removed = this.contacts.remove(m[1].trim());
    return this.say(removed ? `Deleted the contact ${title(removed)}.` : `I can't find a contact called ${m[1].trim()}.`);
  }
  contactInfo(m) {
    const found = this.contacts.find(m[2].trim());
    if (!found) return this.say(`I can't find a contact called ${m[2].trim()}.`);
    const [name, entry] = found;
    if (m[1] === 'number') return this.say(entry.phone ? `${title(name)}'s number is +${entry.phone}.` : `${title(name)} has no number saved.`);
    return this.say(entry.email ? `${title(name)}'s email is ${entry.email}.` : `${title(name)} has no email saved.`);
  }

  // ---- messages
  resolveRecipient(who) {
    who = who.trim();
    if (!who) return this.say('Who should I send it to?');
    const phone = normalizePhone(who, this.contacts.countryCode);
    if (phone) return [`+${phone}`, phone];
    const found = this.contacts.find(who);
    if (found) {
      const [name, entry] = found;
      if (entry.phone) return [title(name), entry.phone];
      return this.say(`${title(name)} has no phone number saved. Say: add contact ${name} 0300 1234567.`);
    }
    return this.say(`I don't have a contact called ${who}. Say: add contact ${who} 0300 1234567, or say the phone number.`);
  }
  whatsappTo(m) {
    const rest = m[1].trim().replace(/\s+(?:on|via|in|using|through) whats ?app$/, '');
    if (rest === 'web' || rest === 'app') return this.go('https://web.whatsapp.com', 'Opening WhatsApp Web.');
    const [who, text] = splitRecipientAndText(rest, this.contacts.names());
    return this.messageFlow(who, text);
  }
  whatsappTextFirst(m) {
    let text = m[1].trim();
    if (['message', 'msg', 'text', 'a message', 'whatsapp', 'whatsapp message'].includes(text)) text = '';
    return this.messageFlow(m[2].trim(), text);
  }
  sendKnown(m) {
    const who = m[2].trim();
    if (!(normalizePhone(who, this.contacts.countryCode) || this.contacts.find(who))) return null;
    return this.messageFlow(who, m[1].trim());
  }
  messageFlow(who, text) {
    const target = this.resolveRecipient(who);
    if (!Array.isArray(target)) return target;
    const [name, phone] = target;
    if (!text) {
      this.followup = (command) => (NO.has(command) ? this.say('Okay, cancelled.') : this.confirmOrSend(name, phone, this.restore(command), true));
      return this.say(`What should I say to ${name}?`);
    }
    return this.confirmOrSend(name, phone, this.restore(text));
  }
  confirmOrSend(name, phone, text, force = false) {
    if (!(this.confirmMessages || force)) return this.sendWhatsapp(name, phone, text);
    this.followup = (command) => {
      if (YES.has(command)) return this.sendWhatsapp(name, phone, text);
      if (NO.has(command)) return this.say("Okay, I won't send it.");
      return null;
    };
    return this.say(`Send '${text}' to ${name} on WhatsApp? Say yes to confirm.`);
  }
  sendWhatsapp(name, phone, text) {
    this.open(whatsappUrl(phone, text));
    return this.say(`Opening WhatsApp with your message to ${name}. Press Send in WhatsApp to deliver it.`);
  }
  emailTo(who, connector, text) {
    let to = '';
    if (who) {
      who = who.trim();
      const found = this.contacts.find(who);
      if (EMAIL_FULL.test(who)) to = who;
      else if (found && found[1].email) to = found[1].email;
      else return this.say(`I don't have an email address for ${who}. Say: add contact ${who} email ${who} at gmail dot com.`);
    }
    text = text ? this.restore(text.trim()) : '';
    const isSubject = ['about', 'regarding', 'with subject', 'subject'].includes(connector);
    this.open(gmailUrl(to, isSubject ? text : '', isSubject ? '' : text));
    return this.say('Opening a new email' + (to ? ` to ${to}` : '') + '. Check it and press send.');
  }

  // ---- timers (they only run while this page stays open)
  alert(message) { if (this.alertSink) this.alertSink(message); else this.alerts.push(message); }
  scheduleAlert(seconds, message) {
    const holder = {};
    holder.handle = this.schedule(seconds, () => {
      this.timers = this.timers.filter((h) => h !== holder.handle);
      this.alert(message);
    });
    this.timers.push(holder.handle);
  }
  timer(m) {
    const text = (m[1] || m[2]).trim();
    const seconds = parseDuration(text);
    if (seconds === null) {
      const clock = parseClockTime(text, this.now());
      if (clock) {
        const label = clockLabel(clock[1]);
        this.scheduleAlert(clock[0], `Alarm! It's ${label}.`);
        return this.say(`Okay, alarm set for ${label}. Keep this tab open.`);
      }
      return this.say('How long should the timer be? For example, set a timer for 5 minutes, or set an alarm for 7 am.');
    }
    if (!(seconds > 0 && seconds <= MAX_SECONDS)) return this.say('Please choose a time between 1 second and 24 hours.');
    const length = formatDuration(seconds);
    this.scheduleAlert(seconds, `Time's up! Your timer for ${length} is done.`);
    return this.say(`Okay, timer set for ${length}. Keep this tab open.`);
  }
  reminder(task, when) {
    task = this.restore(task.trim());
    let seconds = parseDuration(when);
    if (seconds === null) {
      const clock = parseClockTime(when, this.now());
      if (clock) {
        const label = clockLabel(clock[1]);
        this.scheduleAlert(clock[0], `Reminder: ${task}.`);
        return this.say(`Okay, I'll remind you at ${label}: ${task}. Keep this tab open.`);
      }
    }
    if (seconds === null || !(seconds > 0 && seconds <= MAX_SECONDS)) return this.say('Please give a time between 1 second and 24 hours, for example in 10 minutes or at 5 pm.');
    this.scheduleAlert(seconds, `Reminder: ${task}.`);
    return this.say(`Okay, I'll remind you in ${formatDuration(seconds)}: ${task}. Keep this tab open.`);
  }
  cancelTimers() {
    const n = this.timers.length;
    this.timers.forEach((h) => h.cancel());
    this.timers = [];
    return this.say(n ? `Cancelled ${n} timer${n !== 1 ? 's' : ''}.` : 'You have no active timers.');
  }

  // ---- the web
  async weather(m) {
    const place = this.restore((m[1] || '').trim());
    if (!place) {
      this.followup = (command) => (NO.has(command) ? this.say('Okay.') : this.weather([null, command]));
      return this.say('Which city?');
    }
    if (this.fetchJson) {
      try {
        const geo = await this.fetchJson(`https://geocoding-api.open-meteo.com/v1/search?name=${enc(place)}&count=1`);
        const hit = geo.results && geo.results[0];
        if (hit) {
          const w = (await this.fetchJson(`https://api.open-meteo.com/v1/forecast?latitude=${hit.latitude}&longitude=${hit.longitude}&current=temperature_2m,weather_code,wind_speed_10m`)).current;
          const sky = WEATHER_CODES[w.weather_code] || 'unsettled weather';
          return this.say(`In ${hit.name} it is ${Math.round(w.temperature_2m)} degrees Celsius with ${sky}. Wind ${Math.round(w.wind_speed_10m)} kilometres per hour.`);
        }
      } catch { /* offline: fall through to Google */ }
    }
    return this.go(`https://www.google.com/search?q=${plus('weather ' + place)}`, `Showing the weather for ${place}.`);
  }
  async systemStatus(kind) {
    const text = await this.status(kind);
    return this.say(text || "Sorry, your browser doesn't let me read that.");
  }
  translate(m) {
    const [text, language] = m[1] ? [m[1], m[2]] : [m[3], m[4]];
    const code = LANGUAGES[language];
    if (!code) return this.say(`I don't know the language ${language}. Try urdu, hindi, arabic, french, spanish or german.`);
    const t = this.restore(text.trim());
    return this.go(`https://translate.google.com/?sl=auto&tl=${code}&text=${plus(t)}&op=translate`, `Translating '${t}' to ${title(language)}.`);
  }
  news(m) {
    const topic = (m[1] || '').trim();
    return this.go(topic ? `https://news.google.com/search?q=${plus(topic)}` : 'https://news.google.com', topic ? `Showing the news about ${topic}.` : 'Showing the latest news.');
  }
  directions(m) {
    const place = this.restore(m[1].trim());
    return this.go(`https://www.google.com/maps/dir/?api=1&destination=${plus(place)}`, `Getting directions to ${place}.`);
  }
  maps(place) {
    place = this.restore(place.trim());
    return this.go(`https://www.google.com/maps/search/${plus(place)}`, `Showing ${place} on the map.`);
  }
  async knowledge(command) {
    const m = /^(?:tell me about|who is|who was|who are|what is|what are|what was|define|explain)\s+(?:an? |the )?(.+)$/.exec(command);
    if (!m) return null;
    const topic = m[1].trim();
    if (this.fetchJson) {
      for (const name of new Set([title(topic), topic.charAt(0).toUpperCase() + topic.slice(1)])) {
        try {
          const data = await this.fetchJson(`https://en.wikipedia.org/api/rest_v1/page/summary/${enc(name.replace(/ /g, '_'))}`);
          if (data.type === 'standard' && data.extract) {
            const short = data.extract.trim().split(/(?<=[.!?])\s+/).slice(0, 2).join(' ');
            return this.say(short.length <= 350 ? short : short.slice(0, 350).replace(/\s+\S*$/, '') + '...');
          }
        } catch { /* try the next spelling */ }
      }
    }
    return this.say(`Sorry, I couldn't find anything about ${topic}.`);
  }
  searchOn(query, site) {
    const url = searchUrl(site.trim(), query.trim(), this.customSites);
    if (!url) return null;
    return this.go(url, `Searching ${site.trim()} for ${query.trim()}.`);
  }
  openTarget(m) {
    const target = m[1].trim();
    const names = target.split(/\s*,\s*|\s+and\s+/).filter(Boolean);
    if (names.length > 1 && names.every((n) => findSite(n, this.customSites))) return this.say(names.map((n) => this.openOne(n).text).join(' '));
    return this.openOne(target);
  }
  openOne(target) {
    const site = findSite(target, this.customSites);
    if (site) { this.open(site); return this.say(`Opening ${target}.`); }
    if (/^https?:\/\/\S+$/.test(target)) { this.open(target); return this.say('Opening the link.'); }
    const domain = target.replace(/ dot /g, '.').replace(/ /g, '');
    if (DOMAIN.test(domain)) { this.open(`https://${domain}`); return this.say(`Opening ${domain}.`); }
    if (['notepad', 'calculator', 'calc', 'paint', 'word', 'excel', 'powerpoint', 'task manager', 'file explorer', 'vs code', 'vscode'].includes(target)) return this.say(DESKTOP_ONLY);
    return this.say(`I don't know the website ${target}. Try a name like youtube, claude or github, or a domain like example.com.`);
  }

  // ---- numbers
  async convert(command) {
    const parsed = parseConversion(command);
    if (!parsed) return null;
    const [amount, src, dst] = parsed;
    const result = convertUnits(amount, src, dst);
    if (result) return this.say(`${formatNumber(amount)} ${result[1]} is ${formatNumber(Math.round(result[0] * 1e4) / 1e4)} ${result[2]}.`);
    const a = currencyCode(src), b = currencyCode(dst);
    if (!(a && b)) return null;
    try {
      const data = this.fetchJson ? await this.fetchJson(`https://open.er-api.com/v6/latest/${a}`) : null;
      const rate = data && data.result === 'success' ? data.rates[b] : null;
      if (rate) return this.say(`${formatNumber(amount)} ${src} is about ${(amount * rate).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${dst}.`);
    } catch { /* offline */ }
    this.open(`https://www.google.com/search?q=${plus(`${formatNumber(amount)} ${a} to ${b}`)}`);
    return this.say("I couldn't get the live rate, so I'm showing it on Google.");
  }
  maths(command) {
    const expression = command.replace(/^(?:calculate|compute|solve|what is|what's|how much is)\s+/, '');
    try {
      return this.say(`The answer is ${formatNumber(calculate(expression))}.`);
    } catch (e) {
      if (!(e instanceof CalcError)) throw e;
      return e.message === 'not a calculation' ? null : this.say(`Sorry, ${e.message}.`);
    }
  }
}

const title = (s) => s.replace(/\b\w/g, (c) => c.toUpperCase());
