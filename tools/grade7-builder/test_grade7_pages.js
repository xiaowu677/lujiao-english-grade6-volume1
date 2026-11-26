const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..', '..');
const fullCounts = [58, 55, 49, 64, 57, 52, 35];
const coreCounts = [50, 51, 49, 63, 44, 52, 35];

function pageNames() {
  return Array.from({ length: 7 }, (_, index) => {
    const unit = index + 1;
    return [`g7-v1-unit${unit}`, `g7-v1-unit${unit}-core`];
  }).flat();
}

function extractCore(html) {
  const source = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
    .map((match) => match[1])
    .find((script) => script.includes('const WORDS ='));
  const context = { console, window: {} };
  vm.createContext(context);
  vm.runInContext(`${source}\nthis.core = window.WordQuestCore;`, context);
  return context.core;
}

function readPage(name) {
  return fs.readFileSync(
    path.join(root, 'outputs', name, 'index.html'),
    'utf8',
  );
}

test('grade 7 has the expected full and core word counts', () => {
  for (let index = 0; index < 7; index += 1) {
    const unit = index + 1;
    const full = extractCore(readPage(`g7-v1-unit${unit}`));
    const core = extractCore(readPage(`g7-v1-unit${unit}-core`));
    assert.equal(full.WORDS.length, fullCounts[index]);
    assert.equal(core.WORDS.length, coreCounts[index]);
    assert.ok(core.WORDS.every((word) => full.WORDS.some((item) => item.en === word.en)));
  }
});

test('core pages exclude every capitalized proper-name entry', () => {
  for (let unit = 1; unit <= 7; unit += 1) {
    const full = extractCore(readPage(`g7-v1-unit${unit}`)).WORDS;
    const core = new Set(
      extractCore(readPage(`g7-v1-unit${unit}-core`)).WORDS.map(
        (word) => word.en,
      ),
    );
    for (const word of full) {
      const proper = word.en
        .split(/\s+/)
        .some((token) => /^[A-Z]/.test(token.replace(/[.,!?()[\]’]/g, '')));
      assert.equal(core.has(word.en), !proper, `${word.en}: wrong core state`);
    }
  }
});

test('every grade 7 page has four complete context scenes', () => {
  for (const name of pageNames()) {
    const core = extractCore(readPage(name));
    assert.equal(core.CONTEXT_SCENES.length, 4, `${name}: scene count`);
    const sceneWords = core.CONTEXT_SCENES.flatMap((scene) => scene.wordEns);
    assert.equal(sceneWords.length, core.WORDS.length, `${name}: coverage`);
    assert.deepEqual(
      new Set(sceneWords),
      new Set(core.WORDS.map((word) => word.en)),
      `${name}: scene words`,
    );
  }
});

test('grade 7 pages use fixed Sonia audio and grade 7 return links', () => {
  const progressKeys = new Set();
  for (const name of pageNames()) {
    const html = readPage(name);
    assert.match(html, /const FIXED_AUDIO_ENABLED = true;/);
    assert.match(html, /assets\/audio\/g7-v1\/en-GB-SoniaNeural\//);
    assert.match(html, /href="\.\.\/\.\.\/grade7\/"/);
    const key = html.match(/const PROGRESS_KEY = '([^']+)'/)[1];
    assert.ok(!progressKeys.has(key), `${name}: duplicate progress key`);
    progressKeys.add(key);
  }
  assert.equal(progressKeys.size, 14);
});

test('grade 7 audio manifest contains 1138 valid files', () => {
  const audioDir = path.join(
    root,
    'outputs',
    'assets',
    'audio',
    'g7-v1',
    'en-GB-SoniaNeural',
  );
  const manifest = JSON.parse(
    fs.readFileSync(path.join(audioDir, 'manifest.json'), 'utf8'),
  );
  assert.equal(manifest.voice, 'en-GB-SoniaNeural');
  assert.equal(manifest.count, 1138);
  assert.equal(manifest.items.length, 1138);
  for (const item of manifest.items) {
    const file = path.join(audioDir, item.file);
    assert.ok(fs.existsSync(file), `missing ${item.file}`);
    assert.ok(fs.statSync(file).size > 500, `invalid ${item.file}`);
  }
});

test('grade 7 landing links all 14 pages and back to grade 6', () => {
  const html = fs.readFileSync(path.join(root, 'grade7', 'index.html'), 'utf8');
  assert.equal(
    [...html.matchAll(/href="\.\.\/outputs\/g7-v1-unit[1-7]\/index\.html"/g)]
      .length,
    7,
  );
  assert.equal(
    [...html.matchAll(/href="\.\.\/outputs\/g7-v1-unit[1-7]-core\/index\.html"/g)]
      .length,
    7,
  );
  assert.match(html, /href="\.\.\/"/);
});

test('grade 6 landing links to grade 7', () => {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  assert.match(html, /href="grade7\/"/);
});

test('Pages workflow publishes grade 7 pages and audio', () => {
  const workflow = fs.readFileSync(
    path.join(root, '.github', 'workflows', 'pages.yml'),
    'utf8',
  );
  assert.match(workflow, /outputs\/g7-v1-\*/);
  assert.match(workflow, /outputs\/assets\/audio\/g7-v1/);
  assert.match(workflow, /-eq 1138/);
});
