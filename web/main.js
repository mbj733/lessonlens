import * as THREE from './vendor/three.module.js';
import { applyLang, lang, t } from './i18n.js';

const SCENE_ROOT = '../eval/scenes/';
const DPR_CAP = 1.5;

const dom = {
  canvas: document.getElementById('view'),
  loading: document.getElementById('loading'),
  deckSelect: document.getElementById('deck-select'),
  langToggle: document.getElementById('lang-toggle'),
  hudDeck: document.getElementById('hud-deck'),
  hudCount: document.getElementById('hud-count'),
  detail: document.getElementById('detail'),
  detailTitle: document.getElementById('detail-title'),
  detailMeta: document.getElementById('detail-meta'),
  detailQuote: document.getElementById('detail-quote'),
  detailClaim: document.getElementById('detail-claim'),
  taskList: document.getElementById('task-list'),
};

const state = {
  data: null,
  meshes: new Map(),
  selected: null,
  answers: {},
  orderAttempts: {},
  camera: null,
  controls: { radius: 14, theta: 0, phi: 0.92, target: new THREE.Vector3(0, 0.8, 0) },
};

const renderer = new THREE.WebGLRenderer({ canvas: dom.canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, DPR_CAP));

const scene = new THREE.Scene();
scene.background = new THREE.Color('#0d1117');
scene.fog = new THREE.Fog('#0d1117', 22, 44);

const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 200);
state.camera = camera;

scene.add(new THREE.HemisphereLight('#cfe3ff', '#0b1117', 1.1));
const key = new THREE.DirectionalLight('#ffffff', 1.6);
key.position.set(6, 12, 8);
scene.add(key);
const rim = new THREE.DirectionalLight('#58a6ff', 0.5);
rim.position.set(-8, 4, -6);
scene.add(rim);

const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(60, 60),
  new THREE.MeshStandardMaterial({ color: '#0f151c', roughness: 0.95, metalness: 0 }),
);
floor.rotation.x = -Math.PI / 2;
scene.add(floor);
const grid = new THREE.GridHelper(40, 40, '#1f2a36', '#161d26');
grid.position.y = 0.001;
scene.add(grid);

// ------------------------------------------------------------------ geometry

function geometryFor(primitive) {
  switch (primitive) {
    case 'sphere':
      return new THREE.SphereGeometry(0.62, 28, 18);
    case 'cylinder':
      return new THREE.CylinderGeometry(0.55, 0.55, 1, 28);
    case 'cone':
      return new THREE.ConeGeometry(0.6, 1, 28);
    case 'plane':
      return new THREE.PlaneGeometry(1.4, 1.4);
    default:
      return new THREE.BoxGeometry(1, 1, 1);
  }
}

function buildObjects(data) {
  for (const obj of data.objects) {
    const mesh = new THREE.Mesh(
      geometryFor(obj.primitive),
      new THREE.MeshStandardMaterial({
        color: new THREE.Color(obj.color),
        roughness: 0.5,
        metalness: 0.05,
        emissive: new THREE.Color('#000000'),
        side: obj.primitive === 'plane' ? THREE.DoubleSide : THREE.FrontSide,
      }),
    );
    mesh.position.set(obj.position[0], obj.position[1], obj.position[2]);
    mesh.scale.set(obj.scale[0], obj.scale[1], obj.scale[2]);
    mesh.userData.objectId = obj.id;
    mesh.userData.baseColor = new THREE.Color(obj.color);
    scene.add(mesh);
    state.meshes.set(obj.id, mesh);

    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.72, 0.8, 32),
      new THREE.MeshBasicMaterial({ color: '#58a6ff', transparent: true, opacity: 0.35, side: THREE.DoubleSide }),
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(obj.position[0], 0.02, obj.position[2]);
    ring.visible = false;
    mesh.userData.ring = ring;
    scene.add(ring);
  }
}

// ------------------------------------------------------------------ camera

function applyCamera() {
  const { radius, theta, phi, target } = state.controls;
  const x = target.x + radius * Math.sin(phi) * Math.sin(theta);
  const y = target.y + radius * Math.cos(phi);
  const z = target.z + radius * Math.sin(phi) * Math.cos(theta);
  camera.position.set(x, y, z);
  camera.lookAt(target);
}

