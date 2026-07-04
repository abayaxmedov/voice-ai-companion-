// Realistik 3D avatar — Unclaw-darajali taqdimot, to'liq Three.js (Unreal'siz).
// Ready Player Me GLB + to'liq ARKit blendshape to'plami:
//  - lab-sinxron: backend viseme timeline (fonema-aniq), amplitudaga fallback;
//  - jonlilik: nigoh saccade'lari, asimmetrik ko'z qisish, gapirganda bosh
//    ta'kidlari, ko'krakda ko'rinadigan nafas;
//  - yoritish: iliq key + sovuq fill + orqadan qizil rim, ACES, yumshoq soya;
//  - kadr: ko'krakdan yuqori, kamera biroz pastdan, qora-qizil radial fon;
//  - kayfiyat: LLM mood → yuz ifodasi (300ms silliq o'tish).
// GLB yuklanmasa 2D placeholder (avatar.js) ishlayveradi.

import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

const DEFAULT_AVATAR_URL =
  "https://models.readyplayer.me/64bfa15f0e72c63d7c3934a6.glb?morphTargets=ARKit&textureAtlas=1024";
const API_BASE =
  (window.companion && window.companion.orchestratorUrl) ||
  (location.protocol.startsWith("http") ? location.origin : "http://127.0.0.1:8765");
// Ba'zi tarmoqlarda models.readyplayer.me ochilmaydi — kaskad:
// localStorage → lokal backend (assets/avatars/*.glb) → RPM → jsdelivr namuna.
const FALLBACK_URLS = [
  API_BASE + "/avatar/model",
  DEFAULT_AVATAR_URL,
  // RPM'da yaratilgan namuna (to'liq ARKit + viseme morphlar), TalkingHead
  // loyihasidan; litsenziya CC BY-NC 4.0 (nokommersial). jsdelivr orqali —
  // models.readyplayer.me yopiq tarmoqlarda ham ochiladi.
  "https://cdn.jsdelivr.net/gh/met4citizen/TalkingHead@master/avatars/brunette.glb",
];
const CANDIDATE_TIMEOUT_MS = 9000;
const LOCAL_TIMEOUT_MS = 4000; // lokal backend uchun qisqa
const MIN_ARKIT_MORPHS = 30; // to'liq ARKit to'plami uchun minimal chegara
const FAIL_MEMORY_MS = 6 * 60 * 60 * 1000; // yiqilgan manbani 6 soat chetlab o'tish

const container = document.getElementById("avatar3d-container");
const fallbackCanvas = document.getElementById("avatar-canvas");

/* ============================== Sozlamalar ============================== */

const CONFIG = {
  camera: { fov: 25, back: 1.08, belowEye: 0.2, lookBelowEye: 0.065 },
  moodBlendMs: 300,
  breath: { idleHz: 0.22, speakHz: 0.28, chest: 0.022, shoulder: 0.016 },
  maxPixelRatio: 2,
};

// Viseme → ARKit blendshape kombinatsiyalari.
// Unlilar: mouthFunnel/mouthPucker + jawOpen; undoshlar: mouthClose/mouthPress.
const VISEME_SHAPES = {
  sil: [],
  PP: [ // b p m — lablar yopiq
    ["mouthClose", 0.85], ["mouthPressLeft", 0.55], ["mouthPressRight", 0.55],
    ["jawOpen", 0.05], ["mouthRollLower", 0.25], ["mouthRollUpper", 0.2],
  ],
  FF: [ // f v — tish labda
    ["mouthPressLeft", 0.35], ["mouthPressRight", 0.35], ["jawOpen", 0.09],
    ["mouthShrugUpper", 0.2], ["mouthRollLower", 0.45], ["mouthLowerDownLeft", 0.12],
    ["mouthLowerDownRight", 0.12],
  ],
  DD: [ // t d — til tishda
    ["jawOpen", 0.18], ["mouthShrugUpper", 0.25], ["mouthStretchLeft", 0.1],
    ["mouthStretchRight", 0.1], ["mouthPressLeft", 0.12], ["mouthPressRight", 0.12],
  ],
  kk: [ // k g q x h ng
    ["jawOpen", 0.22], ["mouthShrugUpper", 0.1], ["mouthStretchLeft", 0.06],
    ["mouthStretchRight", 0.06],
  ],
  CH: [ // sh ch j — lablar oldinga
    ["jawOpen", 0.16], ["mouthFunnel", 0.45], ["mouthPucker", 0.28],
    ["mouthShrugUpper", 0.2],
  ],
  SS: [ // s z — tishlar yaqin, lablar yon
    ["jawOpen", 0.1], ["mouthSmileLeft", 0.2], ["mouthSmileRight", 0.2],
    ["mouthStretchLeft", 0.28], ["mouthStretchRight", 0.28], ["mouthShrugUpper", 0.15],
  ],
  nn: [ // n l
    ["jawOpen", 0.13], ["mouthShrugUpper", 0.18], ["mouthPressLeft", 0.14],
    ["mouthPressRight", 0.14],
  ],
  RR: [ // r
    ["jawOpen", 0.14], ["mouthFunnel", 0.24], ["mouthPucker", 0.14],
    ["mouthStretchLeft", 0.08], ["mouthStretchRight", 0.08],
  ],
  aa: [ // a — keng ochiq
    ["jawOpen", 0.58], ["mouthFunnel", 0.1], ["mouthLowerDownLeft", 0.22],
    ["mouthLowerDownRight", 0.22], ["mouthUpperUpLeft", 0.16], ["mouthUpperUpRight", 0.16],
  ],
  E: [ // e
    ["jawOpen", 0.3], ["mouthSmileLeft", 0.22], ["mouthSmileRight", 0.22],
    ["mouthStretchLeft", 0.18], ["mouthStretchRight", 0.18], ["mouthLowerDownLeft", 0.1],
    ["mouthLowerDownRight", 0.1],
  ],
  I: [ // i y
    ["jawOpen", 0.16], ["mouthSmileLeft", 0.38], ["mouthSmileRight", 0.38],
    ["mouthStretchLeft", 0.26], ["mouthStretchRight", 0.26],
  ],
  O: [ // o oʻ — yumaloq ochiq
    ["jawOpen", 0.42], ["mouthFunnel", 0.55], ["mouthPucker", 0.34],
    ["mouthUpperUpLeft", 0.08], ["mouthUpperUpRight", 0.08],
  ],
  U: [ // u — kuchli pucker
    ["jawOpen", 0.2], ["mouthFunnel", 0.5], ["mouthPucker", 0.72],
  ],
};
// Eski backend formati bilan moslik.
const VISEME_ALIASES = { A: "aa", M: "PP", O: "O", E: "E", I: "I", U: "U", S: "SS" };
const VOWEL_VISEMES = new Set(["aa", "E", "I", "O", "U"]);

