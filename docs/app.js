// Page code: chat UI, microphone, speech, timers. The commands themselves live in engine.js.
import { Assistant, MemoryStorage } from './engine.js';

const $ = (s) => document.querySelector(s);
const chat = $('#chat'), input = $('#input'), form = $('#form'), mic = $('#mic'), statusEl = $('#status');

// localStorage can throw (private windows, blocked cookies): fall back to memory so the page still works
let storage;
try { localStorage.setItem('va_test', '1'); localStorage.removeItem('va_test'); storage = localStorage; } catch { storage = new MemoryStorage(); }
const load = (k, d) => { try { return JSON.parse(storage.getItem(k)) ?? d; } catch { return d; } };
const settings = { countryCode: '92', speak: false, confirm: false, lang: 'en-US', ...load('va_settings', {}) };
const saveSettings = () => storage.setItem('va_settings', JSON.stringify(settings));

// ---- timers: compare against the clock every half second, so a sleeping laptop still fires late rather than never
const pending = new Set();
setInterval(() => { const now = Date.now(); for (const t of [...pending]) if (t.at <= now) { pending.delete(t); t.fn(); } }, 500);
const schedule = (seconds, fn) => { const t = { at: Date.now() + seconds * 1000, fn }; pending.add(t); return { cancel: () => pending.delete(t) }; };

const fetchJson = async (url) => {
  const r = await fetch(url, { signal: AbortSignal.timeout(6000) });
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
};
const status = async (kind) => {
  if (kind === 'internet') return navigator.onLine ? 'Yes, you are online.' : "No, I can't reach the internet right now.";
  if (kind === 'battery' && navigator.getBattery) {
    const b = await navigator.getBattery();
    return `The battery is at ${Math.round(b.level * 100)} percent and ${b.charging ? 'charging' : 'not charging'}.`;
  }
  return null;
};

const assistant = new Assistant({ storage, schedule, fetchJson, status, countryCode: settings.countryCode, confirmMessages: settings.confirm });

// ---- messages
function add(role, text, links = [], extra = '') {
  $('#welcome')?.remove();
  const div = document.createElement('div');
  div.className = `msg ${role} ${extra}`.trim();
  div.textContent = text;
  if (links.length) {
    const box = document.createElement('div');
    box.className = 'links';
    for (const url of links) {
      const a = document.createElement('a');
      a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer';
      a.textContent = '↗ ' + new URL(url).hostname.replace(/^www\./, '');
      box.append(a);
    }
    div.append(box);
  }
  chat.append(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function openLinks(links) {
  // Browsers only allow pop-ups right after a tap or key press. If one is blocked, the link chips under the message still work.
  if (!links.length) return;
  const w = window.open(links[0], '_blank');
  if (w) w.opener = null;
  else statusEl.textContent = 'Pop-up blocked: tap the link under the message';
}

let voice = null;
function speak(text) {
  if (!settings.speak || !('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = settings.lang;
  speechSynthesis.speak(u);
}

async function submit(text) {
  text = text.trim();
  if (!text) return;
  add('you', text);
  statusEl.textContent = 'Thinking…';
  let reply;
  try { reply = await assistant.handle(text); } catch (e) { reply = { text: 'Sorry, something went wrong with that command.', links: [] }; console.error(e); }
  add('bot', reply.text, reply.links);
  openLinks(reply.links);
  speak(reply.text);
  statusEl.textContent = assistant.awaitingAnswer ? 'Waiting for your answer…' : 'Type or tap the mic';
  input.placeholder = assistant.awaitingAnswer ? 'Your answer…' : 'Say or type a command…';
}

// ---- alerts from timers
function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.25, 0.5].forEach((d) => { const o = ctx.createOscillator(), g = ctx.createGain(); o.connect(g); g.connect(ctx.destination); o.frequency.value = 880; g.gain.value = 0.15; o.start(ctx.currentTime + d); o.stop(ctx.currentTime + d + 0.15); });
  } catch { /* no audio allowed */ }
}
assistant.alertSink = (message) => {
  add('bot', message, [], 'alert');
  beep();
  speak(message);
  if ('Notification' in window && Notification.permission === 'granted') new Notification('Voice Assistant', { body: message });
};
const askNotifications = () => { if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission(); };

// ---- form, chips, microphone
form.addEventListener('submit', (e) => { e.preventDefault(); const t = input.value; input.value = ''; if (/timer|alarm|remind|ka timer/i.test(t)) askNotifications(); submit(t); });
document.addEventListener('click', (e) => { const c = e.target.closest('.chip'); if (c) { if (/timer|alarm|remind/i.test(c.textContent)) askNotifications(); submit(c.textContent); } });

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SR) {
  mic.disabled = true;
  mic.title = 'Voice input needs Chrome, Edge or Safari. You can still type.';
} else {
  let rec = null;
  mic.addEventListener('click', () => {
    if (rec) { rec.stop(); return; }
    rec = new SR();
    rec.lang = settings.lang; rec.interimResults = true; rec.maxAlternatives = 1;
    rec.onstart = () => { mic.classList.add('live'); statusEl.textContent = 'Listening…'; };
    rec.onresult = (e) => {
      const r = e.results[e.results.length - 1];
      input.value = r[0].transcript;
      if (r.isFinal) { const t = input.value; input.value = ''; submit(t); }
    };
    rec.onerror = (e) => { statusEl.textContent = e.error === 'not-allowed' ? 'Microphone blocked. Allow it in the address bar.' : e.error === 'no-speech' ? "I didn't hear anything." : `Voice error: ${e.error}`; };
    rec.onend = () => { mic.classList.remove('live'); rec = null; if (statusEl.textContent === 'Listening…') statusEl.textContent = 'Type or tap the mic'; };
    rec.start();
  });
}