function resize() {
  const rect = dom.canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

// ------------------------------------------------------------------ picking

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

function pointerToNdc(event) {
  const rect = dom.canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
}

function pickAt(clientX, clientY) {
  pointerToNdc({ clientX, clientY });
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects([...state.meshes.values()], false);
  return hits.length ? hits[0].object.userData.objectId : null;
}

function screenPosition(objectId) {
  const mesh = state.meshes.get(objectId);
  if (!mesh) return null;
  const rect = dom.canvas.getBoundingClientRect();
  const world = new THREE.Vector3();
  mesh.getWorldPosition(world);
  world.y += mesh.scale.y * 0.3;
  const projected = world.clone().project(camera);
  return {
    x: rect.left + ((projected.x + 1) / 2) * rect.width,
    y: rect.top + ((1 - projected.y) / 2) * rect.height,
    visible: projected.z > -1 && projected.z < 1,
  };
}

// ------------------------------------------------------------------ sidebar

function objectById(id) {
  return state.data?.objects.find((obj) => obj.id === id) ?? null;
}

function select(objectId) {
  const obj = objectById(objectId);
  if (!obj) return null;
  state.selected = objectId;

  for (const [id, mesh] of state.meshes) {
    const on = id === objectId;
    mesh.material.emissive.set(on ? '#2f5f9e' : '#000000');
    mesh.userData.ring.visible = on;
  }

  dom.detail.classList.remove('empty');
  dom.detailTitle.textContent = obj.label;
  dom.detailMeta.textContent = `${t('page')} ${obj.page} · ${t(`kind${obj.kind[0].toUpperCase()}${obj.kind.slice(1)}`)} · ${obj.primitive}`;
  dom.detailQuote.textContent = obj.claims[0].quote;
  dom.detailClaim.textContent = obj.claims[0].text === obj.claims[0].quote ? '' : obj.claims[0].text;
  document.dispatchEvent(new CustomEvent('lessonlens:select', { detail: obj }));
  return obj;
}

function clearSelection() {
  state.selected = null;
  for (const mesh of state.meshes.values()) {
    mesh.material.emissive.set('#000000');
    mesh.userData.ring.visible = false;
  }
  dom.detail.classList.add('empty');
  dom.detailTitle.textContent = '';
  dom.detailMeta.textContent = '';
  dom.detailQuote.textContent = '';
  dom.detailClaim.textContent = '';
}

// ------------------------------------------------------------------ tasks

function optionsFor(task, index) {
  const answers = new Set(task.answers);
  const distractors = state.data.objects
    .map((obj) => obj.id)
    .filter((id) => !answers.has(id))
    .slice(0, Math.max(1, 3 - task.answers.length));
  const options = [...task.answers, ...distractors];
  const shift = index % options.length;
  return [...options.slice(shift), ...options.slice(0, shift)];
}

function labelFor(id) {
  const obj = objectById(id);
  if (!obj) return id;
  const short = obj.label.length > 34 ? `${obj.label.slice(0, 33)}…` : obj.label;
  return `${id.toUpperCase()} · ${short}`;
}

function renderTasks() {
  dom.taskList.textContent = '';
  state.data.tasks.forEach((task, index) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'task';
    wrapper.dataset.taskId = task.id;

    const prompt = document.createElement('p');
    prompt.textContent = task.prompt;
    wrapper.append(prompt);

    const options = document.createElement('div');
    options.className = 'options';
    for (const id of optionsFor(task, index)) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'option';
      button.dataset.objectId = id;
      button.textContent = labelFor(id);
      button.addEventListener('click', () => answer(task, id, button));
      options.append(button);
    }
    wrapper.append(options);

    const feedback = document.createElement('p');
    feedback.className = 'feedback';
    feedback.dataset.role = 'feedback';
    wrapper.append(feedback);

    dom.taskList.append(wrapper);
  });
}

function markSolved(wrapper, message) {
  wrapper.classList.add('done');
  const feedback = wrapper.querySelector('[data-role="feedback"]');
  feedback.className = 'feedback ok';
  feedback.textContent = `${t('correct')} — ${message}`;
  document.dispatchEvent(new CustomEvent('lessonlens:task-solved', { detail: wrapper.dataset.taskId }));
}

function answer(task, objectId, button) {
  const wrapper = button.closest('.task');
  const feedback = wrapper.querySelector('[data-role="feedback"]');

  if (task.kind === 'order') {
    const attempt = (state.orderAttempts[task.id] ??= []);
    attempt.push(objectId);
    button.classList.add('correct');
    if (attempt.length === task.answers.length) {
      const ok = attempt.every((id, index) => id === task.answers[index]);
      state.answers[task.id] = ok;
      if (ok) markSolved(wrapper, task.explanation);
      else {
        feedback.className = 'feedback bad';
        feedback.textContent = `${t('wrong')} — ${task.explanation}`;
        state.orderAttempts[task.id] = [];
        for (const node of wrapper.querySelectorAll('.option')) node.classList.remove('correct');
      }
    }
    return;
  }

  const ok = task.answers.includes(objectId);
  state.answers[task.id] = ok;
  if (ok) {
    button.classList.add('correct');
    markSolved(wrapper, task.explanation);
  } else {
    button.classList.add('wrong');
    feedback.className = 'feedback bad';
    feedback.textContent = `${t('wrong')} — ${task.explanation}`;
  }
}

// ------------------------------------------------------------------ interaction

let dragging = false;
let moved = 0;
let last = { x: 0, y: 0 };

dom.canvas.addEventListener('pointerdown', (event) => {
  dragging = true;
  moved = 0;
  last = { x: event.clientX, y: event.clientY };
  dom.canvas.setPointerCapture(event.pointerId);
});