// LLM mood → asimmetrik ARKit ifodalar (chap/o'ng biroz farqli — jonli ko'rinadi).
const MOOD_SHAPES = {
  neutral: [
    ["browInnerUp", 0.06], ["mouthSmileLeft", 0.1], ["mouthSmileRight", 0.07],
    ["eyeSquintLeft", 0.04], ["eyeSquintRight", 0.03],
  ],
  happy: [
    ["mouthSmileLeft", 0.5], ["mouthSmileRight", 0.44], ["cheekSquintLeft", 0.28],
    ["cheekSquintRight", 0.23], ["eyeSquintLeft", 0.22], ["eyeSquintRight", 0.17],
    ["browInnerUp", 0.12], ["browOuterUpLeft", 0.08], ["mouthDimpleLeft", 0.24],
    ["mouthDimpleRight", 0.18], ["mouthUpperUpLeft", 0.05], ["mouthUpperUpRight", 0.04],
  ],
  excited: [
    ["mouthSmileLeft", 0.58], ["mouthSmileRight", 0.52], ["browInnerUp", 0.24],
    ["browOuterUpLeft", 0.3], ["browOuterUpRight", 0.26], ["eyeWideLeft", 0.24],
    ["eyeWideRight", 0.2], ["cheekSquintLeft", 0.2], ["cheekSquintRight", 0.16],
    ["mouthDimpleLeft", 0.24], ["mouthDimpleRight", 0.2], ["jawOpen", 0.05],
  ],
  thoughtful: [
    ["browDownLeft", 0.26], ["browDownRight", 0.1], ["browInnerUp", 0.22],
    ["eyeSquintLeft", 0.18], ["eyeSquintRight", 0.07], ["mouthPressLeft", 0.28],
    ["mouthPressRight", 0.16], ["mouthLeft", 0.12], ["mouthFrownLeft", 0.05],
    ["cheekSquintLeft", 0.08],
  ],
  concerned: [
    ["browInnerUp", 0.5], ["browDownLeft", 0.1], ["browDownRight", 0.16],
    ["mouthFrownLeft", 0.26], ["mouthFrownRight", 0.3], ["mouthShrugLower", 0.24],
    ["mouthPressLeft", 0.1], ["eyeSquintLeft", 0.07], ["eyeSquintRight", 0.1],
    ["mouthStretchLeft", 0.06],
  ],
  apologetic: [
    ["browInnerUp", 0.44], ["mouthFrownLeft", 0.14], ["mouthFrownRight", 0.17],
    ["mouthPressLeft", 0.24], ["mouthPressRight", 0.24], ["eyeSquintLeft", 0.12],
    ["eyeSquintRight", 0.12], ["mouthShrugLower", 0.14],
  ],
  reassuring: [
    ["mouthSmileLeft", 0.3], ["mouthSmileRight", 0.27], ["browInnerUp", 0.18],
    ["eyeSquintLeft", 0.12], ["eyeSquintRight", 0.09], ["mouthDimpleLeft", 0.14],
  ],
};
const ERROR_OVERLAY = [
  ["browDownLeft", 0.3], ["browDownRight", 0.3], ["eyeSquintLeft", 0.18],
  ["eyeSquintRight", 0.18], ["mouthPressLeft", 0.2], ["mouthPressRight", 0.2],
];

// Gapirganda kayfiyatning og'iz atrofidagi morphlari pasaytiriladi (visemelar ustun).
const MOUTH_PREFIXES = ["mouth", "jaw", "cheekPuff"];

/* ============================== Holat ============================== */

const state = {
  current: "idle",
  mood: "neutral",
  moodFrom: "neutral",
  moodBlend: 1, // 0..1 (300ms lerp)
  mouthLevel: 0,
  smoothMouth: 0,
  clock: 0,
};

const speech = {
  active: false,
  frames: [],
  audio: null,
  curves: null, // backend audio-tahlili: {fps, jaw, close, spread, round, energy}
  scale: 1,
  idx: 0,
  fade: 0, // 0..1, boshlanish/tugashda silliq
  energy: 0,
  prevEnergy: 0,
  inhaleT0: -10, // gapirishdan oldin ko'rinadigan nafas
};

// Egri chiziqdan chiziqli interpolyatsiya bilan namuna olish (audio vaqtida).
function sampleCurve(arr, fps, tMs) {
  if (!arr || !arr.length) return 0;
  const pos = (tMs / 1000) * fps;
  const i = Math.floor(pos);
  if (i < 0) return arr[0];
  if (i >= arr.length - 1) return arr[arr.length - 1];
  const frac = pos - i;
  return arr[i] * (1 - frac) + arr[i + 1] * frac;
}

const gaze = {
  yaw: 0, pitch: 0, targetYaw: 0, targetPitch: 0,
  nextAt: 0.6, focus: true,
};

const blink = {
  t0: -10, lagR: 0.03, ampR: 1, nextAt: 1.6, pendingDouble: false,
};

const emphasis = { amp: 0, nextAt: 1.5, roll: 0 };
const fps = { ema: 60 };

function noise(t, seed) {
  return (
    Math.sin(t * 0.9 + seed) * 0.55 +
    Math.sin(t * 1.73 + seed * 2.7) * 0.3 +
    Math.sin(t * 3.11 + seed * 1.31) * 0.15
  );
}
const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);
const smoothstep = (v) => {
  const x = clamp01(v);
  return x * x * (3 - 2 * x);
};

