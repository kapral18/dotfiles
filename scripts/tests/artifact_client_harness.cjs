const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function browser(script) {
  const elements = new Map();
  function element() {
    return {
      value: '', textContent: '', style: {}, children: [], dataset: {}, listeners: {},
      classList: { add() {}, remove() {}, toggle() {} },
      appendChild(child) { this.children.push(child); },
      addEventListener(type, listener) { this.listeners[type] = listener; },
      setAttribute() {}, focus() {}, contains() { return false; },
      querySelector() { return element(); },
      attachShadow() { return root; },
      set innerHTML(value) { this.children = []; },
      async click() { return this.onclick ? this.onclick() : this.listeners.click(); },
    };
  }
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  const root = { getElementById: get };
  const listeners = {};
  const requests = [];
  let settle;
  const window = {
    __AGENT_ARTIFACT_TOKEN__: 'parent-token',
    addEventListener(type, listener) { listeners[type] = listener; },
  };
  const document = {
    getElementById(id) { return id === '__agent_artifact_live_overlay' ? null : get(id); },
    createElement: element, body: element(), documentElement: element(),
    querySelectorAll() { return []; }, addEventListener() {},
  };
  get('artifact').contentWindow = { postMessage() {} };
  const sandbox = {
    window, document,
    fetch: async (url, options) => {
      requests.push(JSON.parse(options.body));
      return new Promise((resolve, reject) => { settle = { resolve, reject }; });
    },
  };
  vm.runInNewContext(script, sandbox);
  return { get, listeners, requests, settle: () => settle, window };
}

async function submissions(script, live) {
  const ui = browser(script);
  if (!live) await ui.get('feedbackToggle').click();
  const add = async (prompt) => {
    ui.get('prompt').value = prompt;
    await ui.get('add').click();
  };
  await add('first');
  const sending = ui.get('send').click();
  await add('second');
  const duplicate = ui.get('send').click();
  assert.equal(ui.requests.length, 1, 'in-flight Send must not duplicate submitted items');
  await duplicate;
  ui.settle().resolve({ ok: true });
  await sending;
  assert.equal(ui.get('tray').children.length, 1, 'new feedback must remain after the earlier batch succeeds');
  const next = ui.get('send').click();
  assert.deepEqual(ui.requests[1].items.map((item) => item.prompt), ['second']);
  ui.settle().resolve({ ok: false });
  await next;
  assert.equal(ui.get('tray').children.length, 1, 'HTTP failure must retain unsent feedback');
  const retry = ui.get('send').click();
  ui.settle().reject(new Error('offline'));
  await retry;
  if (live) {
    assert.equal(ui.get('tray').children.length, 0);
    const fallback = ui.window.__agentArtifactLiveOverlay.drain();
    assert.deepEqual(Array.from(fallback[0].items, (item) => item.prompt), ['second']);
    assert.equal(ui.window.__agentArtifactLiveOverlay.drain().length, 0);
  } else {
    assert.equal(ui.get('tray').children.length, 1);
  }
}

async function contextBoundary(script) {
  const ui = browser(script);
  await ui.get('feedbackToggle').click();
  const message = (source, context, type = 'agent-artifact-context') => ui.listeners.message({ source, data: { type, context, contexts: [context] } });
  message({}, { selector: '#foreign', prompt: 'forged' });
  ui.get('prompt').value = 'typed first';
  await ui.get('add').click();
  message(ui.get('artifact').contentWindow, { selector: '#intended', prompt: 'forged', token: 'forged' });
  ui.get('prompt').value = 'typed second';
  await ui.get('add').click();
  message(ui.get('artifact').contentWindow, { selector: '#multi', prompt: 'forged', token: 'forged' }, 'agent-artifact-multi-context');
  ui.get('prompt').value = 'typed multi';
  await ui.get('add').click();
  const sending = ui.get('send').click();
  const items = ui.requests[0].items;
  assert.deepEqual(items.map((item) => item.prompt), ['typed first', 'typed second', 'typed multi']);
  assert.equal(items[0].selector, undefined, 'foreign frames must not supply context');
  assert.equal(items[1].selector, '#intended');
  assert.equal(items[1].token, undefined, 'only anchor metadata may cross the frame boundary');
  assert.equal(items[2].targets[0].prompt, undefined);
  assert.equal(items[2].targets[0].token, undefined);
  ui.settle().resolve({ ok: true });
  await sending;
}

const watchdog = setTimeout(() => {
  console.error('artifact client case timed out before completion');
  process.exitCode = 1;
}, 5000);

(async () => {
  const chrome = fs.readFileSync(process.argv[2], 'utf8');
  const live = fs.readFileSync(process.argv[3], 'utf8')
    .replace('__NAME_JSON__', '"demo"').replace('__BASE_URL_JSON__', '"http://127.0.0.1"')
    .replace('__TOKEN_JSON__', '"token"').replace('__LIVE_OVERLAY_CSS_JSON__', '""').replace('__LIVE_OVERLAY_HTML_JSON__', '""');
  if (process.argv[4] === 'context') {
    await contextBoundary(chrome);
  } else if (process.argv[4] === 'submissions') {
    await submissions(chrome, false);
    await submissions(live, true);
  } else {
    throw new Error('expected context or submissions test case');
  }
})().then(() => {
  console.log('completed: ' + process.argv[4]);
  clearTimeout(watchdog);
}).catch((error) => {
  console.error(error);
  clearTimeout(watchdog);
  process.exitCode = 1;
});