// ---- side panel: contacts, notes, settings
const drawer = $('#drawer'), body = $('#drawer-body');
const el = (tag, props = {}, ...kids) => { const n = Object.assign(document.createElement(tag), props); n.append(...kids); return n; };

function showPanel(name) {
  body.replaceChildren();
  $('#drawer-title').textContent = { contacts: 'Contacts', notes: 'Notes', settings: 'Settings' }[name];
  if (name === 'contacts') {
    const nameIn = el('input', { type: 'text', placeholder: 'Name' }), phoneIn = el('input', { type: 'text', placeholder: 'Phone, e.g. 0300 1234567' }), mailIn = el('input', { type: 'text', placeholder: 'Email (optional)' });
    const addBtn = el('button', { type: 'button', textContent: 'Save contact' });
    addBtn.onclick = async () => {
      const t = `add contact ${nameIn.value} ${mailIn.value ? 'email ' + mailIn.value : ''} ${phoneIn.value}`.replace(/\s+/g, ' ');
      const r = await assistant.handle(t); statusEl.textContent = r.text; showPanel('contacts');
    };
    body.append(el('div', { className: 'add' }, nameIn, phoneIn, mailIn, addBtn));
    const all = assistant.contacts.all();
    if (!Object.keys(all).length) body.append(el('p', { className: 'empty', textContent: 'No contacts yet. Saved only in this browser.' }));
    for (const [n, c] of Object.entries(all).sort()) {
      const del = el('button', { className: 'ghost del', textContent: 'Delete' });
      del.onclick = () => { assistant.contacts.remove(n); showPanel('contacts'); };
      body.append(el('div', { className: 'row' }, el('div', {}, n.replace(/\b\w/g, (x) => x.toUpperCase()), el('small', { textContent: [c.phone && '+' + c.phone, c.email].filter(Boolean).join(' · ') })), del));
    }
  } else if (name === 'notes') {
    const notes = assistant.notes.all();
    if (!notes.length) body.append(el('p', { className: 'empty', textContent: 'No notes. Say "take a note buy milk".' }));
    notes.forEach((n, i) => {
      const del = el('button', { className: 'ghost del', textContent: 'Delete' });
      del.onclick = () => { assistant.notes.remove(i + 1); showPanel('notes'); };
      body.append(el('div', { className: 'row' }, el('div', {}, n.text, el('small', { textContent: new Date(n.created).toLocaleString() })), del));
    });
  } else {
    const cc = el('input', { type: 'text', value: settings.countryCode, inputMode: 'numeric' });
    cc.onchange = () => { settings.countryCode = cc.value.replace(/\D/g, '') || '92'; assistant.contacts.countryCode = settings.countryCode; saveSettings(); };
    const lang = el('select', {}, ...[['en-US', 'English (US)'], ['en-IN', 'English (India) – best for Roman Urdu'], ['en-GB', 'English (UK)'], ['ur-PK', 'Urdu (script)']].map(([v, t]) => el('option', { value: v, textContent: t, selected: v === settings.lang })));
    lang.onchange = () => { settings.lang = lang.value; saveSettings(); };
    const check = (key, label, hint) => { const box = el('input', { type: 'checkbox', checked: settings[key] }); box.onchange = () => { settings[key] = box.checked; assistant.confirmMessages = settings.confirm; saveSettings(); if (key === 'speak' && !box.checked) speechSynthesis?.cancel(); }; return el('label', { className: 'check' }, box, el('span', {}, label, el('small', { textContent: hint }))); };
    body.append(
      el('div', { className: 'field' }, el('label', { textContent: 'Country code for numbers starting with 0' }), cc),
      el('div', { className: 'field' }, el('label', { textContent: 'Voice language' }), lang),
      check('speak', 'Speak the answers', 'Uses your browser’s voice.'),
      check('confirm', 'Ask before opening WhatsApp', 'WhatsApp always opens with the message typed in; you press Send there.'),
      el('p', { className: 'empty', textContent: 'Contacts and notes are stored only in this browser. Timers and alarms work while this tab stays open.' }),
    );
  }
  drawer.hidden = false;
}
document.querySelectorAll('nav [data-panel]').forEach((b) => b.addEventListener('click', () => showPanel(b.dataset.panel)));
$('#close-drawer').addEventListener('click', () => { drawer.hidden = true; });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') drawer.hidden = true; });