/* ============================== Fon ============================== */

function makeBackgroundTexture() {
  const size = 512;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  // Qora-qizil radial gradient (Unclaw uslubi): markazda to'q qizil cho'g',
  // chetlarga qorong'i.
  const g = ctx.createRadialGradient(size * 0.5, size * 0.4, size * 0.05, size * 0.5, size * 0.45, size * 0.78);
  g.addColorStop(0, "#571724");
  g.addColorStop(0.35, "#310d15");
  g.addColorStop(0.7, "#150609");
  g.addColorStop(1, "#060304");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  // Bosh orqasidagi issiq qizil halo.
  const halo = ctx.createRadialGradient(size * 0.5, size * 0.35, 4, size * 0.5, size * 0.35, size * 0.34);
  halo.addColorStop(0, "rgba(214, 48, 62, 0.38)");
  halo.addColorStop(1, "rgba(214, 48, 62, 0)");
  ctx.fillStyle = halo;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/* ============================== Boot ============================== */

function withArkitParams(url) {
  // RPM manzilida ARKit morphlar so'ralmagan bo'lsa — qo'shamiz.
  if (/models\.readyplayer\.me/.test(url) && !/morphTargets=/.test(url)) {
    url += (url.includes("?") ? "&" : "?") + "morphTargets=ARKit&textureAtlas=1024";
  }
  return url;
}

// Sekin yuklanishga qarshi xotira: oxirgi ishlagan manba birinchi sinaladi,
// yaqinda yiqilganlari (masalan bloklangan RPM) chetlab o'tiladi.
function readFailMemory() {
  try {
    return JSON.parse(localStorage.getItem("avatar_url_failures") || "{}");
  } catch {
    return {};
  }
}

function markUrl(url, ok) {
  try {
    const failures = readFailMemory();
    if (ok) {
      delete failures[url];
      localStorage.setItem("avatar_url_last_good", url);
    } else {
      failures[url] = Date.now();
    }
    localStorage.setItem("avatar_url_failures", JSON.stringify(failures));
  } catch {
    // localStorage yozilmasa ham yuklash davom etadi
  }
}

function candidateUrls() {
  const urls = [];
  const push = (u) => { if (u && !urls.includes(u)) urls.push(u); };
  const saved = localStorage.getItem("avatar_glb_url");
  if (saved) push(withArkitParams(saved));
  push(localStorage.getItem("avatar_url_last_good"));
  for (const url of FALLBACK_URLS) push(url);

  const failures = readFailMemory();
  const now = Date.now();
  const fresh = urls.filter((u) => !(failures[u] && now - failures[u] < FAIL_MEMORY_MS));
  const skipped = urls.filter((u) => !fresh.includes(u));
  return fresh.concat(skipped); // yiqilganlar ham oxirida turadi (zaxira)
}

function fetchArrayBuffer(url, timeoutMs) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  return fetch(url, { signal: ctl.signal, cache: "force-cache" })
    .then((res) => {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.arrayBuffer();
    })
    .finally(() => clearTimeout(timer));
}

function parseGlb(loader, buffer) {
  return new Promise((resolve, reject) => loader.parse(buffer, "", resolve, reject));
}

function countMorphTargets(root) {
  const names = new Set();
  root.traverse((node) => {
    if (node.isMesh && node.morphTargetDictionary) {
      for (const name of Object.keys(node.morphTargetDictionary)) names.add(name);
    }
  });
  return names.size;
}

async function loadBestAvatar(loader) {
  let limited = null;
  for (const url of candidateUrls()) {
    try {
      const timeout = url.startsWith(API_BASE) ? LOCAL_TIMEOUT_MS : CANDIDATE_TIMEOUT_MS;
      const buffer = await fetchArrayBuffer(url, timeout);
      const gltf = await parseGlb(loader, buffer);
      const morphs = countMorphTargets(gltf.scene);
      if (morphs >= MIN_ARKIT_MORPHS) {
        markUrl(url, true);
        return { gltf, url, morphs };
      }
      if (!limited) limited = { gltf, url, morphs };
      console.warn(`[avatar3d] ${url}: ARKit morphlar kam (${morphs}) — keyingi manba.`);
    } catch (err) {
      // Lokal backend belgilangmaydi: birinchi so'rovda kesh hali yuklanayotgan
      // bo'lishi mumkin, keyingi ochilishda u eng tez manba bo'ladi.
      if (!url.startsWith(API_BASE)) markUrl(url, false);
      console.warn(`[avatar3d] ${url}: yuklanmadi (${err?.message || err}).`);
    }
  }
  if (limited) {
    console.warn(
      "[avatar3d] To'liq ARKit'li GLB topilmadi — cheklangan mimika. " +
      "Yechim: RPM GLB'ni (?morphTargets=ARKit) assets/avatars/ ga qo'ying."
    );
    return limited;
  }
  throw new Error("hech bir GLB manbasi ochilmadi");
}