dom.canvas.addEventListener('pointermove', (event) => {
  if (dragging) {
    const dx = event.clientX - last.x;
    const dy = event.clientY - last.y;
    moved += Math.abs(dx) + Math.abs(dy);
    state.controls.theta -= dx * 0.006;
    state.controls.phi = Math.min(1.35, Math.max(0.35, state.controls.phi - dy * 0.005));
    last = { x: event.clientX, y: event.clientY };
    applyCamera();
    return;
  }
  const hovered = pickAt(event.clientX, event.clientY);
  dom.canvas.style.cursor = hovered ? 'pointer' : 'grab';
});

dom.canvas.addEventListener('pointerup', (event) => {
  dragging = false;
  if (moved < 6) {
    const hit = pickAt(event.clientX, event.clientY);
    if (hit) select(hit);
    else clearSelection();
  }
});

dom.canvas.addEventListener('wheel', (event) => {
  event.preventDefault();
  state.controls.radius = Math.min(30, Math.max(6, state.controls.radius + event.deltaY * 0.01));
  applyCamera();
}, { passive: false });

window.addEventListener('resize', () => {
  resize();
});

dom.langToggle.addEventListener('click', () => {
  applyLang(lang() === 'en' ? 'zh' : 'en');
  if (state.selected) select(state.selected);
  renderTasks();
});

document.addEventListener('lessonlens:lang', () => {
  dom.hudCount.textContent = `${state.data?.objects.length ?? 0} ${t('objects')}`;
});

dom.deckSelect.addEventListener('change', () => {
  const url = new URL(window.location.href);
  url.searchParams.set('scene', dom.deckSelect.value);
  window.location.href = url.toString();
});

// ------------------------------------------------------------------ boot

async function loadIndex() {
  try {
    const response = await fetch(`${SCENE_ROOT}index.json`, { cache: 'no-store' });
    if (!response.ok) throw new Error(response.statusText);
    const payload = await response.json();
    return payload.scenes ?? [];
  } catch {
    return [];
  }
}

function resolveSceneFile(file) {
  if (!file) return null;
  if (file.startsWith('http') || file.startsWith('/')) return file;
  return file.includes('/') ? file : `${SCENE_ROOT}${file}`;
}

async function loadScene(file) {
  const url = resolveSceneFile(file);
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`cannot load ${url}: ${response.status}`);
  return response.json();
}

function fillDeckSelect(decks, current) {
  dom.deckSelect.textContent = '';
  for (const deck of decks) {
    const option = document.createElement('option');
    option.value = deck.file;
    option.textContent = `${deck.title} · ${deck.lang.toUpperCase()}`;
    option.selected = deck.file === current;
    dom.deckSelect.append(option);
  }
  if (!decks.length) dom.deckSelect.disabled = true;
}

async function boot() {
  const params = new URLSearchParams(window.location.search);
  const decks = await loadIndex();
  const wanted = params.get('scene') ?? decks[0]?.file ?? null;
  if (!wanted) {
    dom.loading.textContent = 'No scene found. Run `python -m lessonlens build eval/slides`.';
    return;
  }
  fillDeckSelect(decks, wanted);

  const data = await loadScene(wanted);
  state.data = data;
  buildObjects(data);
  resize();
  applyCamera();
  clearSelection();
  renderTasks();

  dom.hudDeck.textContent = `${data.deck.title} · ${data.deck.pages}p`;
  dom.hudCount.textContent = `${data.objects.length} ${t('objects')}`;
  document.title = `LessonLens — ${data.deck.title}`;
  dom.loading.classList.add('hidden');

  renderer.setAnimationLoop(() => {
    if (state.firstFrameMs === undefined) {
      state.firstFrameMs = performance.now();
      performance.mark('lessonlens:first-frame');
    }
    for (const mesh of state.meshes.values()) {
      if (mesh.userData.objectId === state.selected) {
        mesh.rotation.y += 0.004;
      }
    }
    renderer.render(scene, camera);
  });

  window.__lessonlens.ready = true;
  document.dispatchEvent(new CustomEvent('lessonlens:ready', { detail: data.deck.id }));
}

// Test / automation surface: deterministic, no synthetic clicks required.
window.__lessonlens = {
  ready: false,
  get scene() { return state.data; },
  get selected() { return state.selected; },
  get answers() { return state.answers; },
  get firstFrameMs() { return state.firstFrameMs ?? null; },
  select,
  clearSelection,
  screenPosition,
  pickAt,
  answerTask(taskId, objectId) {
    const task = state.data.tasks.find((item) => item.id === taskId);
    const wrapper = dom.taskList.querySelector(`[data-task-id="${taskId}"]`);
    const button = wrapper?.querySelector(`.option[data-object-id="${objectId}"]`);
    if (!task || !button) return false;
    answer(task, objectId, button);
    return true;
  },
  setLang: (code) => applyLang(code),
};

boot().catch((error) => {
  console.error(error);
  dom.loading.textContent = `Failed to load: ${error.message}`;
});