function boot() {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: false,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, CONFIG.maxPixelRatio));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; // Unclaw uslubidagi kino rang
  renderer.toneMappingExposure = 1.12;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap; // yumshoq soya

  const scene = new THREE.Scene();
  scene.background = makeBackgroundTexture();

  // PBR teri uchun neytral environment (juda past intensivlik).
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envTexture = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = envTexture;
  pmrem.dispose();

  const camera = new THREE.PerspectiveCamera(CONFIG.camera.fov, 1, 0.05, 20);

  // Selektiv bloom: faqat eng yorqin joylar (qizil rim, ko'z yaltirashi).
  // FPS 50 dan tushsa avtomatik o'chadi — 55+ mezoni buzilmaydi.
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloomPass = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.32, 0.5, 0.82);
  composer.addPass(bloomPass);
  composer.addPass(new OutputPass());
  const post = { composer, enabled: true };

  function resize() {
    const w = container.clientWidth || window.innerWidth;
    const h = container.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    composer.setPixelRatio(Math.min(window.devicePixelRatio || 1, CONFIG.maxPixelRatio));
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);

  /* --------- Uch nuqtali yoritish (Unclaw): iliq key, sovuq fill, qizil rim --------- */
  scene.add(new THREE.HemisphereLight(0x342028, 0x0b0507, 0.4));

  const key = new THREE.SpotLight(0xffdcc0, 2.6);
  key.position.set(-0.75, 1.95, 1.05);
  key.angle = 0.62;
  key.penumbra = 1; // yumshoq chekka
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.bias = -0.0002;
  key.shadow.normalBias = 0.02;
  key.shadow.camera.near = 0.3;
  key.shadow.camera.far = 5;
  scene.add(key);

  const fill = new THREE.DirectionalLight(0x4f6fe6, 0.55);
  fill.position.set(1.1, 1.35, 0.85);
  scene.add(fill);

  const rimMain = new THREE.PointLight(0xff2733, 9, 3.5, 1.8);
  rimMain.position.set(0.55, 1.82, -0.66);
  scene.add(rimMain);

  const rimSoft = new THREE.PointLight(0xb3111f, 4.5, 3.2, 1.8);
  rimSoft.position.set(-0.78, 1.55, -0.56);
  scene.add(rimSoft);

  const loader = new GLTFLoader();
  loadBestAvatar(loader)
    .then(({ gltf, url, morphs }) => {
      console.info(`[avatar3d] GLB manbasi: ${url} (${morphs} morph)`);
      setupAvatar(gltf, { renderer, scene, camera, key, resize, post });
    })
    .catch((err) => {
      console.warn("[avatar3d] GLB yuklanmadi, 2D placeholder ishlaydi:", err?.message || err);
    });
}

/* ============================== Avatar setup ============================== */

// MeshStandardMaterial -> MeshPhysicalMaterial (xaritalarni saqlab), sayqal
// parametrlari uchun. copy() standart materialdan xavfsiz emas — qo'lda.
function upgradeToPhysical(mat) {
  if (!mat || !mat.isMeshStandardMaterial || mat.isMeshPhysicalMaterial) return mat;
  const p = new THREE.MeshPhysicalMaterial({
    name: mat.name,
    map: mat.map,
    normalMap: mat.normalMap,
    roughnessMap: mat.roughnessMap,
    metalnessMap: mat.metalnessMap,
    aoMap: mat.aoMap,
    emissiveMap: mat.emissiveMap,
    alphaMap: mat.alphaMap,
    color: mat.color.clone(),
    emissive: mat.emissive.clone(),
    roughness: mat.roughness,
    metalness: mat.metalness,
    transparent: mat.transparent,
    opacity: mat.opacity,
    alphaTest: mat.alphaTest,
    side: mat.side,
    depthWrite: mat.depthWrite,
  });
  if (mat.normalScale) p.normalScale.copy(mat.normalScale);
  p.envMapIntensity = 0.35;
  return p;
}

// Mesh nomiga qarab material sayqali (RPM Wolf3D_* konvensiyasi).
function polishMaterials(node) {
  const meshName = (node.name || "").toLowerCase();
  const mats = Array.isArray(node.material) ? node.material : [node.material];
  const upgraded = mats.map((m) => {
    if (!m) return m;
    const name = ((m.name || "") + " " + meshName).toLowerCase();
    m.envMapIntensity = 0.35;

    if (name.includes("hair")) {
      const p = upgradeToPhysical(m);
      p.clearcoat = 0.4; // sochga yaltirash chizig'i
      p.clearcoatRoughness = 0.45;
      p.envMapIntensity = 0.5;
      return p;
    }
    if (name.includes("outfit") || name.includes("cloth") || name.includes("top")) {
      const p = upgradeToPhysical(m);
      p.sheen = 0.55; // mato tolasi yaltirashi
      p.sheenRoughness = 0.65;
      p.sheenColor = new THREE.Color(0xffffff).multiplyScalar(0.35);
      return p;
    }
    if (name.includes("eye") && !name.includes("brow") && !name.includes("lash")) {
      const p = upgradeToPhysical(m);
      p.clearcoat = 1.0; // ko'z namligi/glint
      p.clearcoatRoughness = 0.08;
      p.roughness = Math.min(p.roughness, 0.25);
      p.envMapIntensity = 0.7;
      return p;
    }
    if (name.includes("glass")) {
      const p = upgradeToPhysical(m);
      p.clearcoat = 1.0;
      p.clearcoatRoughness = 0.05;
      return p;
    }
    if (name.includes("skin") || name.includes("head") || name.includes("body")) {
      m.roughness = Math.min(Math.max(m.roughness, 0.5), 0.72);
      m.envMapIntensity = 0.4;
      return m;
    }
    return m;
  });
  node.material = Array.isArray(node.material) ? upgraded : upgraded[0];
}

function setupAvatar(gltf, ctx) {
  const { renderer, scene, camera, key, resize, post } = ctx;
  const model = gltf.scene;
  scene.add(model);

  /* --------- Morph bindinglar (to'liq ARKit) --------- */
  const morphBindings = new Map(); // name -> [{influences, index}]
  const bones = { head: null, neck: null, spine2: null, spine1: null, eyeL: null, eyeR: null, clavL: null, clavR: null };

  model.traverse((node) => {
    if (node.isMesh) {
      node.castShadow = true;
      node.receiveShadow = true;
      node.frustumCulled = false; // morph/bosh harakatida chetda kesilmasin
      polishMaterials(node);
      if (node.morphTargetDictionary && node.morphTargetInfluences) {
        for (const [name, index] of Object.entries(node.morphTargetDictionary)) {
          if (!morphBindings.has(name)) morphBindings.set(name, []);
          morphBindings.get(name).push({ influences: node.morphTargetInfluences, index });
        }
      }
    }
    if (node.isBone) {
      const n = node.name.toLowerCase();
      if (!bones.head && n.includes("head")) bones.head = node;
      else if (!bones.neck && n.includes("neck")) bones.neck = node;
      else if (!bones.eyeL && (n === "lefteye" || n.includes("eye_l") || n === "eyeleft")) bones.eyeL = node;
      else if (!bones.eyeR && (n === "righteye" || n.includes("eye_r") || n === "eyeright")) bones.eyeR = node;
      else if (!bones.spine2 && n.includes("spine2")) bones.spine2 = node;
      else if (!bones.spine1 && n.includes("spine1")) bones.spine1 = node;
      else if (!bones.clavL && (n.includes("leftshoulder") || n.includes("clavicle_l"))) bones.clavL = node;
      else if (!bones.clavR && (n.includes("rightshoulder") || n.includes("clavicle_r"))) bones.clavR = node;
    }
  });
  const chest = bones.spine2 || bones.spine1;

  const rest = {
    head: bones.head ? bones.head.rotation.clone() : null,
    neck: bones.neck ? bones.neck.rotation.clone() : null,
    eyeL: bones.eyeL ? bones.eyeL.rotation.clone() : null,
    eyeR: bones.eyeR ? bones.eyeR.rotation.clone() : null,
    clavL: bones.clavL ? bones.clavL.rotation.clone() : null,
    clavR: bones.clavR ? bones.clavR.rotation.clone() : null,
  };

  // Pose bufferi: har kadr nol → yig'ish → yozish (allokatsiyasiz).
  const pose = Object.create(null);
  const managedNames = [];
  for (const name of morphBindings.keys()) {
    pose[name] = 0;
    managedNames.push(name);
  }
  const hasMorph = (name) => morphBindings.has(name);
  function addShape(shape, mult) {
    if (!shape || mult <= 0) return;
    for (let i = 0; i < shape.length; i++) {
      const name = shape[i][0];
      if (pose[name] !== undefined) pose[name] += shape[i][1] * mult;
    }
  }
  function addShapeMouthScaled(shape, mult, mouthMult) {
    if (!shape || mult <= 0) return;
    for (let i = 0; i < shape.length; i++) {
      const name = shape[i][0];
      if (pose[name] === undefined) continue;
      let m = mult;
      for (let p = 0; p < MOUTH_PREFIXES.length; p++) {
        if (name.startsWith(MOUTH_PREFIXES[p])) { m *= mouthMult; break; }
      }
      pose[name] += shape[i][1] * m;
    }
  }

  /* --------- Kadr: ko'krakdan yuqori, kamera biroz pastdan --------- */
  model.updateWorldMatrix(true, true);
  const headPos = new THREE.Vector3(0, 1.62, 0);
  if (bones.head) bones.head.getWorldPosition(headPos);
  const eyeY = headPos.y + 0.045;
  const camY = eyeY - CONFIG.camera.belowEye; // past nuqta → yuqoriga qaraydi
  const lookY = eyeY - CONFIG.camera.lookBelowEye;
  camera.position.set(0, camY, headPos.z + CONFIG.camera.back);
  const lookTarget = new THREE.Vector3(0, lookY, headPos.z);
  camera.lookAt(lookTarget);
  key.target.position.copy(headPos);
  scene.add(key.target);
  const camBase = camera.position.clone();

  /* --------- Har kadr --------- */
  const audioVisemeTime = () => {
    if (speech.audio && !speech.audio.paused && Number.isFinite(speech.audio.currentTime)) {
      return speech.audio.currentTime * 1000 * speech.scale;
    }
    return null;
  };

  let last = performance.now();
  function loop(now) {
    const dt = Math.min(0.05, Math.max(0.001, (now - last) / 1000));
    last = now;
    state.clock += dt;
    const t = state.clock;

    // FPS (diagnostika/qabul mezoni uchun).
    fps.ema += ((1 / dt) - fps.ema) * 0.06;

    const speaking = state.current === "speaking";
    const thinking = state.current === "thinking";
    const listening = state.current === "listening";

    /* ---- Pose'ni nollash ---- */
    for (let i = 0; i < managedNames.length; i++) pose[managedNames[i]] = 0;

    /* ---- Kayfiyat (300ms lerp) ---- */
    state.moodBlend = Math.min(1, state.moodBlend + (dt * 1000) / CONFIG.moodBlendMs);
    const blend = smoothstep(state.moodBlend);
    const mouthMult = speaking ? 0.4 : 1; // gapirganda og'iz visemega bo'ysunadi
    addShapeMouthScaled(MOOD_SHAPES[state.moodFrom] || MOOD_SHAPES.neutral, 1 - blend, mouthMult);
    addShapeMouthScaled(MOOD_SHAPES[state.mood] || MOOD_SHAPES.neutral, blend, mouthMult);
    if (state.current === "error") addShape(ERROR_OVERLAY, 1);
    if (thinking) {
      addShape(MOOD_SHAPES.thoughtful, 0.5);
    }

    /* ---- Lab-sinxron ---- */
    state.smoothMouth += (state.mouthLevel - state.smoothMouth) * Math.min(1, dt * 14);
    let energyTarget = 0;

    if (speech.active && speech.frames.length) {
      speech.fade = Math.min(1, speech.fade + dt * 8);
      const tm = audioVisemeTime();
      if (tm !== null) {
        const frames = speech.frames;
        while (speech.idx + 1 < frames.length && frames[speech.idx + 1].time <= tm) speech.idx++;
        while (speech.idx > 0 && frames[speech.idx].time > tm) speech.idx--; // seek orqaga
        const cur = frames[speech.idx];
        const nxt = frames[speech.idx + 1] || null;
        const segStart = cur.time;
        const segEnd = nxt ? nxt.time : segStart + 180;
        const segLen = Math.max(40, segEnd - segStart);
        // Koartikulyatsiya: kirish rampasi + keyingi visemega krossfeyd.
        const attack = Math.min(60, segLen * 0.5);
        const release = Math.min(80, segLen * 0.4);
        const wIn = smoothstep((tm - segStart) / attack);
        const wOut = nxt ? smoothstep((tm - (segEnd - release)) / release) : 0;
        const wCur = wIn * (1 - wOut);

        // Audio-tahlil egri chiziqlari (haqiqiy audio vaqtida, scale'siz).
        const cv = speech.curves;
        const rawMs = speech.audio ? speech.audio.currentTime * 1000 : tm;
        let ce = -1, cj = 0, cc = 0, cs = 0, cr = 0, cp = 0.5;
        if (cv) {
          ce = sampleCurve(cv.energy, cv.fps, rawMs);
          cj = sampleCurve(cv.jaw, cv.fps, rawMs);
          cc = sampleCurve(cv.close, cv.fps, rawMs);
          cs = sampleCurve(cv.spread, cv.fps, rawMs);
          cr = sampleCurve(cv.round, cv.fps, rawMs);
          if (cv.pitch) cp = sampleCurve(cv.pitch, cv.fps, rawMs);
        }
        // Amplituda: curves bo'lsa o'lchangan energiya, bo'lmasa RMS.
        const amp = ce >= 0
          ? 0.55 + 0.75 * ce
          : 0.72 + 0.55 * Math.min(1, state.smoothMouth * 1.4);
        addShape(VISEME_SHAPES[cur.name], wCur * cur.weight * amp * speech.fade);
        if (nxt) addShape(VISEME_SHAPES[nxt.name], wOut * nxt.weight * amp * speech.fade);

        if (cv) {
          // Fuziya: viseme QAYSI shaklni aytadi, audio QANCHA/QACHONligini.
          const f = speech.fade;
          if (pose.jawOpen !== undefined) {
            pose.jawOpen = pose.jawOpen * (0.45 + 0.75 * cj) * (1 - cc * 0.85);
          }
          if (pose.mouthClose !== undefined) pose.mouthClose += cc * 0.55 * f;
          if (pose.mouthPucker !== undefined) pose.mouthPucker += cr * 0.3 * f;
          if (pose.mouthFunnel !== undefined) pose.mouthFunnel += cr * 0.2 * f;
          if (pose.mouthStretchLeft !== undefined) {
            pose.mouthStretchLeft += cs * 0.2 * f;
            pose.mouthStretchRight += cs * 0.2 * f;
          }

          // Prosodiya -> qosh: ohang ko'tarilsa qosh ko'tariladi (savol/urg'u),
          // past ohangda yengil chimirilish. Ovoz musiqasiga ergashadi.
          const pitchUp = Math.max(0, cp - 0.56);
          const pitchDown = Math.max(0, 0.42 - cp);
          if (pose.browInnerUp !== undefined) pose.browInnerUp += pitchUp * 0.55 * f;
          if (pose.browOuterUpLeft !== undefined) {
            pose.browOuterUpLeft += pitchUp * 0.3 * f;
            pose.browOuterUpRight += pitchUp * 0.26 * f;
          }
          if (pose.browDownLeft !== undefined) {
            pose.browDownLeft += pitchDown * 0.3 * f;
            pose.browDownRight += pitchDown * 0.28 * f;
          }

          // Ta'kid endi tasodifiy emas: energiya cho'qqisida bosh irg'aydi.
          if (ce > 0.75 && ce > speech.prevEnergy + 0.015 && t > emphasis.nextAt) {
            emphasis.amp = 0.35 + ce * 0.55;
            emphasis.roll = (Math.random() - 0.5) * 2;
            emphasis.nextAt = t + 0.55;
          }
          speech.prevEnergy = ce;
          energyTarget = Math.max(ce, 0) * cur.weight;
        } else {
          energyTarget = (VOWEL_VISEMES.has(cur.name) ? 1 : 0.45) * cur.weight * wCur;
        }
      }
    } else if (speaking) {
      // Fallback: faqat amplituda (mock TTS yoki visemesiz javob).
      const m = state.smoothMouth;
      addShape(VISEME_SHAPES.aa, m * 0.75);
      addShape(VISEME_SHAPES.E, m * 0.2);
      energyTarget = m;
    } else {
      speech.fade = Math.max(0, speech.fade - dt * 6);
    }
    speech.energy += (energyTarget - speech.energy) * Math.min(1, dt * 10);

    /* ---- Asimmetrik ko'z qisish ---- */
    const bt = t - blink.t0;
    const blinkEnv = (x) =>
      x < 0 ? 0 : x < 0.07 ? smoothstep(x / 0.07) : x < 0.1 ? 1 : x < 0.22 ? 1 - smoothstep((x - 0.1) / 0.12) : 0;
    const bl = blinkEnv(bt);
    const br = blinkEnv(bt - blink.lagR) * blink.ampR;
    if (bt > 0.25 && t > blink.nextAt) {
      blink.t0 = t;
      blink.lagR = 0.015 + Math.random() * 0.035;
      blink.ampR = 0.88 + Math.random() * 0.12;
      if (blink.pendingDouble) {
        blink.pendingDouble = false;
        blink.nextAt = t + 0.3; // double blink
      } else {
        blink.pendingDouble = Math.random() < 0.14;
        const base = speaking || listening ? 1.6 : 2.2;
        blink.nextAt = t + base + Math.random() * 3.4;
      }
    }

    /* ---- Nigoh saccade'lari ---- */
    if (t > gaze.nextAt) {
      const r = Math.random();
      if (thinking && r < 0.5) {
        // O'ylayotganda yuqori-chapga qarash.
        gaze.targetYaw = -0.16 + (Math.random() - 0.5) * 0.08;
        gaze.targetPitch = 0.1 + Math.random() * 0.06;
        gaze.focus = false;
      } else if (r < (listening || speaking ? 0.78 : 0.6)) {
        // Kameraga (suhbatdoshga) qarash — mikro-siljishlar bilan.
        gaze.targetYaw = (Math.random() - 0.5) * 0.05;
        gaze.targetPitch = (Math.random() - 0.5) * 0.03;
        gaze.focus = true;
      } else if (r < 0.9) {
        gaze.targetYaw = (Math.random() - 0.5) * 0.24;
        gaze.targetPitch = (Math.random() - 0.5) * 0.1;
        gaze.focus = false;
      } else {
        gaze.targetYaw = (Math.random() < 0.5 ? -1 : 1) * (0.14 + Math.random() * 0.08);
        gaze.targetPitch = 0.02 + Math.random() * 0.08;
        gaze.focus = false;
        if (Math.random() < 0.3) blink.nextAt = Math.min(blink.nextAt, t + 0.05); // katta saccade → blink
      }
      gaze.nextAt = t + (gaze.focus ? 1.2 + Math.random() * 2.3 : 0.5 + Math.random() * 1.4);
    }
    // Saccade tez (~90ms), keyin sekin drift.
    const gazeRate = Math.min(1, dt * 26);
    gaze.yaw += (gaze.targetYaw - gaze.yaw) * gazeRate;
    gaze.pitch += (gaze.targetPitch - gaze.pitch) * gazeRate;
    const driftYaw = gaze.yaw + noise(t * 0.7, 3.1) * 0.006;
    const driftPitch = gaze.pitch + noise(t * 0.9, 7.7) * 0.004;

    // Qovoqlar nigohga ergashadi + blink.
    const lookDown = Math.max(0, -driftPitch) * 1.6;
    const lookUp = Math.max(0, driftPitch) * 1.2;
    if (pose.eyeBlinkLeft !== undefined) pose.eyeBlinkLeft += bl;
    if (pose.eyeBlinkRight !== undefined) pose.eyeBlinkRight += br;
    if (pose.eyesClosed !== undefined) pose.eyesClosed += Math.min(bl, br); // legacy rig
    if (pose.eyeLookDownLeft !== undefined) {
      pose.eyeLookDownLeft += lookDown * 0.5;
      pose.eyeLookDownRight += lookDown * 0.5;
    }
    if (pose.eyeLookUpLeft !== undefined) {
      pose.eyeLookUpLeft += lookUp * 0.4;
      pose.eyeLookUpRight += lookUp * 0.4;
    }

    /* ---- Gapirganda bosh ta'kidlari (curves bo'lmasa tasodifiy fallback) ---- */
    if (speaking && !speech.curves && t > emphasis.nextAt) {
      emphasis.amp = 0.5 + Math.random() * 0.5;
      emphasis.roll = (Math.random() - 0.5) * 2;
      emphasis.nextAt = t + 1.1 + Math.random() * 1.6;
    }
    emphasis.amp = Math.max(0, emphasis.amp - dt * 2.6);
    const accent = smoothstep(emphasis.amp);
    if (accent > 0.01 && pose.browInnerUp !== undefined) {
      pose.browInnerUp += accent * 0.12; // ta'kidda qosh ham ko'tariladi
    }

    /* ---- Gapirishdan oldin nafas envelope (pose yozuvidan OLDIN) ---- */
    const it = t - speech.inhaleT0;
    let inhaleEnv = 0;
    if (it >= 0 && it < 0.75) {
      inhaleEnv = it < 0.3 ? smoothstep(it / 0.3) : 1 - smoothstep((it - 0.3) / 0.45);
      if (pose.jawOpen !== undefined && speech.fade < 0.3) {
        pose.jawOpen = Math.max(pose.jawOpen, inhaleEnv * 0.07); // lablar yengil ochiladi
      }
    }

    /* ---- Pose'ni morphlarga yozish ---- */
    for (let i = 0; i < managedNames.length; i++) {
      const name = managedNames[i];
      const value = clamp01(pose[name]);
      const list = morphBindings.get(name);
      for (let j = 0; j < list.length; j++) list[j].influences[list[j].index] = value;
    }

    /* ---- Nafas — ko'krakda ko'rinadi ---- */
    const rate = speaking ? CONFIG.breath.speakHz : CONFIG.breath.idleHz;
    const phase = t * rate * Math.PI * 2;
    const warped = phase + 0.35 * Math.sin(phase); // nafas olish tezroq, chiqarish sekin
    let s = 0.5 - 0.5 * Math.cos(warped);
    let chestAmp = speaking ? 0.6 : 1;

    // Gapirishdan oldin chuqur nafas: ko'krak keskinroq ko'tariladi.
    if (inhaleEnv > 0) {
      s = Math.min(1.2, s + inhaleEnv * 0.85);
      chestAmp = Math.max(chestAmp, 1.15);
    }
    if (chest) {
      const sx = 1 + CONFIG.breath.chest * s * chestAmp;
      const sy = 1 + 0.004 * s * chestAmp;
      const sz = 1 + CONFIG.breath.chest * 1.25 * s * chestAmp;
      chest.scale.set(sx, sy, sz);
      // Bosh kattalashib qolmasin: bo'yinda teskari kompensatsiya.
      if (bones.neck) bones.neck.scale.set(1 / sx, 1 / sy, 1 / sz);
    }
    if (bones.clavL && rest.clavL) bones.clavL.rotation.z = rest.clavL.z - CONFIG.breath.shoulder * s * chestAmp;
    if (bones.clavR && rest.clavR) bones.clavR.rotation.z = rest.clavR.z + CONFIG.breath.shoulder * s * chestAmp;
    model.position.y = 0.0025 * s;

    /* ---- Bosh va bo'yin ---- */
    if (bones.head && rest.head) {
      let rx = noise(t * 0.35, 1.2) * 0.016; // tirik sokin tebranish
      let ry = noise(t * 0.28, 5.9) * 0.022;
      let rz = noise(t * 0.22, 9.4) * 0.008;
      rx -= inhaleEnv * 0.012; // nafasda bosh yengil ko'tariladi
      // Nigohga yengil ergashish.
      ry += driftYaw * 0.25;
      rx += -driftPitch * 0.15;
      if (thinking) { rx += -0.05; ry += -0.1; rz += 0.02; }
      if (listening) { rz += 0.06; rx += 0.02; ry += driftYaw * 0.1; }
      if (state.current === "error") { rx += 0.03; }
      if (speaking) {
        rx += speech.energy * -0.02 + accent * -0.045; // ta'kid: yengil bosh irg'ash
        rz += accent * 0.012 * emphasis.roll;
        ry += noise(t * 1.1, 2.2) * 0.012;
      }
      const smooth = Math.min(1, dt * 9);
      bones.head.rotation.x += (rest.head.x + rx - bones.head.rotation.x) * smooth;
      bones.head.rotation.y += (rest.head.y + ry - bones.head.rotation.y) * smooth;
      bones.head.rotation.z += (rest.head.z + rz - bones.head.rotation.z) * smooth;
      if (bones.neck && rest.neck) {
        bones.neck.rotation.x = rest.neck.x + (bones.head.rotation.x - rest.head.x) * 0.35;
        bones.neck.rotation.y = rest.neck.y + (bones.head.rotation.y - rest.head.y) * 0.4;
        bones.neck.rotation.z = rest.neck.z + (bones.head.rotation.z - rest.head.z) * 0.3;
      }
    }

    /* ---- Ko'z suyaklari (saccade) ---- */
    if (bones.eyeL && rest.eyeL) {
      bones.eyeL.rotation.y = rest.eyeL.y + driftYaw + 0.01;
      bones.eyeL.rotation.x = rest.eyeL.x - driftPitch;
    }
    if (bones.eyeR && rest.eyeR) {
      bones.eyeR.rotation.y = rest.eyeR.y + driftYaw - 0.01;
      bones.eyeR.rotation.x = rest.eyeR.x - driftPitch;
    }

    /* ---- Kamera mikro-drift (kino his) ---- */
    camera.position.x = camBase.x + noise(t * 0.1, 4.4) * 0.004;
    camera.position.y = camBase.y + noise(t * 0.12, 8.2) * 0.003;
    camera.lookAt(lookTarget);

    /* ---- Render: bloom (FPS guard bilan) yoki to'g'ridan-to'g'ri ---- */
    if (post && post.enabled && t > 6 && fps.ema < 50) {
      post.enabled = false;
      console.info("[avatar3d] FPS pasaydi — bloom o'chirildi (55+ mezoni ustun).");
    }
    if (post && post.enabled) post.composer.render();
    else renderer.render(scene, camera);
  }

  container.appendChild(renderer.domElement);
  resize();
  renderer.setAnimationLoop(loop);

  // 2D placeholderni yashiramiz — 3D tayyor.
  if (fallbackCanvas) fallbackCanvas.style.display = "none";

  /* --------- Tashqi API --------- */
  function normalizeFrames(rawFrames) {
    const out = [];
    for (const f of rawFrames || []) {
      if (!f) continue;
      const rawName = String(f.name ?? f.viseme ?? "sil");
      const name = VISEME_SHAPES[rawName]
        ? rawName
        : VISEME_ALIASES[rawName] || (VISEME_SHAPES[rawName.toLowerCase()] ? rawName.toLowerCase() : "sil");
      out.push({
        time: Number(f.time_ms ?? f.time ?? 0),
        name,
        weight: clamp01(Number(f.weight ?? 0.8)),
      });
    }
    out.sort((a, b) => a.time - b.time);
    return out;
  }

  window.Avatar3D = {
    ready: true,
    setState(next) { state.current = next || "idle"; },
    setMood(next) {
      const mood = next && MOOD_SHAPES[next] ? next : "neutral";
      if (mood === state.mood) return;
      state.moodFrom = state.mood;
      state.mood = mood;
      state.moodBlend = 0; // 300ms silliq o'tish boshlanadi
    },
    setMouthLevel(level) { state.mouthLevel = clamp01(level); },
    // Fonema-aniq lab-sinxron: backend viseme timeline + audio elementi +
    // ixtiyoriy audio-tahlil egri chiziqlari (mouth_curves).
    speak(frames, audioEl, curves) {
      const normalized = normalizeFrames(frames);
      if (!normalized.length) return false;
      speech.frames = normalized;
      speech.audio = audioEl || null;
      speech.curves =
        curves && curves.fps > 0 && Array.isArray(curves.jaw) && curves.jaw.length
          ? curves
          : null;
      speech.idx = 0;
      speech.fade = 0;
      speech.scale = 1;
      speech.prevEnergy = 0;
      speech.inhaleT0 = state.clock; // gapirishdan oldin ko'rinadigan nafas
      speech.active = true;
      const timelineDur = normalized[normalized.length - 1].time;
      // Streaming'da audioEl oddiy clock-obyekt (faqat currentTime) bo'ladi —
      // scale 1 qoladi (timeline real vaqtga tayanadi).
      if (
        audioEl &&
        typeof audioEl.addEventListener === "function" &&
        timelineDur > 200
      ) {
        const applyScale = () => {
          if (Number.isFinite(audioEl.duration) && audioEl.duration > 0.2) {
            speech.scale = Math.max(0.6, Math.min(1.7, timelineDur / (audioEl.duration * 1000)));
            // timeline vaqti = audio vaqti * scale emas: audio vaqtini timeline
            // fazosiga o'tkazamiz.
          }
        };
        if (audioEl.readyState >= 1) applyScale();
        else audioEl.addEventListener("loadedmetadata", applyScale, { once: true });
      }
      return true;
    },
    // Streaming: timeline/egri chiziqlar o'sib boradi — holatni buzmasdan
    // yangilash (idx saqlanadi, fade qayta boshlanmaydi).
    updateTimeline(frames, curves) {
      if (!speech.active) return false;
      const normalized = normalizeFrames(frames);
      if (normalized.length) {
        speech.frames = normalized;
        if (speech.idx >= normalized.length) speech.idx = normalized.length - 1;
      }
      if (curves && curves.fps > 0 && Array.isArray(curves.jaw) && curves.jaw.length) {
        speech.curves = curves;
      }
      return true;
    },
    stopSpeaking() {
      speech.active = false;
      speech.audio = null;
      speech.frames = [];
      speech.curves = null;
      speech.idx = 0;
    },
    getFps() { return Math.round(fps.ema); },
    debug: {
      morphCount: morphBindings.size,
      bones: Object.fromEntries(Object.entries(bones).map(([k, v]) => [k, v ? v.name : null])),
    },
  };

  console.info(
    "[avatar3d] 3D avatar yuklandi. Morphlar:", morphBindings.size,
    "| Suyaklar:", window.Avatar3D.debug.bones
  );
  if (morphBindings.size < 30) {
    console.warn(
      "[avatar3d] ARKit morphlar to'liq emas — GLB manziliga ?morphTargets=ARKit qo'shing."
    );
  }
}

try {
  boot();
} catch (err) {
  console.warn("[avatar3d] ishga tushmadi, 2D placeholder ishlaydi:", err);
}
