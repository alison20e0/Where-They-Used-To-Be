#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generar_juego.py  (v2 · estética PSX / VHS)
===========================================
Generador de la demo jugable de terror psicológico "Where They Used to Be".

Al ejecutarse escribe un único 'index.html' con todo el juego (HTML + CSS + JS).
Render 3D con Three.js r128 (CDN). Todo el audio se sintetiza con Web Audio API.

Novedades de la v2
------------------
* ESTÉTICA PSX 32-bit: render interno a baja resolución (240p), texturas con
  filtrado "nearest", temblor de vértices (vertex snapping) e iluminación por
  vértice (Gouraud), como en PlayStation.
* PERSONAJES LOW-POLY CON ROSTRO: estudiantes y monstruo construidos con
  cilindros facetados y deformados, con caras pixeladas generadas en canvas
  (efecto "uncanny valley"). El rostro del monstruo se re-dibuja con glitches.
* FILTRO VHS / CRT: pase de post-proceso con ruido analógico, desgarros de
  tracking, aberración cromática, scanlines, curvatura, dithering 15-bit y
  viñeta. La intensidad del glitch reacciona a la cercanía del monstruo.
* SOMBRAS DURAS: linterna (SpotLight) y luces puntuales clave con sombras
  BasicShadowMap; niebla negra que limita la visión alrededor del jugador.
* FASES:
    1. Oficina del profesor: al entrar, la puerta se cierra y el ruido se corta
       en seco. Al salir todo está oscuro y el juego pide pulsar [F].
    2. Salida principal trancada; la de emergencia sin energía. El Pasillo B
       entra en un BUCLE espacial con cambios sutiles de luz y sombra hasta que
       el jugador activa el PANEL ELÉCTRICO, que desbloquea la salida.
    3. Persecución: al cruzar la puerta de emergencia hay una breve cinemática
       (el jugador se detiene, mira atrás, el monstruo revienta la puerta, la
       cámara vuelve al pasillo y aparece "CORRE"). Jumpscare al ser atrapado;
       reaparición justo ANTES de esa puerta.
    5. Vestíbulo final: la persecución cesa. Una gran puerta de cristal da a la
       ciudad vacía bajo la luna. Está trancada. Al mirar fijamente tu reflejo
       (con la linterna del teléfono encendida) aparece la criatura de cuello
       largo justo detrás de ti. Al voltear no hay nada: la luz parpadea, un
       golpe seco, negro y el título.

Uso:
    python generar_juego.py                  -> genera index.html
    python generar_juego.py --abrir          -> genera y abre en el navegador
    python generar_juego.py -o demo.html     -> nombre de salida personalizado
"""

import argparse
import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

TITULO = "Where They Used to Be"
VERSION = "3.0-psx"

# ---------------------------------------------------------------------------
# Parámetros (velocidades en metros/segundo)
# ---------------------------------------------------------------------------
CONFIG = {
    "walk": 3.0,            # velocidad caminando
    "sprint": 6.6,          # velocidad corriendo (SHIFT)
    "monster": 6.0,         # velocidad base del monstruo (menor que sprint)
    "catchup": 7.4,         # velocidad del monstruo si el jugador se aleja mucho
    "leash": 7.0,           # distancia a partir de la cual el monstruo acelera
    "catchDist": 1.25,      # distancia de captura
    "mouse": 0.0022,        # sensibilidad del mouse
    "fov": 72,
    "resY": 240,            # resolución vertical interna (240 = PlayStation)
    "wobble": 0.35,         # temblor de vértices PSX (0.5 = 1 px; menor = más temblor)
    "loopNeeded": 2,        # vueltas del bucle antes de que aparezca el panel eléctrico
    "vhs": 0.55,            # intensidad del filtro VHS/CRT (0 = limpio, 1 = fuerte)
    "cineSpeed": 8.5,       # velocidad del monstruo en la cinemática de la puerta
    "headStart": 0.9,       # segundos que el monstruo espera tras la cinemática
    "stareTime": 2.2,       # segundos mirando el reflejo para la revelación
}

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Demo</title>
<!-- Generado por generar_juego.py el __DATE__ (versión __VERSION__) -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<style>
  html,body{margin:0;height:100%;background:#000;overflow:hidden;font-family:'Courier New',Courier,monospace;color:#d8d8d0;user-select:none}
  canvas#game{display:block;position:fixed;inset:0;image-rendering:pixelated}
  #fade{position:fixed;inset:0;pointer-events:none;background:#000;opacity:1;transition:opacity 1.2s}
  #objective{position:fixed;top:18px;left:22px;font-size:13px;letter-spacing:1px;text-shadow:0 0 4px #000,0 0 2px #000;max-width:46ch;opacity:.9;transition:opacity .6s}
  #objective b{color:#e9e2c8}
  #rec{position:fixed;top:16px;right:22px;font-size:13px;letter-spacing:2px;color:#e8e0d0;text-shadow:0 0 4px #000;opacity:.75}
  #rec i{display:inline-block;width:9px;height:9px;border-radius:50%;background:#d0201a;margin-right:6px;animation:blink 1.2s steps(1) infinite}
  #prompt{position:fixed;top:57%;left:50%;transform:translateX(-50%);font-size:14px;letter-spacing:1px;opacity:0;transition:opacity .15s;text-shadow:0 0 4px #000}
  #subtitle{position:fixed;bottom:9%;left:50%;transform:translateX(-50%);font-size:16px;text-align:center;opacity:0;transition:opacity .5s;text-shadow:0 0 6px #000,0 0 2px #000;max-width:70ch;line-height:1.5}
  #hint{position:fixed;bottom:22%;left:50%;transform:translateX(-50%);font-size:22px;letter-spacing:6px;color:#e0d0c0;opacity:0;transition:opacity .4s;text-shadow:0 0 8px #000}
  #fhint{position:fixed;bottom:24%;left:50%;transform:translateX(-50%);font-size:18px;letter-spacing:5px;color:#efe6d2;text-shadow:0 0 8px #000;display:none;animation:pulse 1.6s infinite;white-space:nowrap}
  #fhint b{border:2px solid #efe6d2;padding:0 8px;margin:0 6px}
  #crosshair{position:fixed;top:50%;left:50%;width:4px;height:4px;margin:-2px 0 0 -2px;background:rgba(255,255,255,.55)}
  .overlay{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.9);z-index:10;cursor:pointer}
  .overlay .box{max-width:560px;padding:32px;text-align:center;line-height:1.6}
  .overlay .tag{font-size:11px;letter-spacing:4px;color:#8a857a}
  .overlay h2{font-weight:normal;letter-spacing:3px;margin:18px 0 8px;color:#e8e2d0}
  .overlay .keys{display:grid;grid-template-columns:auto auto;gap:4px 18px;justify-content:center;font-size:13px;margin:22px 0;color:#bdb8aa;text-align:left}
  .overlay .keys span:nth-child(odd){color:#f0eadb;text-align:right}
  .overlay .go{margin-top:18px;font-size:14px;letter-spacing:3px;animation:pulse 2.2s infinite}
  .overlay .warn{font-size:12px;color:#9b6a5a;margin-top:12px}
  @keyframes pulse{0%,100%{opacity:.35}50%{opacity:1}}
  @keyframes blink{0%{opacity:1}50%{opacity:0}}
  #end{position:fixed;inset:0;display:none;align-items:center;justify-content:center;flex-direction:column;background:#000;z-index:20;cursor:pointer}
  #end h1{font-family:Georgia,'Times New Roman',serif;font-weight:normal;font-size:clamp(28px,6vw,64px);letter-spacing:.12em;color:#e6e0d2;opacity:0;transition:opacity 4s;margin:0;text-align:center;padding:0 16px;text-shadow:2px 0 rgba(255,0,0,.35),-2px 0 rgba(0,200,255,.3)}
  #end p{opacity:0;transition:opacity 3s;letter-spacing:6px;font-size:12px;color:#8d887c;margin-top:22px}
  #end .again{font-size:11px;letter-spacing:3px;color:#666}
  #nothree{position:fixed;inset:0;display:none;align-items:center;justify-content:center;text-align:center;padding:30px;z-index:30;background:#000}
</style>
</head>
<body>
<div id="objective"></div>
<div id="rec"><i></i>REC</div>
<div id="crosshair"></div>
<div id="prompt"></div>
<div id="hint"></div>
<div id="fhint">PULSA<b>F</b>PARA ENCENDER LA LINTERNA</div>
<div id="subtitle"></div>
<div id="fade"></div>

<div id="start" class="overlay">
  <div class="box">
    <div class="tag">PROTOTIPO JUGABLE · TERROR PSICOLÓGICO · 32-BIT</div>
    <h2>Basado en un sueño real</h2>
    <div style="font-size:14px;color:#c9c3b3">🎧 Usa auriculares. El audio es parte del juego.</div>
    <div class="keys">
      <span>W A S D</span><span>moverse</span>
      <span>Mouse</span><span>mirar</span>
      <span>SHIFT</span><span>correr</span>
      <span>E</span><span>interactuar</span>
      <span>F</span><span>linterna del teléfono</span>
      <span>ESC</span><span>pausa</span>
    </div>
    <div class="go">HAZ CLIC PARA COMENZAR</div>
    <div class="warn">Contiene sustos repentinos, destellos y sonidos fuertes.</div>
  </div>
</div>
<div id="pause" class="overlay" style="display:none">
  <div class="box"><div class="tag">PAUSA</div><div class="go">HAZ CLIC PARA CONTINUAR</div></div>
</div>
<div id="end"><h1>__TITLE__</h1><p>FIN DE LA DEMO</p><p class="again">clic para volver a empezar</p></div>
<div id="nothree"><div>No se pudo cargar Three.js.<br>Conéctate a internet la primera vez que abras la demo y recarga la página.</div></div>

<script>
'use strict';
const CFG = __CONFIG__;
if (typeof THREE === 'undefined') { document.getElementById('nothree').style.display = 'flex'; throw new Error('THREE missing'); }

// =====================================================================
// UTILIDADES
// =====================================================================
const rand = (a, b) => a + Math.random() * (b - a);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const angDiff = (a, b) => { let d = b - a; while (d > Math.PI) d -= Math.PI * 2; while (d < -Math.PI) d += Math.PI * 2; return d; };
const $ = id => document.getElementById(id);
const hash3 = (x, y, z) => { const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return s - Math.floor(s); };
const hex = n => '#' + n.toString(16).padStart(6, '0');

const H = 3.2;           // altura de los pasillos
const EYE = 1.62;        // altura de la cámara
const MOD = 12;          // largo de cada módulo del Pasillo B (bucle)

// =====================================================================
// RENDER: resolución interna baja + pase VHS/CRT
// =====================================================================
const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(1);
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.BasicShadowMap;      // sombras duras, sin suavizado
renderer.domElement.id = 'game';
document.body.prepend(renderer.domElement);

const scene = new THREE.Scene();
const FOG_DAY = 0xbfc1b6;
scene.background = new THREE.Color(FOG_DAY);
scene.fog = new THREE.Fog(FOG_DAY, 10, 46);
let fogFarT = 46;

const camera = new THREE.PerspectiveCamera(CFG.fov, innerWidth / innerHeight, 0.04, 200);
camera.rotation.order = 'YXZ';
scene.add(camera);

const lowSize = () => { const h = CFG.resY; return [Math.max(2, Math.round(h * innerWidth / innerHeight)), h]; };
let [RW, RH] = lowSize();

// --- Temblor de vértices PSX: se ajusta gl_Position a la rejilla de píxeles
const SNAP = { value: new THREE.Vector2(RW, RH) };
function psxCompile(shader) {
  shader.uniforms.uSnap = SNAP;
  shader.vertexShader = 'uniform vec2 uSnap;\n' + shader.vertexShader.replace('#include <project_vertex>',
    '#include <project_vertex>\n{ vec4 sp = gl_Position; vec2 sg = uSnap * ' + Number(CFG.wobble).toFixed(3) +
    '; sp.xy = floor(sp.xy / sp.w * sg + 0.5) / sg * sp.w; gl_Position = sp; }');
}
function psx(m) { if (!m || m.isShaderMaterial || (m.userData && m.userData.psx)) return m; m.userData.psx = true; m.onBeforeCompile = psxCompile; return m; }
function psxAll(root) { root.traverse(o => { if (o.material) [].concat(o.material).forEach(psx); }); }

// --- Post-proceso VHS / CRT
const rt = new THREE.WebGLRenderTarget(RW, RH, { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter });
const postCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
const postScene = new THREE.Scene();
const post = new THREE.ShaderMaterial({
  uniforms: {
    tDiffuse: { value: rt.texture }, uTime: { value: 0 }, uRes: { value: new THREE.Vector2(RW, RH) },
    uGlitch: { value: 0.1 }, uRed: { value: 0 }, uVig: { value: 0.4 }, uAmt: { value: CFG.vhs },
  },
  vertexShader: `
    varying vec2 vUv;
    void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
  fragmentShader: `
    uniform sampler2D tDiffuse;
    uniform float uTime;
    uniform float uGlitch;
    uniform float uRed;
    uniform float uVig;
    uniform float uAmt;
    uniform vec2 uRes;
    varying vec2 vUv;
    float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
    float b2(vec2 p) { return 2.0 * p.x + 3.0 * p.y - 4.0 * p.x * p.y; }
    float bayer(vec2 p) { p = mod(p, 4.0); return (4.0 * b2(mod(p, 2.0)) + b2(floor(p / 2.0))) / 16.0; }
    void main() {
      vec2 cc = vUv - 0.5;
      vec2 uv = 0.5 + cc * (1.0 + 0.06 * uAmt * dot(cc, cc));
      if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) { gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0); return; }
      float g = uGlitch;
      float tf = floor(uTime * 30.0);
      float line = floor(uv.y * uRes.y);
      float blk = floor(uv.y * 30.0);
      float jit = (hash(vec2(line, tf)) - 0.5) * (0.0006 * uAmt + 0.012 * g * g);
      float bandPos = fract(uTime * 0.04 + 0.3);
      float band = (1.0 - smoothstep(0.0, 0.02 + 0.05 * g, abs(uv.y - bandPos))) * (0.25 + g);
      float tear = step(0.997 - 0.06 * g, hash(vec2(blk, tf)));
      uv.x += jit + band * 0.004 * (hash(vec2(line, tf + 7.0)) - 0.5) + tear * (hash(vec2(tf, blk + 3.0)) - 0.5) * 0.07 * g;
      float ca = (0.5 * uAmt + 4.0 * g) / uRes.x;
      vec3 col = vec3(texture2D(tDiffuse, uv + vec2(ca, 0.0)).r, texture2D(tDiffuse, uv).g, texture2D(tDiffuse, uv - vec2(ca, 0.0)).b);
      float lum = dot(col, vec3(0.299, 0.587, 0.114));
      col = mix(vec3(lum), col, 1.0 - 0.15 * uAmt) * mix(vec3(1.0), vec3(1.03, 1.0, 0.94), uAmt);
      vec2 px = floor(uv * uRes);
      float n = hash(px + vec2(fract(uTime * 7.31) * 517.0, fract(uTime * 3.17) * 211.0));
      col += (n - 0.5) * (0.035 * uAmt + 0.08 * g);
      col += band * (0.02 + 0.05 * n);
      col *= 1.0 - 0.07 * uAmt + 0.07 * uAmt * sin(gl_FragCoord.y * 1.5708);
      col = floor(clamp(col, 0.0, 1.0) * 31.0 + bayer(px)) / 31.0;
      col = mix(col, col * vec3(1.7, 0.3, 0.25) + vec3(0.06, 0.0, 0.0), uRed);
      float vig = smoothstep(0.82, 0.18, length(cc * vec2(1.0, 1.2)));
      col *= mix(1.0, vig, uVig);
      gl_FragColor = vec4(col, 1.0);
    }`,
  depthTest: false, depthWrite: false,
});
const postQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), post); postQuad.frustumCulled = false; postScene.add(postQuad);

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  [RW, RH] = lowSize(); rt.setSize(RW, RH); post.uniforms.uRes.value.set(RW, RH); SNAP.value.set(RW, RH);
});

// =====================================================================
// TEXTURAS PROCEDURALES (baja resolución, filtrado "nearest")
// =====================================================================
function canvasTex(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d', { willReadFrequently: true }); g.imageSmoothingEnabled = false; draw(g, w, h);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.magFilter = t.minFilter = THREE.NearestFilter; t.generateMipmaps = false;
  return t;
}
function makeCanvas(w, h) {   // lienzo re-dibujable (caras, pantallas)
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d', { willReadFrequently: true }); g.imageSmoothingEnabled = false;
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  t.magFilter = t.minFilter = THREE.NearestFilter; t.generateMipmaps = false;
  return { c, g, t, w, h };
}
function grainFill(g, w, h, amt) {
  const d = g.getImageData(0, 0, w, h);
  for (let i = 0; i < d.data.length; i += 4) {
    const n = (Math.random() - 0.5) * amt;
    d.data[i] += n; d.data[i + 1] += n; d.data[i + 2] += n;
  }
  g.putImageData(d, 0, 0);
}
function scaleUV(geo, sx, sy) {
  const uv = geo.attributes.uv;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * sx, uv.getY(i) * sy);
  uv.needsUpdate = true; return geo;
}

const floorTex = canvasTex(64, 64, (g, w, h) => {
  const s = 32;
  for (let y = 0; y < 2; y++) for (let x = 0; x < 2; x++) { g.fillStyle = ((x + y) % 2) ? '#b4ae9f' : '#cdc7b8'; g.fillRect(x * s, y * s, s, s); }
  grainFill(g, w, h, 26);
  for (let i = 0; i < 10; i++) { g.fillStyle = 'rgba(70,60,50,0.1)'; g.fillRect(rand(0, w) | 0, rand(0, h) | 0, rand(2, 10) | 0, rand(2, 8) | 0); }
  g.fillStyle = 'rgba(60,55,45,.5)'; g.fillRect(0, 0, w, 1); g.fillRect(0, s, w, 1); g.fillRect(0, 0, 1, h); g.fillRect(s, 0, 1, h);
});
const wallTex = canvasTex(64, 64, (g, w, h) => {
  g.fillStyle = '#d8d1bf'; g.fillRect(0, 0, w, h);
  g.fillStyle = '#7b887a'; g.fillRect(0, 42, w, 22);
  g.fillStyle = '#56604f'; g.fillRect(0, 41, w, 2);
  g.fillStyle = '#2e2f2a'; g.fillRect(0, 61, w, 3);
  for (let i = 0; i < 5; i++) { g.fillStyle = 'rgba(60,50,40,.12)'; g.fillRect(rand(0, w) | 0, rand(0, 40) | 0, 1, rand(4, 16) | 0); }
  grainFill(g, w, h, 18);
});
const wallTex2 = canvasTex(64, 64, (g, w, h) => {   // pasillo de emergencia: concreto
  g.fillStyle = '#8e8c86'; g.fillRect(0, 0, w, h);
  grainFill(g, w, h, 44);
  for (let i = 0; i < 10; i++) { g.fillStyle = 'rgba(40,30,20,0.22)'; g.fillRect(rand(0, w) | 0, rand(10, 40) | 0, rand(1, 4) | 0, rand(10, 40) | 0); }
  g.fillStyle = '#5a1f1a'; g.fillRect(0, 39, w, 2);
  g.fillStyle = '#2a2826'; g.fillRect(0, 61, w, 3);
  g.fillStyle = 'rgba(30,30,30,.4)'; g.fillRect(0, 0, w, 1); g.fillRect(0, 0, 1, h);
});
const ceilTex = canvasTex(32, 32, (g, w, h) => {
  g.fillStyle = '#e4e2da'; g.fillRect(0, 0, w, h); grainFill(g, w, h, 24);
  for (let i = 0; i < 20; i++) { g.fillStyle = 'rgba(80,80,70,.3)'; g.fillRect(rand(0, w) | 0, rand(0, h) | 0, 1, 1); }
  g.fillStyle = '#9d9a90'; g.fillRect(0, 0, w, 1); g.fillRect(0, 0, 1, h);
});
const lockerTex = canvasTex(32, 64, (g, w, h) => {
  g.fillStyle = '#4f6a7c'; g.fillRect(0, 0, w, h); grainFill(g, w, h, 18);
  g.fillStyle = '#2b3a44'; g.fillRect(0, 0, 1, h); g.fillRect(w - 1, 0, 1, h);
  for (let i = 0; i < 4; i++) g.fillRect(9, 5 + i * 3, 14, 1);
  g.fillStyle = '#c9cfd2'; g.fillRect(w - 7, 30, 2, 7);
  g.fillStyle = '#1d262c'; g.fillRect(0, h - 3, w, 3);
});
const bookTex = canvasTex(64, 64, (g, w, h) => {
  g.fillStyle = '#3a2a1e'; g.fillRect(0, 0, w, h);
  for (let row = 0; row < 4; row++) {
    let x = 1;
    while (x < w - 3) {
      const bw = 2 + (rand(0, 3) | 0);
      g.fillStyle = ['#7a2b22', '#2a4a6a', '#3d5c32', '#8a7a4a', '#5a3a6a', '#222', '#9a8a70'][(Math.random() * 7) | 0];
      g.fillRect(x, row * 16 + 2, bw, 12); x += bw + 1;
    }
    g.fillStyle = '#24180f'; g.fillRect(0, row * 16 + 14, w, 2);
  }
});
const boardTex = canvasTex(64, 32, (g, w, h) => {
  g.fillStyle = '#a5794a'; g.fillRect(0, 0, w, h); grainFill(g, w, h, 34);
  for (let i = 0; i < 10; i++) {
    g.fillStyle = ['#f4f1e6', '#f3e27a', '#a8d8f0', '#f2b6b6', '#c9f0b4'][(Math.random() * 5) | 0];
    const x = rand(2, w - 12) | 0, y = rand(2, h - 12) | 0; g.fillRect(x, y, 6 + (rand(0, 4) | 0), 7 + (rand(0, 4) | 0));
    g.fillStyle = 'rgba(0,0,0,.45)'; g.fillRect(x + 1, y + 2, 4, 1); g.fillRect(x + 1, y + 4, 3, 1);
  }
  g.fillStyle = '#5a3c20'; g.fillRect(0, 0, w, 2); g.fillRect(0, h - 2, w, 2); g.fillRect(0, 0, 2, h); g.fillRect(w - 2, 0, 2, h);
});
const clothTex = canvasTex(16, 16, (g, w, h) => {
  g.fillStyle = '#c4c4c4'; g.fillRect(0, 0, w, h); grainFill(g, w, h, 70);
  g.fillStyle = 'rgba(0,0,0,.18)'; g.fillRect(0, 7, w, 1); g.fillRect(7, 0, 1, h);
});
const mSkinTex = canvasTex(32, 32, (g, w, h) => {
  g.fillStyle = '#7a6c5e'; g.fillRect(0, 0, w, h);
  for (let i = 0; i < 60; i++) { g.fillStyle = Math.random() < 0.6 ? 'rgba(30,20,16,.55)' : 'rgba(160,140,115,.35)'; g.fillRect(rand(0, w) | 0, rand(0, h) | 0, 1 + (rand(0, 3) | 0), 1 + (rand(0, 3) | 0)); }
  g.fillStyle = 'rgba(70,10,8,.5)'; for (let i = 0; i < 6; i++) g.fillRect(rand(0, w) | 0, rand(0, h) | 0, 1, 3 + (rand(0, 5) | 0));
  grainFill(g, w, h, 34);
});

// ---------- ROSTROS PIXELADOS (uncanny valley)
// Textura que envuelve una cabeza cilíndrica: el centro (x≈24) es la cara.
function drawFace(g, o) {
  const W = 48, Hh = 24, cr = o.creepy || 0;
  g.fillStyle = o.skin; g.fillRect(0, 0, W, Hh);
  g.fillStyle = 'rgba(0,0,0,.16)'; g.fillRect(14, 0, 2, Hh); g.fillRect(32, 0, 2, Hh); g.fillRect(16, 21, 16, 3);
  g.fillStyle = o.hair; g.fillRect(0, 0, W, 4); g.fillRect(0, 0, 15, 17); g.fillRect(33, 0, 15, 17);
  for (let x = 15; x < 33; x++) g.fillRect(x, 4, 1, 1 + ((hash3(x, o.seed, 1) * 3) | 0));
  const dy = cr ? 1 : 0;
  if (cr >= 2) {
    g.fillStyle = '#000'; g.fillRect(18, 9, 4, 4); g.fillRect(26, 9 + dy, 4, 4);
    g.fillStyle = '#fff'; g.fillRect(19, 10, 1, 1); g.fillRect(28, 11, 1, 1);
  } else {
    g.fillStyle = '#ece6da'; g.fillRect(18, 10, 3, 2); g.fillRect(27, 10 + dy, 3, 2);
    g.fillStyle = cr ? '#000' : '#2a1a10'; g.fillRect(19, 10, cr ? 2 : 1, 2); g.fillRect(28, 10 + dy, cr ? 2 : 1, 2);
  }
  g.fillStyle = o.hair; g.fillRect(18, 8, 3, 1); g.fillRect(27, 8 + dy, 3, 1);
  g.fillStyle = 'rgba(0,0,0,.28)'; g.fillRect(23, 12, 2, 3);
  if (cr >= 2) { g.fillStyle = '#000'; g.fillRect(19, 17, 11, 3); g.fillStyle = '#d8d0c0'; g.fillRect(20, 17, 1, 1); g.fillRect(24, 17, 1, 1); g.fillRect(28, 17, 1, 1); }
  else { g.fillStyle = '#7a3a34'; g.fillRect(21, 17, 6, 1); }
  grainFill(g, W, Hh, 22);
}
// Rostro del monstruo (64x32): pálido, cuencas vacías, boca imposible.
function drawMonsterFace(F, open, glitch) {
  const g = F.g, W = F.w, Hh = F.h;
  g.fillStyle = '#4a4038'; g.fillRect(0, 0, W, Hh);
  g.fillStyle = '#d6ccb4'; g.fillRect(19, 0, 26, Hh);
  g.fillStyle = 'rgba(80,60,50,.4)'; g.fillRect(19, 0, 2, Hh); g.fillRect(43, 0, 2, Hh);
  for (let i = 0; i < 18; i++) { g.fillStyle = 'rgba(90,70,60,.35)'; g.fillRect((19 + rand(0, 26)) | 0, rand(0, Hh) | 0, 1 + (rand(0, 3) | 0), 1); }
  g.fillStyle = '#0c0a09'; for (let x = 0; x < W; x++) { if (x >= 19 && x < 45) continue; g.fillRect(x, 0, 1, 4 + ((hash3(x, 1, 2) * 16) | 0)); }
  g.fillStyle = '#000'; g.fillRect(24, 8, 6, 7); g.fillRect(34, 7, 6, 8);
  g.fillStyle = '#5a0d08'; g.fillRect(24, 15, 6, 1); g.fillRect(34, 15, 6, 1);
  g.fillStyle = '#fff'; g.fillRect(26, 10, 1, 1); g.fillRect(37, 11, 1, 1);
  g.fillStyle = 'rgba(0,0,0,.6)'; g.fillRect(26, 15, 1, 6); g.fillRect(37, 16, 1, 5); g.fillRect(31, 2, 1, 5); g.fillRect(32, 6, 1, 2);
  g.fillStyle = '#1a1210'; g.fillRect(30, 16, 1, 2); g.fillRect(33, 16, 1, 2);
  if (open) {
    g.fillStyle = '#000'; g.fillRect(23, 19, 18, 13);
    g.fillStyle = '#3a0605'; g.fillRect(25, 23, 14, 6);
    g.fillStyle = '#e8e0c8';
    for (let x = 23; x < 41; x += 2) { g.fillRect(x, 19, 1, 2 + ((hash3(x, 3, 4) * 2) | 0)); g.fillRect(x + 1, 29 - ((hash3(x, 5, 6) * 2) | 0), 1, 3); }
  } else {
    g.fillStyle = '#000'; g.fillRect(22, 21, 20, 2); g.fillRect(21, 20, 1, 1); g.fillRect(42, 19, 1, 2); g.fillRect(43, 18, 1, 1);
    g.fillStyle = '#e8e0c8'; for (let x = 23; x < 41; x += 2) g.fillRect(x, 21, 1, 1);
  }
  grainFill(g, W, Hh, 26);
  if (glitch > 0) {
    const n = ((glitch * 8) | 0) + 1;
    for (let i = 0; i < n; i++) {
      const y = rand(0, Hh - 1) | 0, hh = 1 + (rand(0, 4) | 0), dx = rand(-6, 6) | 0;
      const img = g.getImageData(0, y, W, Math.min(hh, Hh - y)); g.putImageData(img, dx, y);
    }
  }
  F.t.needsUpdate = true;
}
const monFace = makeCanvas(64, 32), scareFace = makeCanvas(64, 32);
drawMonsterFace(monFace, false, 0); drawMonsterFace(scareFace, true, 0.3);

// Cartel de persona desaparecida (cara pixelada; versión "corrupta" tras el bucle)
function posterTex(creepy) {
  const P = makeCanvas(48, 64), g = P.g;
  g.fillStyle = '#e9e4d4'; g.fillRect(0, 0, 48, 64);
  g.fillStyle = '#8a1410'; g.fillRect(0, 0, 48, 9);
  g.fillStyle = '#f4ecd8'; g.font = 'bold 7px Arial'; g.textAlign = 'center'; g.fillText('DESAPARECIDA', 24, 7);
  const tmp = makeCanvas(48, 24);
  drawFace(tmp.g, { skin: '#c89474', hair: '#1a1410', creepy: creepy ? 2 : 0, seed: 7 });
  g.fillStyle = '#222'; g.fillRect(11, 12, 26, 30);
  g.drawImage(tmp.c, 14, 0, 20, 24, 12, 13, 24, 28);
  g.fillStyle = '#222'; g.font = 'bold 6px Arial'; g.fillText(creepy ? 'HOY 11:11' : '¿LA HAS VISTO?', 24, 50);
  g.fillStyle = 'rgba(0,0,0,.45)'; g.fillRect(8, 54, 32, 1); g.fillRect(8, 57, 26, 1); g.fillRect(8, 60, 30, 1);
  if (creepy) { g.fillStyle = 'rgba(120,10,8,.7)'; g.fillRect(20, 40, 1, 14); g.fillRect(27, 40, 1, 10); }
  grainFill(g, 48, 64, 24);
  P.t.needsUpdate = true; return P.t;
}
const posterA = posterTex(false), posterB = posterTex(true);

function textPlane(text, w, h, opt) {
  opt = opt || {};
  const cw = 256, ch = Math.max(16, Math.round(256 * h / w));
  const size = opt.size || 0.5;
  const t = canvasTex(cw, ch, g => {
    if (opt.bg) { g.fillStyle = opt.bg; g.fillRect(0, 0, cw, ch); }
    if (opt.border) { g.strokeStyle = opt.border; g.lineWidth = 6; g.strokeRect(3, 3, cw - 6, ch - 6); }
    g.fillStyle = opt.fg || '#fff';
    g.font = (opt.weight || 'bold') + ' ' + Math.round(ch * size) + 'px ' + (opt.font || 'Arial, sans-serif');
    g.textAlign = 'center'; g.textBaseline = 'middle';
    const lines = text.split('\n');
    lines.forEach((l, i) => g.fillText(l, cw / 2, ch / 2 + (i - (lines.length - 1) / 2) * ch * size * 1.15));
    if (opt.rough) grainFill(g, cw, ch, 30);
  });
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  const mat = psx(opt.lit
    ? new THREE.MeshLambertMaterial({ map: t, transparent: !!opt.transparent })
    : new THREE.MeshBasicMaterial({ map: t, transparent: !!opt.transparent }));
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat); m.userData.noCast = true; return m;
}
// Orientaciones para planos pegados a paredes
const FACE = { nx: -Math.PI / 2, px: Math.PI / 2, nz: Math.PI, pz: 0 };

// =====================================================================
// MATERIALES
// =====================================================================
const M_wall = new THREE.MeshLambertMaterial({ map: wallTex });
const M_wall2 = new THREE.MeshLambertMaterial({ map: wallTex2 });
const M_floor = new THREE.MeshLambertMaterial({ map: floorTex });
const M_floor2 = new THREE.MeshLambertMaterial({ map: floorTex, color: 0x77746c });
const M_ceil = new THREE.MeshLambertMaterial({ map: ceilTex });
const M_ceil2 = new THREE.MeshLambertMaterial({ map: ceilTex, color: 0x6a6862 });
const M_locker = new THREE.MeshLambertMaterial({ map: lockerTex });
const M_wood = new THREE.MeshLambertMaterial({ color: 0x6b4a30, map: clothTex });
const M_woodDark = new THREE.MeshLambertMaterial({ color: 0x3e2a1c, map: clothTex });
const M_metal = new THREE.MeshLambertMaterial({ color: 0x4a4d50, map: clothTex });
const M_metalLight = new THREE.MeshLambertMaterial({ color: 0x8a8f94 });
const M_black = new THREE.MeshLambertMaterial({ color: 0x151515 });
const M_door = new THREE.MeshLambertMaterial({ color: 0x8a6a48, map: clothTex });
const M_emDoor = new THREE.MeshLambertMaterial({ color: 0x6d2a22, map: clothTex });
const M_paper = new THREE.MeshLambertMaterial({ color: 0xf3f0e6, side: THREE.DoubleSide });
const M_panelMain = new THREE.MeshLambertMaterial({ color: 0xffffff, emissive: 0xfff8ee });
const M_panelFlick = new THREE.MeshLambertMaterial({ color: 0xffffff, emissive: 0xfff8ee });
const M_panelOffice = new THREE.MeshLambertMaterial({ color: 0xffffff, emissive: 0xfff8ee });
const M_panelLoop = new THREE.MeshLambertMaterial({ color: 0xffffff, emissive: 0x000000 });
const M_panelOff = new THREE.MeshLambertMaterial({ color: 0x3a3a38, emissive: 0x050505 });
const M_emLamp = new THREE.MeshBasicMaterial({ color: 0xff2a14 });
const M_glass = new THREE.MeshBasicMaterial({ color: 0xe9f3ef });
const M_warm = new THREE.MeshBasicMaterial({ color: 0xffd9a0 });
const M_led = new THREE.MeshBasicMaterial({ color: 0xff1a0a });      // lector de la salida de emergencia
const M_swLed = new THREE.MeshBasicMaterial({ color: 0xff1a0a });    // LED del panel eléctrico
const lam = c => psx(new THREE.MeshLambertMaterial({ color: c, map: clothTex }));

function box(w, h, d, mat, x, y, z, parent) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.position.set(x, y, z); (parent || scene).add(m); return m;
}
// Geometría facetada (normales planas) y deformada: look low-poly orgánico
function facet(geo) { const g2 = geo.index ? geo.toNonIndexed() : geo; g2.computeVertexNormals(); return g2; }
function lumpy(geo, amt) {
  const p = geo.attributes.position, r = v => Math.round(v * 1e4) / 1e4;
  for (let i = 0; i < p.count; i++) {
    const x = r(p.getX(i)), y = r(p.getY(i)), z = r(p.getZ(i));
    p.setXYZ(i, x + (hash3(x, y, z) - 0.5) * amt, y + (hash3(y, z, x) - 0.5) * amt, z + (hash3(z, x, y) - 0.5) * amt);
  }
  p.needsUpdate = true; return geo;
}
function part(geo, mat, parent, x, y, z) { const m = new THREE.Mesh(facet(geo), mat); m.position.set(x, y, z); parent.add(m); return m; }

// =====================================================================
// GEOMETRÍA DEL NIVEL
// =====================================================================
// Coordenadas (metros). El jugador empieza en (0, -1.2) mirando hacia -Z.
//  Pasillo principal M ...... x[-2,2]   z[-40,2]   (entrada principal en z=2)
//  Oficina del profesor ..... x[-9,-2]  z[-40,-30] (puerta en x=-2, z[-36,-34])
//  Pasillo B (BUCLE) ........ x[-1.5,1.5] z[-76,-40] (puerta en z=-40); 3 módulos de 12 m
//  Ruta de emergencia (puerta en x=2, z[-11,-9]):
//    A  x[2,48]  z[-12,-8] → este · B x[44,48] z[-60,-12] → sur · C x[4,48] z[-64,-60] → oeste
//    D  x[4,8]   z[-110,-64] → sur (las luces revientan) · E x[4,60] z[-114,-110] → este
//  Vestíbulo final .......... x[60,72] z[-120,-104] (puerta en x=60; cristal en x=72, z[-116,-108])
//  Ciudad exterior .......... x>72 (vacía, iluminada solo por la luna)
function wall(x1, z1, x2, z2, mat) {
  const dx = x2 - x1, dz = z2 - z1, L = Math.hypot(dx, dz);
  const geo = scaleUV(new THREE.BoxGeometry(L, H, 0.2, Math.max(1, Math.ceil(L)), 3, 1), L / 3, 1);
  const m = new THREE.Mesh(geo, mat || M_wall);
  m.position.set((x1 + x2) / 2, H / 2, (z1 + z2) / 2);
  m.rotation.y = -Math.atan2(dz, dx);
  scene.add(m); return m;
}
function slab(x1, x2, z1, z2, fMat, cMat) {
  const w = x2 - x1, d = z2 - z1, sx = Math.max(1, Math.ceil(w)), sz = Math.max(1, Math.ceil(d));
  const f = new THREE.Mesh(scaleUV(new THREE.PlaneGeometry(w, d, sx, sz), w / 1.2, d / 1.2), fMat);
  f.rotation.x = -Math.PI / 2; f.position.set((x1 + x2) / 2, 0, (z1 + z2) / 2); scene.add(f);
  const c = new THREE.Mesh(scaleUV(new THREE.PlaneGeometry(w, d, sx, sz), w / 0.6, d / 0.6), cMat);
  c.rotation.x = Math.PI / 2; c.position.set((x1 + x2) / 2, H, (z1 + z2) / 2); scene.add(c);
}

// --- pasillo principal y oficina
slab(-2, 2, -40, 2, M_floor, M_ceil);
slab(-9, -2, -40, -30, M_floor, M_ceil);
wall(-2, 2, -2, -34); wall(-2, -36, -2, -40);
wall(2, 2, 2, -9); wall(2, -11, 2, -40);
wall(-2, -40, -1, -40); wall(1, -40, 2, -40);          // fondo, con hueco hacia el Pasillo B
wall(-2, 2, 2, 2);
wall(-9, -30, -9, -40); wall(-9, -30, -2, -30); wall(-9, -40, -2, -40);
// dinteles sobre puertas
box(0.2, H - 2.25, 2, M_wall, -2, 2.25 + (H - 2.25) / 2, -35);
box(0.2, H - 2.25, 2, M_wall, 2, 2.25 + (H - 2.25) / 2, -10);
box(2, H - 2.25, 0.2, M_wall, 0, 2.25 + (H - 2.25) / 2, -40);
box(0.2, H - 2.3, 2, M_wall2, 60, 2.3 + (H - 2.3) / 2, -112);

// --- Pasillo B (el bucle)
slab(-1.5, 1.5, -76, -40, M_floor, M_ceil);
wall(-1.5, -40, -1.5, -76); wall(1.5, -40, 1.5, -76); wall(-1.5, -76, 1.5, -76);

// --- ruta de emergencia: rectángulos de geometría (no se solapan)
const R_M = { x1: -2, x2: 2, z1: -40, z2: 2, g: 'em' };
const ROUTE = [
  { x1: 2, x2: 48, z1: -12, z2: -8, g: 'em' },     // A
  { x1: 44, x2: 48, z1: -60, z2: -12, g: 'em' },   // B
  { x1: 4, x2: 48, z1: -64, z2: -60, g: 'em' },    // C
  { x1: 4, x2: 8, z1: -110, z2: -64, g: 'em' },    // D
  { x1: 4, x2: 60, z1: -114, z2: -110, g: 'em' },  // E
];
const R_SAFE = { x1: 60, x2: 72, z1: -120, z2: -104, g: 'safe' };
const GLASS_X = 72;
const D_GLASS = { x1: 71, x2: 73, z1: -116, z2: -108, door: true };   // hueco del cristal (no caminable)
const flags = { emDoorOpen: false, safeDoorOpen: true, officeOpen: true, sDoorOpen: false, knowsPanel: false };
const D_EM = { x1: 1, x2: 3, z1: -11, z2: -9, door: true, on: () => flags.emDoorOpen };
const D_SAFE = { x1: 59, x2: 61, z1: -113, z2: -111, door: true, on: () => flags.safeDoorOpen };
const D_OFF = { x1: -3, x2: -1, z1: -36, z2: -34, door: true, on: () => flags.officeOpen };
const D_SB = { x1: -1, x2: 1, z1: -41, z2: -39, door: true, on: () => flags.sDoorOpen };
const R_SB = { x1: -1.5, x2: 1.5, z1: -76, z2: -40 };

// Paredes automáticas de la ruta: cada borde se vuelve pared salvo conexiones/puertas.
(function buildRouteWalls() {
  const gen = [...ROUTE, R_SAFE], cut = [R_M, ...ROUTE, R_SAFE, D_EM, D_SAFE, D_GLASS], done = [];
  const subtract = (iv, a, b) => {
    const out = [];
    for (const [s, e] of iv) { if (b <= s || a >= e) { out.push([s, e]); continue; } if (a > s) out.push([s, a]); if (b < e) out.push([b, e]); }
    return out;
  };
  for (const R of gen) {
    const edges = [
      { ax: 'z', c: R.z1, a: R.x1, b: R.x2, off: -0.1 }, { ax: 'z', c: R.z2, a: R.x1, b: R.x2, off: 0.1 },
      { ax: 'x', c: R.x1, a: R.z1, b: R.z2, off: -0.1 }, { ax: 'x', c: R.x2, a: R.z1, b: R.z2, off: 0.1 },
    ];
    for (const E of edges) {
      let iv = [[E.a, E.b]]; const p = E.c + E.off;
      for (const O of cut) {
        if (O === R || !(O.door || O.g === R.g)) continue;
        if (E.ax === 'z') { if (p > O.z1 && p < O.z2) iv = subtract(iv, O.x1, O.x2); }
        else { if (p > O.x1 && p < O.x2) iv = subtract(iv, O.z1, O.z2); }
      }
      for (const D of done) if (D.ax === E.ax && Math.abs(D.c - E.c) < 1e-6) iv = subtract(iv, D.a, D.b);
      for (const [s, e] of iv) {
        if (e - s < 0.05) continue;
        const wm = R.g === 'safe' ? M_wall : M_wall2;
        if (E.ax === 'z') wall(s, E.c, e, E.c, wm); else wall(E.c, s, E.c, e, wm);
        done.push({ ax: E.ax, c: E.c, a: s, b: e });
      }
    }
    if (R.g === 'safe') slab(R.x1, R.x2, R.z1, R.z2, M_floor, M_ceil); else slab(R.x1, R.x2, R.z1, R.z2, M_floor2, M_ceil2);
  }
})();

// =====================================================================
// COLISIONES: zonas caminables
// =====================================================================
const walkRects = [
  R_M, D_OFF, { x1: -9, x2: -2, z1: -40, z2: -30 }, D_EM, D_SB, R_SB,
  { x1: 2, x2: 48, z1: -12, z2: -8 },
  { x1: 44, x2: 48, z1: -64, z2: -8 },
  { x1: 4, x2: 48, z1: -64, z2: -60 },
  { x1: 4, x2: 8, z1: -114, z2: -60 },
  { x1: 4, x2: 60, z1: -114, z2: -110 },
  D_SAFE, R_SAFE,
];
const blocks = [];
function addBlock(x1, x2, z1, z2) { blocks.push({ x1, x2, z1, z2 }); }
const PR = 0.3;
function walkable(x, z) {
  let ok = false;
  for (const R of walkRects) {
    if (R.on && !R.on()) continue;
    if (x > R.x1 + PR && x < R.x2 - PR && z > R.z1 + PR && z < R.z2 - PR) { ok = true; break; }
  }
  if (!ok) return false;
  for (const B of blocks) if (x > B.x1 - PR && x < B.x2 + PR && z > B.z1 - PR && z < B.z2 + PR) return false;
  return true;
}

// =====================================================================
// ILUMINACIÓN (puntual, sombras duras)
// =====================================================================
function shadowCfg(l, size, far, bias) {
  l.castShadow = true; l.shadow.mapSize.set(size, size);
  l.shadow.camera.near = 0.15; l.shadow.camera.far = far; l.shadow.bias = bias || -0.004;
}
const amb = new THREE.AmbientLight(0xffffff, 0.45); scene.add(amb);
const hemi = new THREE.HemisphereLight(0xf6f3ea, 0x605a50, 0.5); scene.add(hemi);
const lights = [];
function pLight(x, y, z, color, p1, p2, dist, flick) {
  const l = new THREE.PointLight(color, p1, dist, 1.6); l.position.set(x, y, z); scene.add(l);
  const o = { l, p1, p2, base: p1, fl: 0, fl2: flick || 0, ft: 0, cur: p1 }; lights.push(o); return o;
}
pLight(0, 2.9, -4, 0xfff4e4, 0.8, 0.0, 18);
const mainFlickLight = pLight(0, 2.9, -17, 0xfff4e4, 0.9, 0.38, 18, 0.55);
pLight(0, 2.9, -30, 0xfff4e4, 0.8, 0.0, 18);
const officeLight = pLight(-5.5, 2.9, -35, 0xfff0dd, 0.85, 0.0, 12);
const safeLight = pLight(65, 2.8, -112, 0xdfe6f5, 0.75, 0.75, 13);

// Ruta de emergencia: "anclas" de luz roja servidas por un pool fijo de 6 luces.
const anchors = [];
function anchor(x, z, fl) {
  const lamp = box(0.4, 0.1, 0.4, M_emLamp, x, H - 0.06, z);
  anchors.push({ x, z, base: 0.95, fl: fl, cur: 0.95, ft: 0, dead: false, lamp });
}
[[8, 0.1], [20, 0.35], [32, 0.15], [44, 0.3]].forEach(([x, f]) => anchor(x, -10, f));
[[-22, 0.25], [-34, 0.45], [-46, 0.2], [-57, 0.3]].forEach(([z, f]) => anchor(46, z, f));
[[38, 0.2], [26, 0.4], [14, 0.25]].forEach(([x, f]) => anchor(x, -62, f));
[-70, -80, -90, -100].forEach(z => anchor(6, z, 0.3));
[[6, 0.3], [16, 0.5], [27, 0.35], [38, 0.5], [48, 0.2], [57, 0.1]].forEach(([x, f]) => anchor(x, -112, f));
const D_ANCH = anchors.filter(a => a.x === 6 && a.z <= -70 && a.z >= -100);
const pool = [];
for (let i = 0; i < 6; i++) { const l = new THREE.PointLight(0xff2a18, 0, 13, 1.6); scene.add(l); pool.push(l); }
let routeLit = false;
function poolTick(dt, px, pz) {
  for (const a of anchors) {
    a.ft -= dt;
    if (a.ft < 0) { a.ft = rand(0.04, 0.3); a.cur = a.dead ? 0 : (Math.random() < a.fl ? a.base * rand(0, 0.25) : a.base * rand(0.85, 1.05)); }
  }
  const s = anchors.slice().sort((p, q) => Math.hypot(p.x - px, p.z - pz) - Math.hypot(q.x - px, q.z - pz));
  for (let i = 0; i < pool.length; i++) { pool[i].position.set(s[i].x, 2.7, s[i].z); pool[i].intensity = routeLit ? s[i].cur : 0; }
}

// Luces del Pasillo B: dos luces que siguen a los centros de módulo más cercanos
const loopA = new THREE.PointLight(0xfff4e4, 0, 11, 1.6); scene.add(loopA);
const loopB = new THREE.PointLight(0xfff4e4, 0, 11, 1.6); scene.add(loopB);
const LT = { base: 0.8, fl: 0, cur: 0.8, ft: 0 };
const LOOP_CENTERS = [-46, -58, -70];

// Luz de luna (solo se enciende en el vestíbulo final)
const moonLight = new THREE.DirectionalLight(0x9fb4dc, 0);
moonLight.position.set(10, 110, -40); moonLight.target.position.set(110, 0, -112);
scene.add(moonLight); scene.add(moonLight.target);

// Linterna del teléfono
const flash = new THREE.SpotLight(0xfff1dc, 0, 22, 0.5, 0.35, 1.3);
flash.position.set(0.18, -0.12, 0.05);
const flashTarget = new THREE.Object3D(); flashTarget.position.set(0.05, -0.1, -6);
camera.add(flash); camera.add(flashTarget); flash.target = flashTarget;
// Sombras duras SOLO en la linterna: con MeshLambert la máscara de sombra es global,
// así que una sola luz con sombras da contraste marcado sin apagar las demás.
shadowCfg(flash, 1024, 22, -0.002);
let flashOn = false, flashAvail = false, flashUsed = false;

// Paneles fluorescentes
function panel(x, z, rotY, mat) {
  const p = box(0.55, 0.05, 1.25, mat, x, H - 0.03, z); p.rotation.y = rotY || 0; p.userData.noCast = true; return p;
}
for (let z = 0; z >= -38; z -= 4) panel(0, z, 0, z === -16 ? M_panelFlick : M_panelMain);
panel(-5.5, -33, Math.PI / 2, M_panelOffice); panel(-5.5, -37, Math.PI / 2, M_panelOffice);
for (let x = 6; x <= 46; x += 5) panel(x, -10, Math.PI / 2, M_panelOff);
for (let z = -16; z >= -58; z -= 5) panel(46, z, 0, M_panelOff);
for (let x = 42; x >= 8; x -= 5) panel(x, -62, Math.PI / 2, M_panelOff);
for (let z = -67; z >= -108; z -= 5) panel(6, z, 0, M_panelOff);
for (let x = 11; x <= 56; x += 5) panel(x, -112, Math.PI / 2, M_panelOff);
const M_lobbyLamp = new THREE.MeshBasicMaterial({ color: 0xe6ecf8 });
box(0.6, 0.06, 1.3, M_lobbyLamp, 65, H - 0.03, -112).userData.noCast = true;

// =====================================================================
// UTILERÍA DEL ESCENARIO
// =====================================================================
// --- Entrada principal (z=2)
box(3.6, 0.15, 0.2, M_metal, 0, 2.55, 1.85);
box(0.12, 2.55, 0.2, M_metal, -1.8, 1.27, 1.85);
box(0.12, 2.55, 0.2, M_metal, 1.8, 1.27, 1.85);
box(0.1, 2.55, 0.2, M_metal, 0, 1.27, 1.85);
[-0.9, 0.9].forEach(x => {
  const g = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 2.3), M_glass); g.position.set(x, 1.3, 1.86); g.rotation.y = Math.PI; scene.add(g);
  box(1.1, 0.07, 0.07, M_metalLight, x, 1.05, 1.72);
});
const exitSign1 = textPlane('SALIDA PRINCIPAL', 1.6, 0.3, { bg: '#0f5a2a', fg: '#e9ffe9', size: 0.55 });
exitSign1.position.set(0, 2.85, 1.88); exitSign1.rotation.y = Math.PI; scene.add(exitSign1);

// --- Casilleros
function lockers(x, z1, z2, side) {
  const len = Math.abs(z2 - z1);
  const geo = scaleUV(new THREE.BoxGeometry(0.42, 1.9, len, 1, 2, Math.ceil(len / 0.6)), len / 0.45, 1);
  const m = new THREE.Mesh(geo, M_locker);
  const cx = side < 0 ? x + 0.21 : x - 0.21;
  m.position.set(cx, 0.95, (z1 + z2) / 2); scene.add(m);
  addBlock(Math.min(x, x - side * 0.42), Math.max(x, x - side * 0.42), Math.min(z1, z2), Math.max(z1, z2));
}
lockers(-1.9, -3, -15, -1); lockers(-1.9, -20, -30, -1);
lockers(1.9, -13.5, -24, 1); lockers(1.9, -26, -30.5, 1);

const board = new THREE.Mesh(new THREE.PlaneGeometry(1.9, 0.95), new THREE.MeshLambertMaterial({ map: boardTex }));
board.position.set(-1.88, 1.55, -17.5); board.rotation.y = FACE.px; board.userData.noCast = true; scene.add(board);
function decoDoor(x, z, face, label, mat) {
  const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = face; scene.add(g);
  box(1.1, 2.15, 0.06, mat || M_door, 0, 1.075, 0.02, g);
  box(0.06, 0.06, 0.12, M_metalLight, 0.42, 1.0, 0.08, g);
  box(0.4, 0.55, 0.03, M_black, 0, 1.6, 0.06, g);
  if (label) { const s = textPlane(label, 0.6, 0.18, { bg: '#e8e2d2', fg: '#222', size: 0.6, lit: true }); s.position.set(0, 2.3, 0.07); g.add(s); }
  return g;
}
decoDoor(1.9, -4.8, FACE.nx, 'Aula 101');
decoDoor(1.9, -33, FACE.nx, 'Aula 103');
decoDoor(-1.9, -38.5, FACE.px, 'Aula 102');
box(0.5, 0.9, 0.4, M_metalLight, 1.7, 0.45, -31.6); addBlock(1.4, 2, -31.85, -31.35);
box(0.4, 0.7, 0.4, M_black, -1.7, 0.35, -16.6); addBlock(-2, -1.5, -16.8, -16.4);

// --- Puerta de la oficina (abierta) + rótulo
const OFF_OPEN = 2.2, OFF_CLOSED = Math.PI * 1.5;
const offLeaf = new THREE.Group(); offLeaf.position.set(-2, 0, -36); offLeaf.rotation.y = OFF_OPEN; scene.add(offLeaf);
box(1.95, 2.2, 0.06, M_door, 0.98, 1.1, 0, offLeaf);
const offSign = textPlane('Oficina 104\nProf. M. Andrade', 0.8, 0.32, { bg: '#e8e2d2', fg: '#1d1d1d', size: 0.36, lit: true });
offSign.position.set(-1.88, 2.42, -35); offSign.rotation.y = FACE.px; scene.add(offSign);

// --- Puerta del Pasillo B (cerrada en la fase normal)
const sLeaf = new THREE.Group(); sLeaf.position.set(-1, 0, -40); sLeaf.rotation.y = 0; scene.add(sLeaf);
box(1.98, 2.22, 0.06, M_door, 0.99, 1.11, 0, sLeaf);
box(0.06, 0.06, 0.14, M_metalLight, 1.75, 1.0, 0, sLeaf);
const sSign = textPlane('PASILLO B', 0.9, 0.24, { bg: '#e8e2d2', fg: '#1d1d1d', size: 0.55, lit: true });
sSign.position.set(0, 2.62, -39.88); scene.add(sSign);

// --- Puerta de emergencia (bloqueada: lector electrónico sin energía)
const emLeaf = new THREE.Group(); emLeaf.position.set(2, 0, -11); emLeaf.rotation.y = -Math.PI / 2; scene.add(emLeaf);
box(1.98, 2.22, 0.08, M_emDoor, 0.99, 1.11, 0, emLeaf);
box(1.2, 0.07, 0.07, M_metalLight, 1.0, 1.05, -0.08, emLeaf);
const emSign = textPlane('SALIDA DE EMERGENCIA', 1.4, 0.26, { bg: '#0f5a2a', fg: '#e9ffe9', size: 0.5 });
emSign.position.set(1.88, 2.55, -10); emSign.rotation.y = FACE.nx; scene.add(emSign);
box(0.05, 0.24, 0.15, M_metal, 1.88, 1.3, -11.45);
box(0.03, 0.05, 0.05, M_led, 1.85, 1.38, -11.45).userData.noCast = true;

// --- Oficina: escritorio, estantería, silla, bandeja
box(1.9, 0.06, 0.9, M_wood, -6.5, 0.76, -37.6);
box(0.06, 0.74, 0.86, M_woodDark, -7.4, 0.37, -37.6); box(0.06, 0.74, 0.86, M_woodDark, -5.6, 0.37, -37.6);
box(1.84, 0.6, 0.04, M_woodDark, -6.5, 0.45, -38.0);
addBlock(-7.5, -5.5, -38.1, -37.1);
box(0.55, 0.38, 0.05, M_black, -6.9, 1.02, -37.95); box(0.12, 0.2, 0.12, M_black, -6.9, 0.85, -37.9);
for (let i = 0; i < 4; i++) { const p = box(0.24, 0.012, 0.32, M_paper, -7.15 + rand(-0.05, 0.05), 0.795 + i * 0.012, -37.45); p.rotation.y = rand(-0.3, 0.3); }
box(0.4, 0.05, 0.3, M_metal, -5.85, 0.81, -37.45);   // bandeja de entregas
const deskPaper = box(0.22, 0.008, 0.3, M_paper, -5.85, 0.84, -37.45); deskPaper.visible = false;
const trayGlow = new THREE.Mesh(new THREE.RingGeometry(0.28, 0.32, 12), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.4, side: THREE.DoubleSide }));
trayGlow.rotation.x = -Math.PI / 2; trayGlow.position.set(-5.85, 0.84, -37.45); scene.add(trayGlow);
const note = textPlane('Salí un momento.\nDejen los trabajos\nen la bandeja.\n— M.A.', 0.18, 0.16, { bg: '#f7ec8c', fg: '#333', size: 0.15, weight: 'normal', font: 'Georgia', lit: true });
note.rotation.x = -Math.PI / 2; note.rotation.z = 0.2; note.position.set(-6.4, 0.795, -37.3); scene.add(note);
box(0.5, 0.05, 0.5, M_black, -6.5, 0.48, -36.8); box(0.5, 0.6, 0.05, M_black, -6.5, 0.8, -36.55);
const shelf = new THREE.Mesh(new THREE.BoxGeometry(0.4, 2.2, 4), [M_woodDark, new THREE.MeshLambertMaterial({ map: bookTex }), M_woodDark, M_woodDark, M_woodDark, M_woodDark]);
shelf.position.set(-8.75, 1.1, -33.5); scene.add(shelf); addBlock(-9, -8.5, -35.5, -31.5);
const diploma = textPlane('UNIVERSIDAD\nDiploma', 0.6, 0.45, { bg: '#efe6cf', fg: '#5a4020', size: 0.18, font: 'Georgia', border: '#3a2a10', lit: true });
diploma.position.set(-5.5, 1.8, -30.12); diploma.rotation.y = FACE.nz; scene.add(diploma);

// --- Ruta de emergencia: tuberías, señales, obstáculos
const pipeMat = new THREE.MeshLambertMaterial({ color: 0x5a5550, map: clothTex });
function pipe(x1, z1, x2, z2, r) {
  const L = Math.hypot(x2 - x1, z2 - z1);
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, L, 6, Math.ceil(L)), pipeMat);
  m.rotation.z = Math.PI / 2; m.rotation.y = -Math.atan2(z2 - z1, x2 - x1);
  m.position.set((x1 + x2) / 2, 2.95, (z1 + z2) / 2); scene.add(m);
}
pipe(2, -8.4, 48, -8.4, 0.07); pipe(47.6, -8, 47.6, -64, 0.09); pipe(48, -63.6, 4, -63.6, 0.08);
pipe(4.4, -64, 4.4, -114, 0.09); pipe(4, -113.6, 60, -113.6, 0.07);
function arrowSign(txt, x, z, face, y) { const s = textPlane(txt, 1.3, 0.3, { bg: '#0f5a2a', fg: '#e9ffe9', size: 0.5 }); s.position.set(x, y || 2.4, z); s.rotation.y = face; scene.add(s); }
function scrawlText(txt, x, z, face, w, y) {
  const s = textPlane(txt, w || 2.2, 0.6, { fg: '#7a0d0a', size: 0.55, font: 'Georgia', weight: 'italic bold', transparent: true, lit: true });
  s.position.set(x, y || 1.6, z); s.rotation.y = face; scene.add(s); return s;
}
arrowSign('SALIDA  →', 12, -8.12, FACE.nz);
arrowSign('SALIDA  →', 30, -8.12, FACE.nz);
arrowSign('SALIDA  ↓', 47.88, -16, FACE.nx);
arrowSign('ZONA SEGURA ↓', 44.12, -36, FACE.px);
scrawlText('NO MIRES ATRÁS', 44.12, -28, FACE.px);
arrowSign('←  SALIDA', 46, -63.88, FACE.pz);
scrawlText('¿DÓNDE ESTÁN?', 28, -60.12, FACE.nz);
arrowSign('SALIDA  →', 4.12, -63.2, FACE.px, 2.75);
scrawlText('NO PARES', 4.12, -84, FACE.px, 1.6);
scrawlText('CORRE', 7.88, -96, FACE.nx, 1.4);
arrowSign('SALIDA  →', 6, -113.88, FACE.pz);
const safeSign = textPlane('VESTÍBULO', 1.2, 0.3, { bg: '#0f5a2a', fg: '#e9ffe9', size: 0.6 });
safeSign.position.set(59.88, 2.6, -112); safeSign.rotation.y = FACE.nx; scene.add(safeSign);
decoDoor(20, -8.1, FACE.nz, 'Cuarto eléctrico', M_metal);
decoDoor(33, -11.9, FACE.pz, 'Bodega', M_metal);
decoDoor(47.9, -46, FACE.nx, 'Mantenimiento', M_metal);
decoDoor(30, -63.9, FACE.pz, 'Laboratorio 3', M_metal);
decoDoor(7.9, -76, FACE.nx, 'Archivo', M_metal);
decoDoor(4.1, -61.6, FACE.px, null, M_emDoor);     // salida falsa tapiada
{ const s = textPlane('SALIDA', 0.9, 0.26, { bg: '#0f5a2a', fg: '#e9ffe9', size: 0.6 }); s.position.set(4.12, 2.45, -61.6); s.rotation.y = FACE.px; scene.add(s); }
[0.7, 1.2, 1.75].forEach((y, i) => { const p = box(0.06, 0.16, 1.5, M_woodDark, 4.22, y, -61.6); p.rotation.x = [0.3, -0.25, 0.15][i]; });
{ const s = textPlane('CERRADO', 0.8, 0.2, { bg: '#d8d0b8', fg: '#7a0d0a', size: 0.6, lit: true }); s.position.set(4.28, 1.45, -61.6); s.rotation.y = FACE.px; scene.add(s); }

function obstacle(x1, x2, z1, z2, kind) {
  addBlock(x1, x2, z1, z2);
  const cx = (x1 + x2) / 2, cz = (z1 + z2) / 2, w = x2 - x1, d = z2 - z1;
  if (kind === 'cart') {
    const c = box(w * 0.9, 0.9, d * 0.9, M_metal, cx, 0.5, cz); c.rotation.y = rand(-0.2, 0.2); c.rotation.z = rand(-0.1, 0.1);
    box(w * 0.9, 0.05, d * 0.9, M_metalLight, cx, 0.98, cz);
  } else if (kind === 'chairs') {
    for (let i = 0; i < 4; i++) {
      const g = new THREE.Group(); g.position.set(cx + rand(-w / 3, w / 3), 0.25, cz + rand(-d / 3, d / 3));
      g.rotation.set(rand(-1.4, 1.4), rand(0, 6), rand(-1, 1)); scene.add(g);
      box(0.45, 0.05, 0.45, M_black, 0, 0, 0, g); box(0.45, 0.45, 0.05, M_black, 0, 0.22, -0.2, g);
      box(0.04, 0.45, 0.04, M_metalLight, 0.2, -0.22, 0.2, g); box(0.04, 0.45, 0.04, M_metalLight, -0.2, -0.22, 0.2, g);
    }
  } else {
    const s = box(w, 0.45, d, M_woodDark, cx, 0.23, cz); s.rotation.y = rand(-0.08, 0.08);
    for (let i = 0; i < 6; i++) { const p = box(0.22, 0.01, 0.3, M_paper, cx + rand(-1, 1), 0.006, cz + rand(-1, 1)); p.rotation.y = rand(0, 6); }
  }
}
obstacle(10, 11.6, -12, -10.4, 'cart'); obstacle(22, 23.4, -9.6, -8, 'chairs');
obstacle(31, 32.7, -12, -10.3, 'shelf'); obstacle(38, 39.2, -9.5, -8, 'cart');
obstacle(44, 45.9, -22.6, -21.2, 'chairs'); obstacle(46.1, 48, -33, -31.6, 'cart');
obstacle(44, 45.8, -44.6, -43.2, 'shelf'); obstacle(46.2, 48, -52.4, -51, 'chairs');
obstacle(40, 41.5, -64, -62.2, 'cart'); obstacle(33, 34.4, -61.8, -60, 'chairs');
obstacle(24, 25.8, -64, -62.3, 'shelf'); obstacle(17, 18.3, -61.7, -60, 'cart');
obstacle(4, 5.9, -74, -72.6, 'chairs'); obstacle(6.2, 8, -84, -82.5, 'shelf');
obstacle(4, 5.8, -94, -92.6, 'cart'); obstacle(6.1, 8, -102, -100.6, 'chairs');
obstacle(14, 15.6, -114, -112.2, 'cart'); obstacle(24, 25.4, -111.7, -110, 'chairs');
obstacle(34, 35.8, -114, -112.3, 'shelf'); obstacle(43, 44.3, -111.8, -110, 'cart');
obstacle(51, 52.6, -114, -112.2, 'chairs');
for (const R of ROUTE) {
  const n = Math.round((R.x2 - R.x1) * (R.z2 - R.z1) / 9);
  for (let i = 0; i < n; i++) { const p = box(0.22, 0.008, 0.3, M_paper, rand(R.x1 + 0.3, R.x2 - 0.3), 0.005, rand(R.z1 + 0.3, R.z2 - 0.3)); p.rotation.y = rand(0, 6); }
}

// --- Vestíbulo final: puerta metálica, recepción y la gran puerta de cristal
const SAFE_OPEN = 0.0, SAFE_CLOSED = -Math.PI / 2;
const safeLeaf = new THREE.Group(); safeLeaf.position.set(60, 0, -113); safeLeaf.rotation.y = SAFE_OPEN; scene.add(safeLeaf);
box(2.0, 2.28, 0.12, M_metal, 1.0, 1.14, 0, safeLeaf);
box(0.6, 0.06, 0.08, M_metalLight, 1.6, 1.05, 0.1, safeLeaf);
box(3.2, 1.05, 0.7, M_wood, 64.6, 0.525, -105.4); addBlock(63, 66.2, -105.75, -105.05);       // recepción
box(3.3, 0.06, 0.8, M_woodDark, 64.6, 1.08, -105.4);
for (const z of [-108.6, -115.4]) { box(0.6, H, 0.6, M_wall, 66.5, H / 2, z); addBlock(66.2, 66.8, z - 0.3, z + 0.3); }   // columnas
box(2.4, 0.45, 0.6, M_metal, 64.5, 0.225, -119.2); addBlock(63.3, 65.7, -119.5, -118.9);     // banca
box(2.4, 0.5, 0.08, M_metal, 64.5, 0.7, -119.5);
{ const g = new THREE.Group(); g.position.set(68.4, 0, -117.3); g.rotation.y = 0.8; scene.add(g);   // mochila abandonada
  box(0.34, 0.18, 0.44, lam(0x6a5a3a), 0, 0.09, 0, g); }
const lobbySign = textPlane('SALIDA', 1.1, 0.26, { bg: '#0f5a2a', fg: '#e9ffe9', size: 0.6 });
lobbySign.position.set(GLASS_X - 0.12, 3.05, -112); lobbySign.rotation.y = FACE.nx; scene.add(lobbySign);
// la gran puerta de cristal (8 m), marcos, barras y cadena
const M_glassV = new THREE.MeshBasicMaterial({ color: 0x8fa4c4, transparent: true, opacity: 0.07, depthWrite: false, side: THREE.DoubleSide });
const glassPane = new THREE.Mesh(new THREE.PlaneGeometry(8, 2.9), M_glassV);
glassPane.position.set(GLASS_X, 1.45, -112); glassPane.rotation.y = -Math.PI / 2; glassPane.userData.noCast = true; scene.add(glassPane);
box(0.2, H - 2.9, 8, M_wall, GLASS_X, 2.9 + (H - 2.9) / 2, -112);
box(0.14, 0.1, 8, M_metal, GLASS_X, 2.88, -112); box(0.14, 0.08, 8, M_metal, GLASS_X, 0.04, -112);
for (const z of [-116, -114, -110, -108]) box(0.14, 2.9, 0.09, M_metal, GLASS_X, 1.45, z);
box(0.1, 2.9, 0.025, M_metal, GLASS_X, 1.45, -112);   // junta central de las dos hojas
for (const z of [-112.75, -111.25]) box(0.07, 0.07, 1.1, M_metalLight, GLASS_X - 0.14, 1.05, z);
box(0.05, 0.12, 0.6, M_black, GLASS_X - 0.18, 1.05, -112);
box(0.07, 0.11, 0.08, M_metalLight, GLASS_X - 0.2, 0.95, -112);

// --- Ciudad exterior: vacía, en silencio, iluminada solo por la luna
const asphaltTex = canvasTex(64, 64, (g, w, h) => {
  g.fillStyle = '#2a2c30'; g.fillRect(0, 0, w, h); grainFill(g, w, h, 30);
  g.fillStyle = '#b8b6a8'; g.fillRect(31, 0, 2, 28);                  // línea central discontinua
  g.fillStyle = 'rgba(200,200,190,.5)'; g.fillRect(2, 0, 1, h); g.fillRect(61, 0, 1, h);
});
const concreteTex = canvasTex(32, 32, (g, w, h) => {
  g.fillStyle = '#6c6c68'; g.fillRect(0, 0, w, h); grainFill(g, w, h, 26);
  g.fillStyle = 'rgba(30,30,30,.4)'; g.fillRect(0, 0, w, 1); g.fillRect(0, 0, 1, h);
});
const facadeTex = canvasTex(64, 128, (g, w, h) => {
  g.fillStyle = '#4b505a'; g.fillRect(0, 0, w, h); grainFill(g, w, h, 18);
  for (let y = 4; y < h - 6; y += 10) for (let x = 3; x < w - 6; x += 10) {
    const r = Math.random();
    g.fillStyle = r < 0.08 ? '#46587a' : (r < 0.14 ? '#232a38' : '#0b0f18');
    g.fillRect(x, y, 6, 6);
    if (r < 0.08) { g.fillStyle = 'rgba(190,210,240,.35)'; g.fillRect(x, y, 2, 2); }   // reflejo de luna
  }
});
const M_asphalt = psx(new THREE.MeshLambertMaterial({ map: asphaltTex }));
const M_concrete = psx(new THREE.MeshLambertMaterial({ map: concreteTex }));
const M_facade = psx(new THREE.MeshLambertMaterial({ map: facadeTex }));
const M_facade2 = psx(new THREE.MeshLambertMaterial({ map: facadeTex, color: 0x9aa0b0 }));
function ground(x1, x2, z1, z2, mat, ux, uz) {
  const w = x2 - x1, d = z2 - z1;
  const m = new THREE.Mesh(scaleUV(new THREE.PlaneGeometry(w, d, 2, Math.ceil(d / 20)), ux || w / 4, uz || d / 4), mat);
  m.rotation.x = -Math.PI / 2; m.position.set((x1 + x2) / 2, 0, (z1 + z2) / 2); scene.add(m); return m;
}
ground(72, 78, -330, 110, M_concrete);
ground(78, 92, -330, 110, M_asphalt, 1, 440 / 8);
ground(92, 96, -330, 110, M_concrete);
{ const cr = ground(96, 330, -121, -103, M_asphalt, 1, 234 / 8); cr.rotation.z = Math.PI / 2;    // calle transversal hacia la luna
  cr.geometry = scaleUV(new THREE.PlaneGeometry(18, 234, 2, 12), 18 / 14, 234 / 8); cr.position.set(213, 0.005, -112); }
ground(96, 400, -330, 110, M_concrete, 60, 110).position.y = -0.01;
box(0.25, 0.15, 440, M_concrete, 78, 0.075, -110); box(0.25, 0.15, 440, M_concrete, 92, 0.075, -110);
function building(x, z, w, d, hgt, mat) {
  const geo = scaleUV(new THREE.BoxGeometry(d, hgt, w), Math.max(1, w / 7), Math.max(1, hgt / 14));
  const m = new THREE.Mesh(geo, mat); m.position.set(x + d / 2, hgt / 2, z); scene.add(m); return m;
}
for (let z = -330; z < 110;) {
  const w = rand(12, 26);
  if (z + w > -125 && z < -99) { z = -99; continue; }        // hueco de la calle transversal
  building(rand(97, 100), z + w / 2, w, rand(14, 24), rand(9, 44), M_facade);
  z += w + rand(2, 5);
}
for (let z = -330; z < 110;) {
  const w = rand(18, 34);
  if (z + w > -126 && z < -98) { z = -98; continue; }
  building(rand(125, 160), z + w / 2, w, rand(18, 30), rand(30, 85), M_facade2);
  z += w + rand(3, 8);
}
for (let x = 135; x < 330; x += rand(30, 45)) for (const s of [-1, 1]) building(x, -112 + s * rand(22, 30), rand(14, 22), rand(16, 26), rand(14, 60), M_facade2);
// postes de luz apagados
for (let z = -320; z < 100; z += 24) for (const x of [76.6, 93.4]) {
  if (Math.abs(z + 112) < 8) continue;
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.09, 6.5, 5), M_metal); pole.position.set(x, 3.25, z); scene.add(pole);
  box(1.4, 0.08, 0.1, M_metal, x + (x < 85 ? 0.7 : -0.7), 6.45, z); box(0.5, 0.12, 0.25, M_black, x + (x < 85 ? 1.3 : -1.3), 6.38, z);
}
// luna, halo y estrellas (sin niebla)
const moon = new THREE.Mesh(new THREE.SphereGeometry(16, 14, 10), new THREE.MeshBasicMaterial({ color: 0xe9eef7, fog: false }));
moon.position.set(560, 230, -112); moon.userData.noCast = true; scene.add(moon);
const haloTex = (() => { const H2 = makeCanvas(64, 64), g = H2.g, gr = g.createRadialGradient(32, 32, 4, 32, 32, 32);
  gr.addColorStop(0, 'rgba(210,225,255,0.9)'); gr.addColorStop(0.35, 'rgba(150,175,230,0.25)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64); H2.t.needsUpdate = true; return H2.t; })();
const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTex, blending: THREE.AdditiveBlending, depthWrite: false, fog: false, opacity: 0.8 }));
halo.position.copy(moon.position); halo.scale.set(150, 150, 1); scene.add(halo);
{ const pos = [];
  for (let i = 0; i < 600; i++) {
    const az = rand(-1.4, 1.4), el = rand(0.05, 1.3), r = 800;
    pos.push(70 + r * Math.cos(el) * Math.cos(az), r * Math.sin(el), -112 + r * Math.cos(el) * Math.sin(az));
  }
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  scene.add(new THREE.Points(sg, new THREE.PointsMaterial({ color: 0xcfd8ff, size: 1.4, sizeAttenuation: false, fog: false })));
}

// =====================================================================
// PERSONAS LOW-POLY CON ROSTRO PIXELADO
// =====================================================================
const SKIN = [0xe0b18f, 0xc89474, 0x9a6a4c, 0x6e4a32, 0xf0c8a8];
const SHIRT = [0x2f4a7a, 0x7a2f2f, 0x2f6a4a, 0xd9d4c4, 0x444444, 0x8a6a2a, 0x5a3a7a, 0x1f1f2a, 0xb05a3a];
const PANTS = [0x1f2a3a, 0x2a2a2a, 0x3a3226, 0x4a5a6a];
const HAIR = [0x1a1410, 0x3a2414, 0x5a3a1a, 0x0d0d0d];
const BAGS = [0x1f1f1f, 0x2a3f6a, 0x7a2222, 0x3f5a2a, 0x6a5a3a];
const pick = arr => arr[(Math.random() * arr.length) | 0];
function makePerson(o) {
  o = o || {};
  const g = new THREE.Group();
  const shirt = lam(o.shadow ? 0x161616 : pick(SHIRT)), pants = lam(o.shadow ? 0x0e0e0e : pick(PANTS));
  const skinHex = o.shadow ? 0x2a2622 : pick(SKIN), hairHex = o.shadow ? 0x050505 : pick(HAIR);
  const skin = lam(skinHex), hair = lam(hairHex), shoe = lam(0x161210);
  const F = makeCanvas(48, 24);
  drawFace(F.g, { skin: hex(skinHex), hair: hex(hairHex), creepy: o.creepy || 0, seed: (Math.random() * 100) | 0 });
  F.t.needsUpdate = true;
  const faceMat = psx(o.shadow
    ? new THREE.MeshLambertMaterial({ map: F.t, emissive: 0x2a2a2a, emissiveMap: F.t })
    : new THREE.MeshLambertMaterial({ map: F.t }));
  const legs = [-0.085, 0.085].map(x => {
    const p = new THREE.Group(); p.position.set(x, 0.9, 0); g.add(p);
    part(new THREE.CylinderGeometry(0.075, 0.058, 0.84, 5), pants, p, 0, -0.42, 0);
    part(new THREE.BoxGeometry(0.1, 0.07, 0.22), shoe, p, 0, -0.86, 0.04);
    return p;
  });
  part(new THREE.CylinderGeometry(0.17, 0.15, 0.16, 6).scale(1, 1, 0.65), pants, g, 0, 0.92, 0);
  part(new THREE.CylinderGeometry(0.21, 0.165, 0.6, 6).scale(1, 1, 0.62), shirt, g, 0, 1.25, 0);
  part(new THREE.CylinderGeometry(0.05, 0.055, 0.1, 5), skin, g, 0, 1.58, 0);
  const arms = [-0.25, 0.25].map(x => {
    const p = new THREE.Group(); p.position.set(x, 1.5, 0); g.add(p);
    part(new THREE.CylinderGeometry(0.058, 0.045, 0.58, 5), shirt, p, 0, -0.29, 0);
    part(new THREE.IcosahedronGeometry(0.048, 0), skin, p, 0, -0.62, 0);
    return p;
  });
  // cabeza: cilindro de 8 caras con la textura del rostro centrada al frente (+Z)
  const head = new THREE.Mesh(facet(new THREE.CylinderGeometry(0.115, 0.098, 0.27, 8, 1, false, -Math.PI)), [faceMat, hair, skin]);
  head.position.y = 1.76; g.add(head);
  let bag = null;
  if (!o.shadow && Math.random() < 0.75) { bag = pick(BAGS); part(new THREE.BoxGeometry(0.3, 0.4, 0.14), lam(bag), g, 0, 1.24, -0.19); }
  g.scale.setScalar(o.shadow ? 1.06 : rand(0.92, 1.08));
  scene.add(g);
  return { g, legs, arms, head, bag, t: rand(0, 6) };
}
const npcs = [];
function npcStand(x, z, rotY, phone) { const n = makePerson(); n.g.position.set(x, 0, z); n.g.rotation.y = rotY; n.walk = false; n.phone = phone; if (phone) n.arms[1].rotation.x = -1.9; npcs.push(n); }
function npcWalk(x, z1, z2, z, dir) { const n = makePerson(); n.g.position.set(x, 0, z); n.walk = true; n.z1 = z1; n.z2 = z2; n.dir = dir; n.speed = rand(1.0, 1.45); npcs.push(n); }
npcStand(-1.25, -6.2, Math.PI / 2); npcStand(-0.6, -6.9, -2.2); npcStand(-1.2, -7.6, 0.9);
npcStand(1.3, -20, -Math.PI / 2); npcStand(0.7, -20.8, -0.3);
npcStand(-1.3, -27, Math.PI / 2, true); npcStand(1.25, -36.5, -2.6, true);
npcWalk(-0.7, -31, -3, -12, -1); npcWalk(0.7, -31, -3, -25, 1);
npcWalk(0.55, -31, -3, -8, -1); npcWalk(-0.55, -31, -3, -30, 1);

// =====================================================================
// PASILLO B: 3 módulos idénticos de 12 m (el bucle teletransporta +12 m)
// =====================================================================
const posterMat = psx(new THREE.MeshLambertMaterial({ map: posterA }));
const loopMods = [];
for (let k = 0; k < 3; k++) {
  const z0 = -40 - k * MOD;
  panel(0, z0 - 6, 0, M_panelLoop);
  decoDoor(-1.4, z0 - 3, FACE.px, 'Aula 2B');
  lockers(1.5, z0 - 7, z0 - 11, 1);
  const poster = new THREE.Mesh(new THREE.PlaneGeometry(0.42, 0.56), posterMat);
  poster.position.set(1.38, 1.55, z0 - 4); poster.rotation.y = FACE.nx; poster.userData.noCast = true; scene.add(poster);
  const bp = new THREE.Group(); bp.position.set(-0.7, 0, z0 - 8.6); bp.rotation.y = 0.6; scene.add(bp);
  const bb = box(0.34, 0.18, 0.44, lam(0x2a3f6a), 0, 0.09, 0, bp); bb.rotation.z = 0.12;
  box(0.06, 0.03, 0.36, lam(0x111111), 0.1, 0.19, 0, bp); box(0.06, 0.03, 0.36, lam(0x111111), -0.1, 0.19, 0, bp);
  // panel eléctrico (aparece tras varias vueltas)
  const sw = new THREE.Group(); sw.position.set(-1.38, 0, z0 - 9); sw.rotation.y = FACE.px; sw.visible = false; scene.add(sw);
  box(0.5, 0.72, 0.12, M_metal, 0, 1.35, 0.06, sw);
  box(0.44, 0.06, 0.02, M_emLamp, 0, 1.66, 0.13, sw).userData.noCast = true;
  const lever = new THREE.Group(); lever.position.set(0.08, 1.3, 0.13); sw.add(lever);
  box(0.05, 0.22, 0.05, M_black, 0, 0.09, 0, lever); lever.rotation.z = 0.6;
  box(0.05, 0.05, 0.03, M_swLed, -0.15, 1.5, 0.13, sw).userData.noCast = true;
  const lbl = textPlane('PANEL ELÉCTRICO', 0.48, 0.1, { bg: '#d8d0b8', fg: '#111', size: 0.6, lit: true }); lbl.position.set(0, 1.8, 0.07); sw.add(lbl);
  const scrawl = scrawlText('NO ES LA PRIMERA VEZ', -1.38, z0 - 6.3, FACE.px, 2.0, 1.9); scrawl.visible = false;
  const fig = makePerson({ shadow: true, creepy: 2 }); fig.g.position.set(0.45, 0, z0 - 11.5); fig.g.rotation.y = 0; fig.g.visible = false;
  loopMods.push({ z0, sw, lever, scrawl, fig, k });
}

// =====================================================================
// OBJETOS DE LA DESAPARICIÓN
// =====================================================================
const leftovers = new THREE.Group(); leftovers.visible = false; scene.add(leftovers);
function phoneMesh(x, z, lit, text) {
  const g = new THREE.Group(); g.position.set(x, 0.006, z); g.rotation.y = rand(0, 6); leftovers.add(g);
  box(0.08, 0.012, 0.16, lam(0x0d0d0d), 0, 0, 0, g);
  if (lit) { const s = textPlane(text || '', 0.07, 0.145, { bg: '#0d2236', fg: '#d5ecff', size: 0.07, weight: 'normal' }); s.rotation.x = -Math.PI / 2; s.position.y = 0.008; g.add(s); }
  return g;
}
function backpackMesh(x, z, color) {
  const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.set(0, rand(0, 6), 0); leftovers.add(g);
  const b = box(0.34, 0.18, 0.44, lam(color), 0, 0.09, 0, g); b.rotation.z = rand(-0.2, 0.2);
  box(0.06, 0.03, 0.36, lam(0x111111), 0.1, 0.19, 0, g); box(0.06, 0.03, 0.36, lam(0x111111), -0.1, 0.19, 0, g);
}
function spawnLeftovers() {
  for (const n of npcs) {
    const p = n.g.position;
    if (n.bag !== null) backpackMesh(p.x + rand(-0.2, 0.2), p.z + rand(-0.2, 0.2), n.bag);
    if (n.phone || Math.random() < 0.55) phoneMesh(p.x + rand(-0.4, 0.4), p.z + rand(-0.4, 0.4), Math.random() < 0.5, '11:11\nSin señal');
    if (Math.random() < 0.3) { const c = box(0.08, 0.12, 0.08, lam(0xe8e2d0), p.x + rand(-0.5, 0.5), 0.04, p.z + rand(-0.5, 0.5)); c.rotation.z = Math.PI / 2; leftovers.add(c); }
    n.g.visible = false;
  }
  backpackMesh(0.8, -11.6, 0x2a3f6a);
  backpackMesh(-0.9, -2.2, 0x7a2222);
  phoneMesh(1.25, -12.4, true, 'Mamá\n23 llamadas\nperdidas');
  psxAll(leftovers); setShadows(leftovers);
}

// Hoja que el jugador lleva en la mano
const handPaper = new THREE.Mesh(new THREE.PlaneGeometry(0.21, 0.29), new THREE.MeshLambertMaterial({
  map: canvasTex(64, 88, (g, w, h) => {
    g.fillStyle = '#f4f1e8'; g.fillRect(0, 0, w, h);
    g.fillStyle = '#222'; g.font = 'bold 7px Arial'; g.fillText('INFORME FINAL', 6, 11);
    g.fillStyle = 'rgba(0,0,0,.45)'; for (let i = 0; i < 16; i++) g.fillRect(6, 18 + i * 4, rand(30, 50) | 0, 1);
  }), side: THREE.DoubleSide,
}));
handPaper.position.set(0.26, -0.27, -0.5); handPaper.rotation.set(-0.9, -0.25, -0.2); handPaper.userData.noCast = true;
camera.add(handPaper);

// =====================================================================
// EL MONSTRUO (low-poly deformado, rostro pixelado con glitches)
// =====================================================================
const MON = { x: 0, z: 0, heading: 0, speed: 0, phase: 0, trail: [], bangT: 1, hbT: 0, sway: 0, swayT: 0, faceT: 0, hold: 0 };
const skinMat = psx(new THREE.MeshLambertMaterial({ map: mSkinTex, color: 0x8a7a6a, emissive: 0x120d0a }));
const paleMat = psx(new THREE.MeshLambertMaterial({ map: mSkinTex, color: 0xf0e6d0, emissive: 0x2e2a24 }));
function mpart(geo, mat, parent, x, y, z, amt) { const m = new THREE.Mesh(facet(lumpy(geo, amt || 0.03)), mat); m.position.set(x, y, z); parent.add(m); return m; }
function buildHead(scare) {
  const h = new THREE.Group(), F = scare ? scareFace : monFace;
  const faceMat = psx(scare
    ? new THREE.MeshBasicMaterial({ map: F.t })
    : new THREE.MeshLambertMaterial({ map: F.t, emissive: 0x3a3630, emissiveMap: F.t }));
  const geo = lumpy(new THREE.CylinderGeometry(0.17, 0.12, 0.44, 9, 3, false, -Math.PI), 0.025);
  h.add(new THREE.Mesh(facet(geo), [faceMat, skinMat, skinMat]));
  mpart(new THREE.IcosahedronGeometry(0.11, 0), skinMat, h, 0.05, 0.22, -0.07, 0.04);
  mpart(new THREE.IcosahedronGeometry(0.08, 0), skinMat, h, -0.07, 0.2, -0.03, 0.03);
  return h;
}
const monster = new THREE.Group(); monster.visible = false; scene.add(monster);
const mBody = new THREE.Group(); mBody.position.y = 1.05; mBody.rotation.x = -0.28; monster.add(mBody);
{
  const torso = mpart(new THREE.CylinderGeometry(0.26, 0.2, 1.5, 7, 4).scale(1, 1, 0.75), skinMat, mBody, 0, 0, 0, 0.07);
  torso.rotation.x = Math.PI / 2;
  for (let i = 0; i < 7; i++) mpart(new THREE.ConeGeometry(0.045, 0.16, 4), paleMat, mBody, 0, 0.2, -0.66 + i * 0.22, 0.01);
  for (const s of [-1, 1]) for (let i = 0; i < 4; i++) {
    const c = mpart(new THREE.ConeGeometry(0.03, 0.12, 4), paleMat, mBody, s * 0.23, -0.02, 0.25 - i * 0.16, 0.01);
    c.rotation.z = -s * Math.PI / 2;
  }
}
function limb(x, y, z, l1, l2, spread) {
  const sh = new THREE.Group(); sh.position.set(x, y, z); sh.rotation.z = spread; mBody.add(sh);
  mpart(new THREE.CylinderGeometry(0.07, 0.05, l1, 5, 2), skinMat, sh, 0, -l1 / 2, 0, 0.03);
  const el = new THREE.Group(); el.position.y = -l1; sh.add(el);
  mpart(new THREE.IcosahedronGeometry(0.06, 0), skinMat, el, 0, 0, 0, 0.02);
  mpart(new THREE.CylinderGeometry(0.05, 0.03, l2, 5, 2), skinMat, el, 0, -l2 / 2, 0, 0.025);
  const hand = new THREE.Group(); hand.position.set(0, -l2, 0.02); el.add(hand);
  mpart(new THREE.IcosahedronGeometry(0.06, 0).scale(1, 0.5, 1.3), paleMat, hand, 0, 0, 0, 0.01);
  for (let f = -1; f <= 1; f++) { const fg = mpart(new THREE.ConeGeometry(0.016, 0.3, 4), paleMat, hand, f * 0.045, -0.01, 0.17, 0.01); fg.rotation.x = Math.PI / 2; }
  return { sh, el, spread };
}
const mLimbs = [
  limb(-0.3, 0.05, 0.62, 0.9, 1.0, -0.78), limb(0.3, 0.05, 0.62, 0.9, 1.0, 0.78),
  limb(-0.24, -0.1, -0.66, 0.6, 0.72, -0.3), limb(0.24, -0.1, -0.66, 0.6, 0.72, 0.3),
];
const neckSegs = [];
let headPivot;
{
  const base = new THREE.Group(); base.position.set(0, 0.15, 0.7); mBody.add(base);
  let parent = base; const ang = [0.15, 0.22, 0.3, 0.38, 0.42, 0.42]; const L = 0.38;
  ang.forEach((a, i) => {
    const s = new THREE.Group(); if (i > 0) s.position.y = L; s.rotation.x = a; parent.add(s);
    const r = 0.085 - i * 0.006;
    mpart(new THREE.CylinderGeometry(r * 0.9, r, L + 0.05, 6, 1), skinMat, s, 0, L / 2, 0, 0.02);
    neckSegs.push({ g: s, a }); parent = s;
  });
  headPivot = new THREE.Group(); headPivot.position.y = L; parent.add(headPivot);
}
const mHead = buildHead(false); headPivot.add(mHead);
const scareHead = buildHead(true); scareHead.scale.setScalar(1.45); scareHead.visible = false; scene.add(scareHead);

// =====================================================================
// REFLEJO EN EL CRISTAL: imágenes "fantasma" en posición especular (x' = 2·72 − x)
// =====================================================================
const reflGroup = new THREE.Group(); reflGroup.visible = false; scene.add(reflGroup);
const ghostMats = { me: [], tall: [] };
function ghostify(root, tint, list) {
  root.traverse(o => {
    if (!o.isMesh) return;
    const conv = m => {
      const g = psx(new THREE.MeshBasicMaterial({ map: m.map || null, color: (m.color ? m.color.clone() : new THREE.Color(1, 1, 1)).multiplyScalar(tint),
        transparent: true, opacity: 0, depthWrite: false, fog: false }));
      list.push(g); return g;
    };
    o.material = Array.isArray(o.material) ? o.material.map(conv) : conv(o.material);
    o.castShadow = o.receiveShadow = false; o.renderOrder = 3;
  });
}
const reflMe = makePerson(); scene.remove(reflMe.g); reflGroup.add(reflMe.g);
reflMe.g.scale.setScalar(0.95); reflMe.arms[0].rotation.x = -1.25; reflMe.arms[0].rotation.z = -0.35;   // brazo sosteniendo el teléfono
ghostify(reflMe.g, 0.85, ghostMats.me);
const glareTex = (() => { const G = makeCanvas(32, 32), g = G.g, gr = g.createRadialGradient(16, 16, 1, 16, 16, 16);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.25, 'rgba(255,245,225,0.6)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 32, 32); G.t.needsUpdate = true; return G.t; })();
const glare = new THREE.Sprite(new THREE.SpriteMaterial({ map: glareTex, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false, fog: false }));
glare.scale.set(0.45, 0.45, 1); glare.renderOrder = 4; reflGroup.add(glare);
const glare2 = new THREE.Sprite(new THREE.SpriteMaterial({ map: glareTex, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false, fog: false, opacity: 0.25 }));
glare2.scale.set(1.8, 1.8, 1); glare2.renderOrder = 4; reflGroup.add(glare2);
// la criatura de cuello largo, de pie
const tall = new THREE.Group(); reflGroup.add(tall);
let tallHead;
{
  for (const s of [-1, 1]) mpart(new THREE.CylinderGeometry(0.075, 0.05, 1.25, 5, 3), skinMat, tall, s * 0.13, 0.63, 0, 0.05);
  mpart(new THREE.CylinderGeometry(0.21, 0.13, 0.9, 6, 3).scale(1, 1, 0.6), skinMat, tall, 0, 1.68, 0, 0.06);
  for (let i = 0; i < 4; i++) mpart(new THREE.ConeGeometry(0.03, 0.1, 4), paleMat, tall, 0, 1.45 + i * 0.13, -0.13, 0.01).rotation.x = -Math.PI / 2;
  for (const s of [-1, 1]) {
    const sh = new THREE.Group(); sh.position.set(s * 0.25, 2.06, 0); sh.rotation.set(0.12, 0, s * 0.07); tall.add(sh);
    mpart(new THREE.CylinderGeometry(0.05, 0.035, 0.9, 5, 2), skinMat, sh, 0, -0.45, 0, 0.03);
    mpart(new THREE.CylinderGeometry(0.035, 0.025, 0.85, 5, 2), skinMat, sh, 0, -1.3, 0, 0.02);
    for (let f = -1; f <= 1; f++) mpart(new THREE.ConeGeometry(0.014, 0.34, 4), paleMat, sh, f * 0.03, -1.88, 0, 0.01).rotation.x = Math.PI;
  }
  let parent = new THREE.Group(); parent.position.set(0, 2.1, 0.02); tall.add(parent);
  const L = 0.23;
  [0.0, 0.3, 0.55, 0.7, 0.7, 0.5].forEach((a, i) => {
    const sgm = new THREE.Group(); if (i > 0) sgm.position.y = L; sgm.rotation.x = a; parent.add(sgm);
    mpart(new THREE.CylinderGeometry(0.06, 0.07, L + 0.05, 6, 1), skinMat, sgm, 0, L / 2, 0, 0.02);
    parent = sgm;
  });
  tallHead = new THREE.Group(); tallHead.position.y = L; tallHead.scale.setScalar(1.2); parent.add(tallHead);
  const fm = new THREE.MeshBasicMaterial({ map: monFace.t });
  const hg = lumpy(new THREE.CylinderGeometry(0.17, 0.12, 0.44, 9, 3, false, -Math.PI), 0.025);
  tallHead.add(new THREE.Mesh(facet(hg), [fm, skinMat, skinMat]));
}
ghostify(tall, 0.75, ghostMats.tall);
tall.traverse(o => { if (o.isMesh && Array.isArray(o.material)) o.material[0].color.setRGB(1, 1, 1); });

// =====================================================================
// SOMBRAS + PSX para todo lo construido
// =====================================================================
function setShadows(root) {
  root.traverse(o => {
    if (!o.isMesh) return;
    const mats = [].concat(o.material);
    const basic = mats.every(m => m.isMeshBasicMaterial);
    o.castShadow = !basic && !o.userData.noCast && !mats.includes(M_paper);
    o.receiveShadow = !basic;
  });
}
psxAll(scene); setShadows(scene);

// =====================================================================
// AUDIO (Web Audio API, todo sintetizado)
// =====================================================================
const A = { ctx: null };
function initAudio() {
  const c = new (window.AudioContext || window.webkitAudioContext)(); A.ctx = c;
  A.comp = c.createDynamicsCompressor(); A.comp.threshold.value = -14; A.comp.knee.value = 8; A.comp.ratio.value = 6;
  A.master = c.createGain(); A.master.gain.value = 0.9; A.master.connect(A.comp); A.comp.connect(c.destination);
  const len = c.sampleRate * 2;
  A.white = c.createBuffer(1, len, c.sampleRate);
  { const d = A.white.getChannelData(0); for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1; }
  A.brown = c.createBuffer(1, len * 2, c.sampleRate);
  { const d = A.brown.getChannelData(0); let last = 0; for (let i = 0; i < d.length; i++) { last = (last + 0.02 * (Math.random() * 2 - 1)) / 1.02; d[i] = last * 3.5; } }
  A.verb = c.createConvolver();
  const il = Math.floor(c.sampleRate * 2.6), ib = c.createBuffer(2, il, c.sampleRate);
  for (let ch = 0; ch < 2; ch++) { const d = ib.getChannelData(ch); for (let i = 0; i < il; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / il, 3.2); }
  A.verb.buffer = ib;
  A.verbOut = c.createGain(); A.verbOut.gain.value = 0.35; A.verb.connect(A.verbOut); A.verbOut.connect(A.master);
  A.mPan = makePanner(3.5, 0.7);
  A.mBus = c.createGain(); A.mBus.gain.value = 1.6;
  A.mSub = c.createGain(); A.mSub.gain.value = 0; A.mSub.connect(A.master); A.mBus.connect(A.mPan); A.mPan.connect(A.master);
  A.mSend = c.createGain(); A.mSend.gain.value = 0.3; A.mPan.connect(A.mSend); A.mSend.connect(A.verb);
  A.pPan = makePanner(0.8, 1.4); A.pPan.connect(A.master);
  setPannerPos(A.pPan, 1.25, 0.05, -12.4);
  A.stepBus = c.createGain(); A.stepBus.gain.value = 1; A.stepBus.connect(A.master);
  A.stepSend = c.createGain(); A.stepSend.gain.value = 0.15; A.stepBus.connect(A.stepSend); A.stepSend.connect(A.verb);
}
function makePanner(ref, roll) {
  const p = A.ctx.createPanner();
  p.panningModel = 'HRTF'; p.distanceModel = 'inverse'; p.refDistance = ref; p.rolloffFactor = roll; p.maxDistance = 100;
  return p;
}
function setPannerPos(p, x, y, z) {
  if (p.positionX) { p.positionX.value = x; p.positionY.value = y; p.positionZ.value = z; } else p.setPosition(x, y, z);
}
const _fwd = new THREE.Vector3();
function updateListener() {
  const l = A.ctx.listener, p = camera.position; camera.getWorldDirection(_fwd);
  if (l.positionX) {
    l.positionX.value = p.x; l.positionY.value = p.y; l.positionZ.value = p.z;
    l.forwardX.value = _fwd.x; l.forwardY.value = _fwd.y; l.forwardZ.value = _fwd.z;
    l.upX.value = 0; l.upY.value = 1; l.upZ.value = 0;
  } else { l.setPosition(p.x, p.y, p.z); l.setOrientation(_fwd.x, _fwd.y, _fwd.z, 0, 1, 0); }
}
function loopNoise(buf) { const s = A.ctx.createBufferSource(); s.buffer = buf || A.white; s.loop = true; return s; }
function env(g, t, a, peak, d) {
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(Math.max(0.0002, peak), t + a);
  g.gain.exponentialRampToValueAtTime(0.0001, t + a + d);
}
function thump(t, f, dur, vol, dest) {
  const c = A.ctx, o = c.createOscillator(), g = c.createGain();
  o.frequency.setValueAtTime(f, t); o.frequency.exponentialRampToValueAtTime(Math.max(20, f * 0.35), t + dur);
  env(g, t, 0.004, vol, dur); o.connect(g); g.connect(dest); o.start(t); o.stop(t + dur + 0.05);
}
function burst(t, dur, type, f, q, vol, dest) {
  const c = A.ctx, s = c.createBufferSource(), fl = c.createBiquadFilter(), g = c.createGain();
  s.buffer = A.white; fl.type = type; fl.frequency.value = f; fl.Q.value = q;
  env(g, t, 0.003, vol, dur); s.connect(fl); fl.connect(g); g.connect(dest);
  s.start(t, Math.random() * 1.5); s.stop(t + dur + 0.05);
}

// ---------- Bullicio universitario
const VOW = [[800, 1200], [500, 1900], [300, 2300], [500, 900], [350, 800], [650, 1700]];
function startCrowd() {
  const c = A.ctx, now = c.currentTime;
  A.crowd = c.createGain(); A.crowd.gain.setValueAtTime(0, now); A.crowd.gain.linearRampToValueAtTime(0.95, now + 2.5);
  const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2300;
  A.crowd.connect(lp); lp.connect(A.master); A.crowdLP = lp;
  const send = c.createGain(); send.gain.value = 0.7; lp.connect(send); send.connect(A.verb);
  const n = loopNoise(A.brown), bp = c.createBiquadFilter(), ng = c.createGain();
  bp.type = 'bandpass'; bp.frequency.value = 420; bp.Q.value = 0.6; ng.gain.value = 0.06;
  n.connect(bp); bp.connect(ng); ng.connect(A.crowd); n.start();
  A.voices = [];
  for (let i = 0; i < 9; i++) {
    const o = c.createOscillator(); o.type = 'sawtooth'; const f0 = rand(95, 235); o.frequency.value = f0;
    const f1 = c.createBiquadFilter(); f1.type = 'bandpass'; f1.Q.value = 6;
    const f2 = c.createBiquadFilter(); f2.type = 'bandpass'; f2.Q.value = 8;
    const vg = c.createGain(); vg.gain.value = 0.0001;
    const pan = c.createStereoPanner(); pan.pan.value = rand(-0.9, 0.9);
    const mix = c.createGain(); mix.gain.value = rand(0.045, 0.1);
    o.connect(f1); o.connect(f2); f1.connect(vg); f2.connect(vg); vg.connect(mix); mix.connect(pan); pan.connect(A.crowd);
    o.start(); A.voices.push({ o, f1, f2, vg, f0, next: now + rand(0, 1.5) });
  }
  A.nextLaugh = now + rand(1.5, 4); A.nextMisc = now + rand(0.5, 2);
  A.crowdTimer = setInterval(crowdTick, 90);
  const bz = c.createOscillator(); bz.type = 'sawtooth'; bz.frequency.value = 120;
  const bf = c.createBiquadFilter(); bf.type = 'bandpass'; bf.frequency.value = 240; bf.Q.value = 3;
  A.buzz = c.createGain(); A.buzz.gain.value = 0.012; bz.connect(bf); bf.connect(A.buzz); A.buzz.connect(A.master); bz.start();
}
function crowdTick() {
  const now = A.ctx.currentTime;
  for (const v of A.voices) {
    while (v.next < now + 0.3) {
      const t = Math.max(v.next, now), d = rand(0.07, 0.2), vw = VOW[(Math.random() * VOW.length) | 0];
      v.f1.frequency.setTargetAtTime(vw[0], t, 0.02); v.f2.frequency.setTargetAtTime(vw[1], t, 0.02);
      v.o.frequency.setTargetAtTime(v.f0 * rand(0.85, 1.25), t, 0.05);
      v.vg.gain.setTargetAtTime(rand(0.5, 1), t, 0.015); v.vg.gain.setTargetAtTime(0.0001, t + d, 0.03);
      v.next = t + d + (Math.random() < 0.18 ? rand(0.4, 1.6) : rand(0.02, 0.08));
    }
  }
  if (now > A.nextLaugh) { laugh(now + 0.05); A.nextLaugh = now + rand(3, 8); }
  if (now > A.nextMisc) { miscCrowd(now + 0.05); A.nextMisc = now + rand(0.7, 2.4); }
}
function laugh(t) {
  const c = A.ctx, o = c.createOscillator(); o.type = 'sawtooth'; const f = rand(220, 340);
  const f1 = c.createBiquadFilter(); f1.type = 'bandpass'; f1.frequency.value = rand(700, 900); f1.Q.value = 5;
  const f2 = c.createBiquadFilter(); f2.type = 'bandpass'; f2.frequency.value = rand(1100, 1400); f2.Q.value = 6;
  const g = c.createGain(); g.gain.value = 0.0001; const pan = c.createStereoPanner(); pan.pan.value = rand(-1, 1);
  const vol = rand(0.05, 0.12);
  o.connect(f1); o.connect(f2); f1.connect(g); f2.connect(g); g.connect(pan); pan.connect(A.crowd);
  const n = rand(4, 8) | 0;
  for (let i = 0; i < n; i++) {
    const tt = t + i * rand(0.13, 0.17);
    o.frequency.setValueAtTime(f * (1 - i * 0.03), tt);
    g.gain.setTargetAtTime(vol * (1 - i / (n + 2)), tt, 0.01); g.gain.setTargetAtTime(0.0001, tt + 0.07, 0.02);
  }
  o.start(t); o.stop(t + n * 0.17 + 0.4);
}
function miscCrowd(t) {
  const r = Math.random(), pan = A.ctx.createStereoPanner(); pan.pan.value = rand(-1, 1); pan.connect(A.crowd);
  if (r < 0.6) { const n = rand(3, 8) | 0; for (let i = 0; i < n; i++) burst(t + i * rand(0.42, 0.55), 0.05, 'bandpass', rand(1500, 2500), 1.5, 0.07, pan); }
  else if (r < 0.85) { burst(t, 0.35, 'bandpass', rand(900, 1400), 12, 0.14, pan); thump(t, 140, 0.2, 0.09, pan); }
  else { thump(t, 80, 0.35, 0.16, pan); burst(t, 0.2, 'lowpass', 500, 1, 0.1, pan); }
}
function stopCrowd() {   // corte en seco
  const t = A.ctx.currentTime;
  clearInterval(A.crowdTimer);
  A.crowd.gain.cancelScheduledValues(t); A.crowd.gain.setValueAtTime(0, t);
  A.buzz.gain.cancelScheduledValues(t); A.buzz.gain.setValueAtTime(0, t);
}
// ---------- Zumbido grave opresivo
function startHum() {
  const c = A.ctx, now = c.currentTime;
  A.hum = c.createGain(); A.hum.gain.setValueAtTime(0.0001, now); A.hum.gain.linearRampToValueAtTime(0.55, now + 1.2);
  A.hum.connect(A.master);
  const n = loopNoise(A.brown), lp = c.createBiquadFilter(), ng = c.createGain();
  lp.type = 'lowpass'; lp.frequency.value = 150; ng.gain.value = 0.6; n.connect(lp); lp.connect(ng); ng.connect(A.hum); n.start();
  [[48, 0.12], [96.5, 0.03], [51, 0.06]].forEach(([f, v]) => { const o = c.createOscillator(), g = c.createGain(); o.frequency.value = f; g.gain.value = v; o.connect(g); g.connect(A.hum); o.start(); });
  const lfo = c.createOscillator(), lg = c.createGain(); lfo.frequency.value = 0.13; lg.gain.value = 0.15; lfo.connect(lg); lg.connect(A.hum.gain); lfo.start();
  const w = c.createOscillator(), wg = c.createGain(); w.frequency.value = 7400; wg.gain.value = 0.002; w.connect(wg); wg.connect(A.hum); w.start();
}
// ---------- Respiración del monstruo
function startRasp() {
  const c = A.ctx, n = loopNoise(), bp = c.createBiquadFilter(), g = c.createGain();
  bp.type = 'bandpass'; bp.frequency.value = 620; bp.Q.value = 2.5; g.gain.value = 0;
  const lfo = c.createOscillator(), lg = c.createGain(); lfo.frequency.value = 2.2; lg.gain.value = 0.22;
  lfo.connect(lg); lg.connect(g.gain);
  A.raspOut = c.createGain(); A.raspOut.gain.value = 0;
  n.connect(bp); bp.connect(g); g.connect(A.raspOut); A.raspOut.connect(A.mBus); n.start(); lfo.start();
}
// ---------- Efectos
function playerStep(run) { const t = A.ctx.currentTime; burst(t, 0.06, 'bandpass', rand(900, 1400), 1.2, run ? 0.11 : 0.06, A.stepBus); thump(t, rand(80, 110), 0.09, run ? 0.13 : 0.07, A.stepBus); }
function monsterStep(heavy) {
  const t = A.ctx.currentTime, v = heavy ? 1 : 0.75;
  thump(t, rand(48, 64), 0.32, 1.9 * v, A.mBus);
  burst(t, 0.16, 'lowpass', rand(600, 900), 0.8, 1.5 * v, A.mBus);
  burst(t, 0.09, 'bandpass', rand(160, 220), 1.2, 1.3 * v, A.mBus);
  burst(t + 0.005, 0.04, 'highpass', 2400, 0.7, 0.7 * v, A.mBus);
  if (Math.random() < 0.5) burst(t + 0.02, 0.05, 'bandpass', 3200, 2, 0.35 * v, A.mBus);
  thump(t, 34, 0.4, 1.3 * v, A.mSub);
}
function wallBang(dest) { const t = A.ctx.currentTime; thump(t, 38, 0.6, 1.4, dest); burst(t, 0.45, 'lowpass', 260, 0.7, 1.2, dest); burst(t, 0.1, 'bandpass', 1200, 3, 0.3, dest); }
function clunk() { const t = A.ctx.currentTime; thump(t, 70, 0.6, 0.9, A.master); burst(t, 0.35, 'lowpass', 300, 1, 0.6, A.master); burst(t, 0.3, 'lowpass', 300, 1, 0.5, A.verb); }
function rattle() { const t = A.ctx.currentTime; for (let i = 0; i < 6; i++) { burst(t + i * 0.11, 0.12, 'bandpass', rand(900, 1300), 10, 0.3, A.master); thump(t + i * 0.11, 130, 0.12, 0.25, A.master); burst(t + i * 0.11, 0.1, 'bandpass', 1100, 8, 0.12, A.verb); } }
function doorSlam() { const t = A.ctx.currentTime; thump(t, 50, 0.9, 1.4, A.master); burst(t, 0.6, 'lowpass', 420, 0.8, 1.0, A.master); burst(t, 0.15, 'bandpass', 900, 4, 0.35, A.master); burst(t, 0.5, 'lowpass', 500, 1, 0.8, A.verb); }
function heartbeat(vol) { const t = A.ctx.currentTime; thump(t, 55, 0.18, vol, A.master); thump(t + 0.17, 48, 0.2, vol * 0.7, A.master); }
function phoneBuzz() {
  const c = A.ctx, t = c.currentTime, o = c.createOscillator(), lp = c.createBiquadFilter(), g = c.createGain();
  o.type = 'sawtooth'; o.frequency.value = 165; lp.type = 'lowpass'; lp.frequency.value = 520; g.gain.value = 0.0001;
  [0, 0.55].forEach(s => { g.gain.setTargetAtTime(0.4, t + s, 0.01); g.gain.setTargetAtTime(0.0001, t + s + 0.38, 0.02); });
  o.connect(lp); lp.connect(g); g.connect(A.pPan); o.start(t); o.stop(t + 1.2);
}
function distCurve(k) { const n = 2048, cv = new Float32Array(n); for (let i = 0; i < n; i++) { const x = i * 2 / n - 1; cv[i] = (3 + k) * x * 20 * Math.PI / 180 / (Math.PI + k * Math.abs(x)); } return cv; }
function stepCurve(steps) { const n = 1024, cv = new Float32Array(n); for (let i = 0; i < n; i++) { const x = i * 2 / n - 1; cv[i] = Math.round(x * steps) / steps; } return cv; }
function wail(dest, vol, base, dur) {
  const c = A.ctx, t = c.currentTime;
  const out = c.createGain(); out.gain.setValueAtTime(0.0001, t); out.gain.exponentialRampToValueAtTime(vol, t + 0.025);
  out.gain.setValueAtTime(vol, t + dur * 0.6); out.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  const ws = c.createWaveShaper(); ws.curve = distCurve(400); ws.oversample = '4x';
  const hp = c.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 180;
  ws.connect(hp); hp.connect(out); out.connect(dest);
  const vs = c.createGain(); vs.gain.value = 0.5; out.connect(vs); vs.connect(A.verb);
  [1, 1.5, 2.02, 2.9, 0.5].forEach((m, i) => {
    const o = c.createOscillator(); o.type = i % 2 ? 'sawtooth' : 'square'; const f = base * m;
    o.frequency.setValueAtTime(f * 0.6, t); o.frequency.exponentialRampToValueAtTime(f * 1.4, t + 0.15); o.frequency.exponentialRampToValueAtTime(f * 0.85, t + dur * 0.9);
    const vib = c.createOscillator(), vg = c.createGain(); vib.frequency.value = rand(18, 32); vg.gain.value = f * 0.06; vib.connect(vg); vg.connect(o.frequency);
    const g = c.createGain(); g.gain.value = 0.18; o.connect(g); g.connect(ws);
    o.start(t); vib.start(t); o.stop(t + dur + 0.05); vib.stop(t + dur + 0.05);
  });
  const n = c.createBufferSource(), nb = c.createBiquadFilter(), ng = c.createGain();
  n.buffer = A.white; nb.type = 'bandpass'; nb.frequency.value = 2500; nb.Q.value = 0.8; ng.gain.value = 0.6;
  n.connect(nb); nb.connect(ng); ng.connect(ws); n.start(t); n.stop(t + dur + 0.05);
}
function scream() { wail(A.master, 1.0, 380, 1.65); thump(A.ctx.currentTime, 90, 0.6, 1.0, A.master); burst(A.ctx.currentTime, 1.2, 'highpass', 1500, 0.5, 0.6, A.master); }
function doorClose() {
  const t = A.ctx.currentTime;
  thump(t, 85, 0.35, 0.8, A.master); burst(t, 0.25, 'lowpass', 500, 1, 0.6, A.master);
  burst(t + 0.02, 0.05, 'bandpass', 2200, 3, 0.25, A.master); burst(t + 0.09, 0.03, 'bandpass', 3000, 4, 0.18, A.master);
}
function doorCreak() {
  const c = A.ctx, t = c.currentTime, o = c.createOscillator(), bp = c.createBiquadFilter(), g = c.createGain();
  o.type = 'sawtooth'; o.frequency.setValueAtTime(38, t);
  for (let i = 0; i < 10; i++) o.frequency.setValueAtTime(rand(30, 70), t + i * 0.12);
  bp.type = 'bandpass'; bp.frequency.setValueAtTime(900, t); bp.frequency.linearRampToValueAtTime(1500, t + 1.3); bp.Q.value = 6;
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.35, t + 0.1); g.gain.setValueAtTime(0.35, t + 1.0); g.gain.exponentialRampToValueAtTime(0.0001, t + 1.4);
  o.connect(bp); bp.connect(g); g.connect(A.master); const s = c.createGain(); s.gain.value = 0.4; g.connect(s); s.connect(A.verb);
  o.start(t); o.stop(t + 1.5);
}
function breath(inhale) {
  const t = A.ctx.currentTime;
  if (inhale) burst(t, 0.26, 'highpass', 1700, 0.7, 0.07, A.master);
  else burst(t, 0.22, 'bandpass', rand(900, 1200), 0.9, 0.1, A.master);
}
function sparks(x, y, z) {
  const p = makePanner(2.5, 0.9); setPannerPos(p, x, y, z); p.connect(A.master);
  const t = A.ctx.currentTime;
  burst(t, 0.12, 'highpass', 3500, 0.7, 0.9, p); thump(t, 120, 0.15, 0.6, p);
  for (let i = 0; i < 7; i++) burst(t + 0.05 + i * rand(0.03, 0.07), 0.02, 'highpass', 5000, 1, 0.5, p);
  burst(t + 0.02, 0.4, 'bandpass', 4200, 3, 0.35, p);
  burst(t, 0.4, 'highpass', 2000, 1, 0.3, A.verb);
}
function rattleAt(x, z) {
  const p = makePanner(2, 0.9); setPannerPos(p, x, 1.2, z); p.connect(A.master);
  const t = A.ctx.currentTime;
  for (let i = 0; i < 5; i++) { burst(t + i * 0.09, 0.1, 'bandpass', rand(700, 1100), 8, 0.6, p); thump(t + i * 0.09, 110, 0.12, 0.5, p); }
}
function tinnitus() {   // pitido en los oídos tras el silencio repentino
  const c = A.ctx, t = c.currentTime, o = c.createOscillator(), g = c.createGain();
  o.frequency.value = 6300; g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.02, t + 0.25); g.gain.exponentialRampToValueAtTime(0.0001, t + 7);
  o.connect(g); g.connect(A.master); o.start(t); o.stop(t + 7.2);
}
function whisperAt(x, y, z) {   // susurro espacial
  const c = A.ctx, t = c.currentTime, p = makePanner(1.5, 1); setPannerPos(p, x, y, z); p.connect(A.master);
  const s2 = c.createGain(); s2.gain.value = 0.6; p.connect(s2); s2.connect(A.verb);
  const n = c.createBufferSource(), bp = c.createBiquadFilter(), g = c.createGain();
  n.buffer = A.white; bp.type = 'bandpass'; bp.Q.value = 2.5; g.gain.value = 0.0001;
  for (let i = 0; i < 12; i++) {
    const tt = t + i * rand(0.08, 0.15);
    bp.frequency.setValueAtTime(rand(1800, 3600), tt);
    g.gain.setTargetAtTime(rand(0.2, 0.5), tt, 0.01); g.gain.setTargetAtTime(0.0001, tt + 0.06, 0.03);
  }
  n.connect(bp); bp.connect(g); g.connect(p); n.start(t, rand(0, 1)); n.stop(t + 2.2);
}
function buzzerAt(x, z) {   // cerradura electrónica que se libera
  const c = A.ctx, t = c.currentTime, p = makePanner(2, 0.8); setPannerPos(p, x, 1.3, z); p.connect(A.master);
  const o = c.createOscillator(), g = c.createGain(); o.type = 'square'; o.frequency.value = 98;
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.5, t + 0.02); g.gain.setValueAtTime(0.5, t + 0.6); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.7);
  o.connect(g); g.connect(p); o.start(t); o.stop(t + 0.75);
  thump(t + 0.72, 70, 0.4, 1.2, p); burst(t + 0.72, 0.25, 'lowpass', 400, 1, 1.0, p);
}

// ---------- Final
function stingBehind() {   // presencia justo detrás (muy baja, casi subliminal)
  const t = A.ctx.currentTime, bx = P.x + Math.sin(P.yaw) * 0.9, bz = P.z + Math.cos(P.yaw) * 0.9;
  thump(t, 30, 1.2, 0.9, A.master);
  whisperAt(bx, 2.3, bz);
  const p = makePanner(0.6, 1.2); setPannerPos(p, bx, 2.2, bz); p.connect(A.master);
  burst(t + 0.3, 0.9, 'bandpass', 620, 2.5, 0.35, p);
}
function thudFinal() {   // golpe seco
  const t = A.ctx.currentTime;
  thump(t, 44, 0.45, 1.8, A.master); burst(t, 0.18, 'lowpass', 220, 0.8, 1.4, A.master); burst(t, 0.6, 'lowpass', 300, 1, 0.6, A.verb);
}
function buzzFlicker() { const t = A.ctx.currentTime; for (let i = 0; i < 6; i++) burst(t + i * rand(0.06, 0.14), 0.04, 'bandpass', 240, 6, 0.25, A.master); }

// =====================================================================
// HUD + EFECTOS DE PANTALLA
// =====================================================================
let subTimer = 0;
function say(text, ms) { const s = $('subtitle'); s.textContent = text; s.style.opacity = 1; clearTimeout(subTimer); subTimer = setTimeout(() => s.style.opacity = 0, ms || 3500); }
function setObjective(text) { const o = $('objective'); o.style.opacity = 0; setTimeout(() => { o.innerHTML = text ? '<b>OBJETIVO</b> · ' + text : ''; o.style.opacity = 0.9; }, 400); }
function hint(text, ms) { const h = $('hint'); h.textContent = text; h.style.opacity = 1; setTimeout(() => h.style.opacity = 0, ms || 2500); }
function fade(v, secs) { const f = $('fade'); f.style.transition = 'opacity ' + secs + 's'; f.style.opacity = v; }
const FX = { glitch: 0.08, spike: 0, red: 0, prox: 0, vig: 0.4 };
function fxTick(dt, inS) {
  let g = 0.02, vig = 0.35;
  if (phase === 'dark') { g = 0.05 + (inS ? 0.035 * Math.min(6, LOOP.count) : 0); vig = 0.55; }
  else if (phase === 'intro') { g = 0.12 + (INTRO.arrived ? 0.25 : 0); vig = 0.55; }
  else if (phase === 'chase') { g = 0.08 + FX.prox * 0.55; vig = 0.55; }
  else if (phase === 'vestibule') { g = 0.03 + (VST.revealed ? 0.12 * VST.k : 0); vig = 0.5; }
  else if (phase === 'final') { g = 0.2; vig = 0.6; }
  else if (phase === 'caught') { g = 1; vig = 0.3; }
  FX.glitch = lerp(FX.glitch, g, Math.min(1, dt * 3));
  FX.vig = lerp(FX.vig, vig, Math.min(1, dt * 2));
  FX.spike *= Math.exp(-dt * 5);
  if (phase !== 'chase' && phase !== 'caught') FX.red = lerp(FX.red, 0, Math.min(1, dt * 4));
  post.uniforms.uGlitch.value = Math.min(1, FX.glitch + FX.spike * 0.7);
  post.uniforms.uRed.value = FX.red;
  post.uniforms.uVig.value = FX.vig;
}

// =====================================================================
// ESTADO DEL JUEGO
// =====================================================================
// phase: title -> normal -> office -> delivered -> dark -> intro -> chase <-> caught -> vestibule -> final -> end
let phase = 'title', paused = false, T = 0, triedExit = false, phoneT = 2;
let firstChase = true, deaths = 0, scareT = 0, scareDir = { x: 1, z: 0 }, worldBroken = false, offFlickT = 0;
const LOOP = { state: 0, count: 0, figHidden: true };      // state: 0 fuera, 1 atrapado, 2 roto
const INTRO = { t: 0, arrived: false, at: 0, turnBack: false, tb: 0, shake: 0 };
const VST = { tried: false, stare: 0, noFlashT: 0, hinted: false, revealed: false, revT: 0, k: 0 };
const FINAL = { t: 0, auto: false, yaw: 0, thud: false };
const EV = { lightsOut: false, roarT: 6, breathT: 0, breathIn: true, cornerC: false, cornerE: false };
const P = { x: 0, z: -1.2, yaw: 0, pitch: 0, vx: 0, vz: 0, bob: 0, stepAcc: 0, speed: 0, running: false };
const keys = {};

// Animación de puertas
const anims = [];
function swing(obj, to, dur, slam) {
  for (let i = anims.length - 1; i >= 0; i--) if (anims[i].o === obj) anims.splice(i, 1);
  anims.push({ o: obj, from: obj.rotation.y, to, t: 0, dur, slam });
}
function animsTick(dt) {
  for (let i = anims.length - 1; i >= 0; i--) {
    const a = anims[i]; a.t = Math.min(1, a.t + dt / a.dur);
    const e = a.slam ? a.t * a.t : 1 - Math.pow(1 - a.t, 3);
    a.o.rotation.y = lerp(a.from, a.to, e);
    if (a.t >= 1) anims.splice(i, 1);
  }
}

addEventListener('keydown', e => {
  keys[e.code] = true;
  if (e.code === 'KeyE') interact();
  if (e.code === 'KeyF' && flashAvail && phase !== 'end' && phase !== 'final' && !paused) {
    flashOn = !flashOn; if (A.ctx) burst(A.ctx.currentTime, 0.02, 'highpass', 3000, 1, 0.15, A.master);
    if (!flashUsed && flashOn) { flashUsed = true; $('fhint').style.display = 'none'; say('La linterna del teléfono. Sin señal.', 2600); }
  }
});
addEventListener('keyup', e => { keys[e.code] = false; });
addEventListener('blur', () => { for (const k in keys) keys[k] = false; });
addEventListener('mousemove', e => {
  if (document.pointerLockElement !== renderer.domElement || paused) return;
  if (phase === 'caught' || phase === 'end' || phase === 'final' || phase === 'intro') return;
  P.yaw -= e.movementX * CFG.mouse; P.pitch -= e.movementY * CFG.mouse;
  P.pitch = clamp(P.pitch, -1.35, 1.35);
});
function lock() { renderer.domElement.requestPointerLock && renderer.domElement.requestPointerLock(); }
$('start').addEventListener('click', () => {
  $('start').style.display = 'none';
  initAudio(); startCrowd(); startRasp();
  phase = 'normal'; fade(0, 2.5); lock();
  setTimeout(() => setObjective('Entrega el documento en la <b>Oficina 104</b> (Prof. M. Andrade), al fondo del pasillo.'), 1200);
});
$('pause').addEventListener('click', () => { lock(); });
document.addEventListener('pointerlockchange', () => {
  const locked = document.pointerLockElement === renderer.domElement;
  if (locked) {
    paused = false; $('pause').style.display = 'none';
    if (A.ctx && A.ctx.state === 'suspended') A.ctx.resume();
  } else if (phase !== 'title' && phase !== 'end' && phase !== 'final') {
    paused = true; $('pause').style.display = 'flex'; for (const k in keys) keys[k] = false;
    if (A.ctx) A.ctx.suspend();
  }
});
$('end').addEventListener('click', () => { if ($('end').dataset.ready) location.reload(); });

// ---------- Interacciones
const inter = [];
function addInter(x, y, z, r, label, can, use) { inter.push({ p: new THREE.Vector3(x, y, z), r, label, can, use }); }
addInter(-5.85, 0.84, -37.45, 2.4, 'Dejar el documento en la bandeja', () => phase === 'office', deliver);
addInter(-6.4, 0.8, -37.3, 2.2, 'Leer la nota', () => phase === 'normal' || phase === 'office' || phase === 'delivered',
  () => say('«Salí un momento. Dejen los trabajos en la bandeja. — M.A.»', 4000));
addInter(-2.15, 1.2, -35, 2.6, 'Abrir la puerta', () => phase === 'office' || phase === 'delivered', () => {
  if (phase === 'office') say('Primero dejo el documento en la bandeja.', 2800); else openOffice();
});
addInter(0, 1.3, 1.8, 2.8, 'Salir', () => phase === 'normal' || phase === 'dark', () => {
  if (phase === 'normal') say('Primero tengo que entregar el documento.', 3000); else tryExit();
});
addInter(1.95, 1.2, -10, 2.2, 'Abrir', () => phase === 'normal',
  () => { say('«Salida de emergencia. Uso exclusivo en caso de emergencia.»', 3500); rattle(); });
addInter(1.95, 1.2, -10, 2.2, 'Abrir la salida de emergencia', () => phase === 'dark' && !flags.emDoorOpen, lockedEmergency);
addInter(1.25, 0.05, -12.4, 1.9, 'Mirar el teléfono', () => phase === 'dark',
  () => say('«Mamá» — 23 llamadas perdidas. Sin señal. El reloj marca 11:11 y no avanza.', 5500));
addInter(-1.85, 1.5, -17.5, 2.0, 'Leer el tablero', () => phase === 'normal',
  () => say('Avisos de becas, un gato perdido, “Grupo de estudio — Sala 3”. Lo de siempre.', 3800));
addInter(0, 1.2, -39.8, 2.4, 'Abrir', () => phase === 'normal',
  () => { rattle(); say('«PASILLO B — Solo personal autorizado». Cerrado con llave.', 3200); });
addInter(0, 1.2, -40.3, 2.4, 'Abrir la puerta', () => phase === 'dark' && LOOP.state === 1,
  () => { rattle(); say('No abre. Del otro lado no se escucha nada.', 2600); });
addInter(GLASS_X - 0.35, 1.1, -112, 2.4, 'Empujar la puerta de cristal', () => phase === 'vestibule' && !VST.revealed, pushGlass);
for (const m of loopMods) {
  addInter(-1.2, 1.35, m.z0 - 9, 2.0, 'Activar el panel eléctrico',
    () => phase === 'dark' && LOOP.state === 1 && LOOP.count >= CFG.loopNeeded, pressSwitch);
  addInter(1.3, 1.55, m.z0 - 4, 1.8, 'Leer el cartel', () => phase === 'dark', () => say(LOOP.count >= 1
    ? '«DESAPARECIDA. Valeria R., 19 años. Vista por última vez: hoy, 11:11, Pasillo B.»'
    : '«DESAPARECIDA. Valeria R., 19 años. Vista por última vez en el Pasillo B.»', 4800));
}
let curInter = null;
function interactTick() {
  curInter = null; let best = 1e9;
  if (phase === 'caught' || phase === 'final' || phase === 'intro' || phase === 'end' || phase === 'title') { $('prompt').style.opacity = 0; return; }
  camera.getWorldDirection(_fwd);
  for (const it of inter) {
    if (!it.can()) continue;
    const d = camera.position.distanceTo(it.p); if (d > it.r) continue;
    const dir = it.p.clone().sub(camera.position).normalize();
    const dot = dir.dot(_fwd); if (dot < 0.72) continue;
    const score = d * (2 - dot); if (score < best) { best = score; curInter = it; }
  }
  const pr = $('prompt');
  if (curInter) { pr.textContent = '[E]  ' + curInter.label; pr.style.opacity = 1; } else pr.style.opacity = 0;
}
function interact() { if (curInter && !paused) curInter.use(); }

// =====================================================================
// FASE 1: la oficina (la puerta se cierra y el ruido se corta en seco)
// =====================================================================
function closeOffice() {
  phase = 'office'; flags.officeOpen = false;
  swing(offLeaf, OFF_CLOSED, 0.36, true);
  setTimeout(() => { doorClose(); stopCrowd(); tinnitus(); FX.spike = 0.35; breakWorld(); }, 340);
}
function deliver() {
  phase = 'delivered'; handPaper.visible = false; deskPaper.visible = true; trayGlow.visible = false;
  burst(A.ctx.currentTime, 0.12, 'bandpass', 2400, 1, 0.12, A.master);
  say('Listo. Lo verá cuando vuelva.', 3000);
  setObjective('Documento entregado. Sal de la oficina.');
}
function breakWorld() {   // cambios invisibles mientras la puerta está cerrada
  if (worldBroken) return;
  worldBroken = true;
  spawnLeftovers(); leftovers.visible = true;
  for (const L of lights) if (L !== officeLight && L !== safeLight) { L.base = L.p2; L.fl = L.fl2; L.cur = L.p2; L.l.intensity = L.p2; }
  M_panelMain.emissive.setHex(0x080808); M_panelFlick.emissive.setHex(0x080808);
  flags.sDoorOpen = true; sLeaf.rotation.y = 1.25;      // el Pasillo B quedó entreabierto
  M_glass.color.setHex(0x030405);
}
function openOffice() {
  phase = 'dark'; flags.officeOpen = true;
  swing(offLeaf, OFF_OPEN, 1.1);
  doorCreak(); clunk(); startHum();
  A.stepSend.gain.value = 0.55;
  amb.intensity = 0.03; hemi.intensity = 0.025;
  scene.fog.color.setHex(0x020203); scene.fog.near = 1; scene.fog.far = 16; fogFarT = 16;
  scene.background.setHex(0x000000);
  offFlickT = 1.3; FX.spike = 0.4;
  setTimeout(() => say('...', 1500), 1200);
  setTimeout(() => say('¿Hola?', 2200), 2900);
  setTimeout(() => { flashAvail = true; if (!flashUsed) $('fhint').style.display = 'block'; }, 3600);
  setTimeout(() => setObjective('Sal de la universidad por la <b>entrada principal</b>.'), 5400);
}

// =====================================================================
// FASE 2: salidas bloqueadas y el bucle del Pasillo B
// =====================================================================
function tryExit() {
  if (triedExit) { rattle(); say('No se mueve.', 2000); return; }
  triedExit = true; rattle();
  say('Está trancada. Las puertas no ceden... y afuera no se ve absolutamente nada.', 4500);
  setTimeout(() => setObjective('Busca otra salida. La <b>salida de emergencia</b> estaba a mitad del pasillo.'), 2500);
}
function lockedEmergency() {
  rattle();
  say('Bloqueada. El lector parpadea en rojo: «FALLA ELÉCTRICA — RESTABLECER EN PANEL (PASILLO B)».', 5200);
  if (!flags.knowsPanel) {
    flags.knowsPanel = true;
    setTimeout(() => setObjective('Busca el <b>panel eléctrico</b> en el <b>Pasillo B</b>, al fondo del corredor.'), 1800);
  }
}
function enterLoop() {
  LOOP.state = 1; flags.sDoorOpen = false;
  swing(sLeaf, 0, 0.3, true);
  setTimeout(() => { doorSlam(); FX.spike = 0.5; }, 260);
  setTimeout(() => say('...la puerta.', 2000), 1100);
  setTimeout(() => setObjective(flags.knowsPanel ? 'Encuentra el <b>panel eléctrico</b>. Sigue por el Pasillo B.' : 'Sigue por el <b>Pasillo B</b>.'), 2300);
}
function applyLoop() {   // cambios sutiles en cada vuelta
  const c = LOOP.count;
  if (c === 1) {
    LT.fl = 0.3; posterMat.map = posterB;
    whisperAt(0, 1.6, P.z - 5);
    setTimeout(() => say('¿No acabo de pasar por aquí?', 3000), 500);
  }
  if (c === 2) { LT.fl = 0.42; LT.base = 0.6; loopA.color.setHex(0xff7a58); loopB.color.setHex(0xff7a58); }
  if (c === CFG.loopNeeded) {
    loopMods.forEach(m => { m.sw.visible = true; m.scrawl.visible = true; });
    setTimeout(() => say('Ese panel... no estaba ahí antes.', 3200), 700);
    setObjective('Activa el <b>panel eléctrico</b>.');
  }
  if (c >= 3) {
    LT.base = 0.42; LT.fl = 0.55;
    const col = c % 2 ? 0x8fa0ff : 0xff6a48; loopA.color.setHex(col); loopB.color.setHex(col);
    LOOP.figHidden = false; loopMods.forEach(m => { m.fig.g.visible = m.k >= 1; });
  }
  if (c >= 4) setTimeout(() => say(['Otra vez.', 'No termina.', 'El panel. Tengo que usar el panel.'][Math.min(2, c - 4)], 2400), 600);
}
function figTick() {   // la silueta al fondo se desvanece al acercarse
  if (LOOP.figHidden) return;
  for (const m of loopMods) {
    const f = m.fig.g; if (!f.visible) continue;
    const dz = P.z - f.position.z;
    if (dz > 0 && Math.hypot(P.x - f.position.x, dz) < 6) {
      loopMods.forEach(o => o.fig.g.visible = false); LOOP.figHidden = true;
      whisperAt(f.position.x, 1.6, f.position.z); FX.spike = 0.6;
      return;
    }
  }
}
function pressSwitch() {
  if (LOOP.state !== 1) return;
  LOOP.state = 2;
  const m = loopMods.reduce((a, b) => Math.abs(b.z0 - 9 - P.z) < Math.abs(a.z0 - 9 - P.z) ? b : a);
  loopMods.forEach(o => { o.lever.rotation.z = -0.6; o.fig.g.visible = false; });
  M_swLed.color.setHex(0x22ff44); LOOP.figHidden = true;
  clunk(); sparks(-1.3, 1.4, m.z0 - 9); FX.spike = 0.8;
  LT.base = 0.85; LT.fl = 0.06; loopA.color.setHex(0xfff4e4); loopB.color.setHex(0xfff4e4);
  setTimeout(() => { flags.sDoorOpen = true; swing(sLeaf, 1.4, 1.3); doorCreak(); }, 900);
  setTimeout(() => {
    flags.emDoorOpen = true; swing(emLeaf, 0.35, 1.0); routeLit = true;
    M_led.color.setHex(0x22ff44); buzzerAt(2, -10);
  }, 1700);
  setTimeout(() => say('Algo se desbloqueó... lejos, en el pasillo principal.', 3400), 2200);
  setTimeout(() => setObjective('La <b>salida de emergencia</b> se abrió. Vuelve al pasillo principal.'), 2800);
}

function lightsTick(dt) {
  poolTick(dt, P.x, P.z);
  if (offFlickT > 0) {
    offFlickT -= dt; const on = Math.random() < 0.45 && offFlickT > 0;
    officeLight.l.intensity = on ? officeLight.p1 : 0;
    M_panelOffice.emissive.setHex(on ? 0xfff8ee : 0x080808);
  }
  for (const L of lights) {
    if (!L.fl) continue;
    L.ft -= dt;
    if (L.ft < 0) { L.ft = rand(0.04, 0.3); L.cur = Math.random() < L.fl ? L.base * rand(0, 0.25) : L.base * rand(0.85, 1.05); }
    L.l.intensity = L.cur;
  }
  if (worldBroken) { const k = mainFlickLight.cur / 0.38; M_panelFlick.emissive.setRGB(k * 0.9, k * 0.88, k * 0.82); }
  // Pasillo B: las dos luces se colocan en los dos centros de módulo más cercanos
  LT.ft -= dt;
  if (LT.ft < 0) { LT.ft = rand(0.05, 0.3); LT.cur = Math.random() < LT.fl ? LT.base * rand(0, 0.2) : LT.base * rand(0.85, 1.05); }
  const zs = LOOP_CENTERS.slice().sort((a, b) => Math.abs(a - P.z) - Math.abs(b - P.z));
  loopA.position.set(0, 2.85, zs[0]); loopB.position.set(0, 2.85, zs[1]);
  const li = worldBroken ? LT.cur : 0;
  loopA.intensity = li; loopB.intensity = li;
  M_panelLoop.emissive.copy(loopA.color).multiplyScalar(li / 0.85);
}

// =====================================================================
// FASE 3: persecución
// =====================================================================
function startChase(first) {
  phase = 'chase';
  MON.x = 0; MON.z = -26;    // sale del fondo del pasillo principal, desde el Pasillo B
  MON.trail = [{ x: 0, z: -12 }, { x: 0.6, z: -10 }, { x: 2.6, z: -10 }, { x: P.x, z: P.z }];
  MON.heading = 0; MON.speed = CFG.monster; MON.phase = 0;
  MON.bangT = 0.4; MON.hbT = 0.5; MON.faceT = 0; MON.hold = 0;
  EV.roarT = rand(5, 8); EV.breathT = 0.5;
  monster.visible = true; mHead.visible = true;
  const t = A.ctx.currentTime;
  A.raspOut.gain.setTargetAtTime(1, t, 0.2);
  A.hum.gain.setTargetAtTime(0.25, t, 0.4);
  wallBang(A.mBus); setTimeout(() => { if (phase === 'chase') wail(A.mBus, 0.95, 240, 1.3); }, 350);
  FX.spike = 0.7;
  if (first) {
    firstChase = false;
    setTimeout(() => hint('C O R R E   ·   S H I F T', 2600), 700);
    setObjective('Encuentra la <b>salida</b>. No te detengas.');
  }
}
// ---------- Cinemática: el jugador se detiene, mira atrás y el monstruo revienta la puerta
function startIntro() {
  phase = 'intro';
  INTRO.t = 0; INTRO.arrived = false; INTRO.turnBack = false; INTRO.shake = 0;
  P.vx = P.vz = 0; P.speed = 0; P.running = false;
  MON.x = 0; MON.z = -24; MON.trail = [{ x: 0, z: -12 }, { x: 0.6, z: -10 }, { x: 2.0, z: -10 }];
  MON.heading = 0; MON.speed = 0; MON.phase = 0; MON.faceT = 0; MON.sway = 0; MON.swayT = 0;
  monster.visible = true; mHead.visible = true;
  monster.position.set(MON.x, 0, MON.z);
  const t = A.ctx.currentTime;
  A.raspOut.gain.setTargetAtTime(0.6, t, 0.4);
  A.hum.gain.setTargetAtTime(0.2, t, 0.4);
  setTimeout(() => { wallBang(A.mBus); setPannerPos(A.mPan, 0, 1.5, -22); }, 150);
  setTimeout(() => say('...', 1200), 300);
}
function cineMonster(dt, speed) {
  let move = speed * dt, dx = 0, dz = 0;
  while (move > 0 && MON.trail.length) {
    const tg = MON.trail[0], ex = tg.x - MON.x, ez = tg.z - MON.z, d = Math.hypot(ex, ez);
    if (d <= move) { MON.x = tg.x; MON.z = tg.z; move -= d; MON.trail.shift(); if (d > 1e-4) { dx = ex / d; dz = ez / d; } }
    else { dx = ex / d; dz = ez / d; MON.x += dx * move; MON.z += dz * move; move = 0; }
  }
  if (dx || dz) MON.heading += angDiff(MON.heading, Math.atan2(dx, dz)) * (1 - Math.exp(-dt * 10));
  if (dx || dz) {
    const prev = MON.phase; MON.phase += dt * speed / 2.5;
    const p0 = prev % 1, p1 = MON.phase % 1;
    for (const s of [0.001, 0.17, 0.5, 0.68]) {
      const crossed = p1 >= p0 ? (s > p0 && s <= p1) : (s > p0 || s <= p1);
      if (crossed) monsterStep(s < 0.1 || (s > 0.4 && s < 0.6));
    }
  } else MON.phase += dt * 0.25;
  monster.position.set(MON.x, 0, MON.z); monster.rotation.y = MON.heading;
  animateMonster(dt);
  setPannerPos(A.mPan, MON.x, 1.5, MON.z);
  MON.faceT -= dt;
  if (MON.faceT < 0) { drawMonsterFace(monFace, INTRO.arrived && Math.random() < 0.6, 0.3); MON.faceT = rand(0.07, 0.15); }
}
function introTick(dt) {
  INTRO.t += dt; const t = INTRO.t;
  P.x = lerp(P.x, 5.4, Math.min(1, dt * 2.2)); P.z = lerp(P.z, -10, Math.min(1, dt * 2.2));
  let yawT, rate;
  if (INTRO.turnBack) { yawT = -Math.PI / 2; rate = 10; }          // vuelve a mirar el pasillo
  else if (t > 0.45) { yawT = Math.PI / 2; rate = 3.4; }            // mira hacia la puerta
  else { yawT = P.yaw; rate = 0; }
  P.yaw += angDiff(P.yaw, yawT) * Math.min(1, dt * rate);
  P.pitch = lerp(P.pitch, INTRO.arrived && !INTRO.turnBack ? 0.08 : 0, Math.min(1, dt * 3));
  if (t > 0.8) cineMonster(dt, INTRO.arrived ? 0 : CFG.cineSpeed);
  else { monster.position.set(MON.x, 0, MON.z); animateMonster(dt); }
  if (!INTRO.arrived && !MON.trail.length) {
    INTRO.arrived = true; INTRO.at = t; INTRO.shake = 1;
    swing(emLeaf, 1.25, 0.12, true);
    wallBang(A.mBus); doorSlam(); wail(A.mBus, 1.0, 230, 1.4);
    A.raspOut.gain.setTargetAtTime(1, A.ctx.currentTime, 0.1);
    FX.spike = 0.9; heartbeat(1);
  }
  if (INTRO.arrived && !INTRO.turnBack && t > INTRO.at + 1.15) { INTRO.turnBack = true; INTRO.tb = t; }
  if (INTRO.turnBack && t > INTRO.tb + 0.35) { beginChaseFromIntro(); return; }
  INTRO.shake *= Math.exp(-dt * 2.5);
  const sh = INTRO.shake * 0.03;
  camera.fov = lerp(camera.fov, INTRO.arrived && !INTRO.turnBack ? 62 : CFG.fov, Math.min(1, dt * 5)); camera.updateProjectionMatrix();
  camera.position.set(P.x + rand(-sh, sh), EYE + rand(-sh, sh), P.z + rand(-sh, sh));
  camera.rotation.set(P.pitch + rand(-sh, sh), P.yaw + rand(-sh, sh), rand(-sh, sh) * 0.6);
}
function beginChaseFromIntro() {
  phase = 'chase'; firstChase = false;
  MON.trail = [{ x: P.x, z: P.z }]; MON.speed = CFG.monster; MON.hold = CFG.headStart;
  MON.bangT = 1.2; MON.hbT = 0.3;
  EV.roarT = rand(5, 8); EV.breathT = 0.3;
  hint('C O R R E   ·   S H I F T', 2600);
  setObjective('Encuentra la <b>salida</b>. No te detengas.');
}
function chaseEvents(dt, dP) {
  EV.roarT -= dt;
  if (EV.roarT < 0) { wail(A.mBus, 0.7, rand(230, 300), 1.1); EV.roarT = rand(7, 12); }
  EV.breathT -= dt;
  if (EV.breathT < 0 && P.running) { breath(EV.breathIn); EV.breathIn = !EV.breathIn; EV.breathT = EV.breathIn ? 0.36 : 0.3; }
  if (!EV.cornerC && P.z < -60 && P.x < 30) { EV.cornerC = true; rattleAt(4.2, -61.6); }
  if (!EV.lightsOut && P.z < -67 && P.x < 9) {
    EV.lightsOut = true;
    D_ANCH.forEach((a, i) => setTimeout(() => {
      if (phase !== 'chase') return;
      a.dead = true; a.cur = 0; a.lamp.material = M_panelOff; sparks(a.x, 2.9, a.z); FX.spike = 0.5;
    }, 120 + i * 380));
    setTimeout(() => { if (phase === 'chase') wail(A.mBus, 1.0, 210, 1.4); }, 900);
  }
  if (!EV.cornerE && P.z < -110 && P.x > 10) { EV.cornerE = true; say('¡La luz! ¡Ahí!', 1800); }
  const k = clamp(1 - dP / 6, 0, 1);
  FX.prox = clamp(1 - dP / 10, 0, 1);
  FX.red = k * (0.25 + 0.15 * Math.sin(T * 14));
}
function resetChaseEvents() {
  EV.lightsOut = false; EV.cornerC = false; EV.cornerE = false;
  for (const a of anchors) if (a.dead) { a.dead = false; a.lamp.material = M_emLamp; }
}
function updateMonster(dt) {
  const last = MON.trail[MON.trail.length - 1];
  if (!last || Math.hypot(P.x - last.x, P.z - last.z) > 0.55) MON.trail.push({ x: P.x, z: P.z });
  const dP = Math.hypot(P.x - MON.x, P.z - MON.z);
  let target = CFG.monster; if (dP > CFG.leash) target = CFG.catchup;
  MON.speed = lerp(MON.speed, target, 1 - Math.exp(-dt * 2.5));
  let move = MON.hold > 0 ? 0 : MON.speed * dt, dx = 0, dz = 0;
  if (MON.hold > 0) MON.hold -= dt;
  while (move > 0 && MON.trail.length) {
    const tg = MON.trail[0], ex = tg.x - MON.x, ez = tg.z - MON.z, d = Math.hypot(ex, ez);
    if (d <= move) { MON.x = tg.x; MON.z = tg.z; move -= d; MON.trail.shift(); if (d > 1e-4) { dx = ex / d; dz = ez / d; } }
    else { dx = ex / d; dz = ez / d; MON.x += dx * move; MON.z += dz * move; move = 0; }
  }
  if (move > 0) { const ex = P.x - MON.x, ez = P.z - MON.z, d = Math.hypot(ex, ez) || 1; dx = ex / d; dz = ez / d; MON.x += dx * Math.min(move, d); MON.z += dz * Math.min(move, d); }
  if (dx || dz) MON.heading += angDiff(MON.heading, Math.atan2(dx, dz)) * (1 - Math.exp(-dt * 8));

  A.mSub.gain.setTargetAtTime(clamp(1.15 - dP / 18, 0.25, 1.15), A.ctx.currentTime, 0.05);
  const prev = MON.phase; MON.phase += dt * MON.speed / 2.5;
  const p0 = prev % 1, p1 = MON.phase % 1;
  for (const s of [0.001, 0.17, 0.5, 0.68]) {
    const crossed = p1 >= p0 ? (s > p0 && s <= p1) : (s > p0 || s <= p1);
    if (crossed) monsterStep(s < 0.1 || (s > 0.4 && s < 0.6));
  }
  MON.bangT -= dt;
  if (MON.bangT < 0) { wallBang(A.mBus); MON.bangT = rand(0.8, 2.0); MON.swayT = Math.random() < 0.5 ? -1 : 1; }
  MON.sway = lerp(MON.sway, MON.swayT * 0.55 + Math.sin(T * 2.3) * 0.25, 1 - Math.exp(-dt * 4));

  const px = Math.cos(MON.heading), pz = -Math.sin(MON.heading);
  monster.position.set(MON.x + px * MON.sway, 0, MON.z + pz * MON.sway);
  monster.rotation.y = MON.heading;
  animateMonster(dt);
  setPannerPos(A.mPan, MON.x, 1.5, MON.z);

  MON.faceT -= dt;   // el rostro "hierve": se re-dibuja con glitches
  if (MON.faceT < 0) { drawMonsterFace(monFace, Math.random() < 0.3, 0.2 + FX.prox * 0.8); MON.faceT = rand(0.08, 0.18); }

  MON.hbT -= dt;
  if (MON.hbT < 0) { const k = clamp(1 - dP / 16, 0, 1); heartbeat(0.3 + k * 0.7); MON.hbT = lerp(0.8, 0.3, k); }
  if (dP < 6 && Math.random() < 0.12) flash.intensity *= rand(0.1, 0.6);

  if (dP < CFG.catchDist) caught();
  return dP;
}
function animateMonster(dt) {
  const ph = MON.phase * Math.PI * 2;
  mLimbs[0].sh.rotation.x = 0.45 * Math.sin(ph); mLimbs[0].el.rotation.x = -0.5 + 0.35 * Math.sin(ph + 1.2);
  mLimbs[1].sh.rotation.x = 0.45 * Math.sin(ph + 1.1); mLimbs[1].el.rotation.x = -0.5 + 0.35 * Math.sin(ph + 2.3);
  mLimbs[2].sh.rotation.x = 0.6 + 0.45 * Math.sin(ph + Math.PI); mLimbs[2].el.rotation.x = -1.2 + 0.3 * Math.sin(ph + 4.1);
  mLimbs[3].sh.rotation.x = 0.6 + 0.45 * Math.sin(ph + Math.PI + 1.1); mLimbs[3].el.rotation.x = -1.2 + 0.3 * Math.sin(ph + 5.2);
  mLimbs[0].sh.rotation.z = mLimbs[0].spread - MON.sway * 0.25; mLimbs[1].sh.rotation.z = mLimbs[1].spread - MON.sway * 0.25;
  mBody.position.y = 1.05 + 0.09 * Math.abs(Math.sin(ph * 2));
  mBody.rotation.z = 0.12 * Math.sin(ph) + MON.sway * 0.18;
  neckSegs.forEach((s, i) => { s.g.rotation.x = s.a + 0.07 * Math.sin(T * 7 + i * 0.9); s.g.rotation.z = 0.13 * Math.sin(T * 3.1 + i * 0.7); });
  monster.updateMatrixWorld(true);
  mHead.lookAt(camera.position);
  mHead.rotateZ(Math.sin(T * 1.7) * 0.5);
}
function caught() {   // JUMPSCARE
  phase = 'caught'; deaths++; scareT = 0;
  const t = A.ctx.currentTime; A.raspOut.gain.setTargetAtTime(0, t, 0.05); A.mSub.gain.setTargetAtTime(0, t, 0.05);
  scream();
  const dx = MON.x - P.x, dz = MON.z - P.z, d = Math.hypot(dx, dz) || 1; scareDir = { x: dx / d, z: dz / d };
  mHead.visible = false; scareHead.visible = true; flashOn = true;
  $('hint').style.opacity = 0;
  setTimeout(() => fade(1, 0.12), 1250);
  setTimeout(respawn, 1750);
}
// Reaparece JUSTO ANTES de la salida de emergencia, sin monstruo.
function respawn() {
  phase = 'dark';
  P.x = -0.6; P.z = -10; P.yaw = -Math.PI / 2; P.pitch = 0; P.vx = P.vz = 0;
  scareHead.visible = false; monster.visible = false; MON.trail = [];
  FX.red = 0; FX.prox = 0;
  camera.fov = CFG.fov; camera.updateProjectionMatrix();
  flashOn = true; resetChaseEvents();
  A.hum.gain.setTargetAtTime(0.55, A.ctx.currentTime, 0.5);
  setTimeout(() => fade(0, 0.8), 250);
  setTimeout(() => say('Otra vez aquí... La salida de emergencia.', 2600), 900);
}
function updateCaught(dt) {
  scareT += dt;
  const cam = camera.position;
  const k = Math.min(1, scareT / 0.1);
  const dist = lerp(1.6, 0.58, k);
  scareHead.position.set(cam.x + scareDir.x * dist + rand(-0.02, 0.02), EYE - 0.05 + rand(-0.02, 0.02), cam.z + scareDir.z * dist + rand(-0.02, 0.02));
  scareHead.lookAt(cam); scareHead.rotateZ(Math.sin(scareT * 40) * 0.15);
  drawMonsterFace(scareFace, true, 1);
  monster.position.set(cam.x + scareDir.x * 2.3, 0, cam.z + scareDir.z * 2.3);
  monster.rotation.y = Math.atan2(-scareDir.x, -scareDir.z);
  animateMonster(dt);
  const yawT = Math.atan2(-scareDir.x, -scareDir.z);
  P.yaw += angDiff(P.yaw, yawT) * Math.min(1, dt * 25); P.pitch = lerp(P.pitch, 0.05, Math.min(1, dt * 25));
  camera.fov = lerp(camera.fov, 50, Math.min(1, dt * 12)); camera.updateProjectionMatrix();
  camera.position.set(P.x + rand(-0.04, 0.04), EYE + rand(-0.04, 0.04), P.z + rand(-0.04, 0.04));
  camera.rotation.set(P.pitch + rand(-0.03, 0.03), P.yaw + rand(-0.03, 0.03), rand(-0.08, 0.08));
  FX.red = Math.random() < 0.5 ? 0.9 : 0.35;
}

// =====================================================================
// FASE 5: el vestíbulo, la ciudad vacía y el reflejo
// =====================================================================
function startVestibule() {
  phase = 'vestibule';
  flags.safeDoorOpen = false; swing(safeLeaf, SAFE_CLOSED, 0.22, true);
  monster.visible = false;
  const t = A.ctx.currentTime; A.raspOut.gain.setTargetAtTime(0, t, 0.05); A.mSub.gain.setTargetAtTime(0, t, 0.05);
  $('hint').style.opacity = 0; FX.red = 0; FX.prox = 0;
  setTimeout(() => { doorSlam(); FX.spike = 0.5; }, 180);
  setPannerPos(A.mPan, 59.2, 1.5, -112);
  setTimeout(() => wallBang(A.mBus), 1000);
  // ...y después: silencio absoluto
  A.hum.gain.setTargetAtTime(0.0001, t + 1.5, 1.2);
  // luz de luna y cielo nocturno
  moonLight.intensity = 0.65; amb.color.setHex(0x7d8db0); amb.intensity = 0.1; hemi.intensity = 0.06;
  scene.fog.color.setHex(0x0a1222); scene.background.setHex(0x0a1426);
  scene.fog.near = 30; scene.fog.far = 330; fogFarT = 330;
  camera.far = 1200; camera.updateProjectionMatrix();
  setTimeout(() => say('...ya no lo escucho.', 2600), 3200);
  setTimeout(() => setObjective('Sal por la <b>puerta de cristal</b>.'), 4200);
}
function pushGlass() {
  rattle();
  if (!VST.tried) {
    VST.tried = true;
    say('Trancada. Afuera no hay nadie... ni un solo auto. Nada se mueve.', 4200);
    setTimeout(() => say('En el vidrio solo se ve mi reflejo.', 3200), 4600);
    setObjective('');
  } else say('No cede.', 1600);
}
function reflTick() {
  const show = (phase === 'vestibule' || phase === 'final') && P.x > 62;
  reflGroup.visible = show;
  if (!show) return;
  const fx = -Math.sin(P.yaw), fz = -Math.cos(P.yaw);
  const ry = Math.atan2(-fx, fz);                           // orientación especular
  reflMe.g.position.set(2 * GLASS_X - P.x, 0, P.z); reflMe.g.rotation.y = ry;
  reflMe.head.rotation.y = 0;
  const near = clamp((P.x - 64) / 6, 0, 1), lit = flashOn ? 1 : 0.35;
  ghostMats.me.forEach(m => m.opacity = 0.6 * near * lit);
  const fp = camera.localToWorld(new THREE.Vector3(0.18, -0.12, -0.05));
  glare.position.set(2 * GLASS_X - fp.x, fp.y, fp.z); glare2.position.copy(glare.position);
  glare.visible = glare2.visible = flashOn && near > 0;
  glare.material.opacity = near; glare2.material.opacity = 0.25 * near;
  // criatura: justo detrás del jugador real, reflejada
  const sx = -fz, sz = fx;   // vector lateral
  const bx = P.x - fx * 0.8 + sx * 0.32, bz = P.z - fz * 0.8 + sz * 0.32;
  tall.position.set(2 * GLASS_X - bx, 0, bz); tall.rotation.y = ry;
  const k = VST.k * near;
  ghostMats.tall.forEach((m, i) => m.opacity = (m.map === monFace.t ? 0.95 : 0.6) * k);
  tall.visible = k > 0.001;
  if (tall.visible) {
    tall.updateMatrixWorld(true);
    tallHead.lookAt(camera.position.x, camera.position.y, camera.position.z);
    tallHead.rotateZ(Math.sin(T * 1.3) * 0.25);
    MON.faceT -= 0.016; if (MON.faceT < 0) { drawMonsterFace(monFace, false, 0.15); MON.faceT = 0.2; }
  }
}
function vestibuleTick(dt) {
  camera.getWorldDirection(_fwd);
  const looking = _fwd.x > 0.9 && Math.abs(P.z + 112) < 4.5 && P.x > 68.8;
  if (!VST.revealed) {
    if (VST.tried && looking && flashOn) VST.stare += dt; else VST.stare = Math.max(0, VST.stare - dt * 0.5);
    if (VST.tried && looking && !flashOn) {
      VST.noFlashT += dt;
      if (VST.noFlashT > 2 && !VST.hinted) { VST.hinted = true; say('Está muy oscuro para verme... la linterna. [F]', 3200); }
    }
    if (VST.stare > CFG.stareTime) { VST.revealed = true; VST.revT = 0; stingBehind(); FX.spike = 0.25; }
  } else {
    VST.revT += dt; VST.k = Math.min(1, VST.k + dt * 1.6);
    if (_fwd.x < -0.1) startFinal(false);          // se dio la vuelta
    else if (VST.revT > 6.5) startFinal(true);     // no se voltea: la cámara lo hace sola
  }
}
function startFinal(auto) {
  phase = 'final'; FINAL.t = 0; FINAL.auto = auto; FINAL.thud = false;
  FINAL.yaw = Math.PI / 2;                          // mirar hacia el interior (-X)
  VST.k = 0; tall.visible = false;                 // en la habitación real no hay nada
  $('prompt').style.opacity = 0;
}
function finalTick(dt) {
  FINAL.t += dt; const t = FINAL.t;
  if (FINAL.auto) { P.yaw += angDiff(P.yaw, FINAL.yaw) * Math.min(1, dt * 14); P.pitch = lerp(P.pitch, 0, Math.min(1, dt * 10)); }
  // la luz parpadea
  if (t > 0.25 && t < 1.25) {
    const on = Math.random() < 0.4;
    safeLight.l.intensity = on ? 0.9 : 0; M_lobbyLamp.color.setHex(on ? 0xe6ecf8 : 0x101214);
    if (Math.random() < 0.08) buzzFlicker();
  }
  if (t >= 1.25 && !FINAL.thud) {                  // golpe seco y negro inmediato
    FINAL.thud = true;
    safeLight.l.intensity = 0; M_lobbyLamp.color.setHex(0x101214);
    thudFinal(); fade(1, 0.04);
    setTimeout(showTitle, 700);
  }
  camera.position.set(P.x, EYE, P.z);
  camera.rotation.set(P.pitch, P.yaw, 0);
}
function showTitle() {
  phase = 'end';
  if (document.exitPointerLock) document.exitPointerLock();
  const e = $('end'); e.style.display = 'flex'; $('rec').style.display = 'none';
  e.querySelector('h1').style.transition = 'opacity 2.5s';
  requestAnimationFrame(() => { e.querySelector('h1').style.opacity = 1; });
  setTimeout(() => e.querySelectorAll('p')[0].style.opacity = 1, 3500);
  setTimeout(() => { e.querySelectorAll('p')[1].style.opacity = 1; e.dataset.ready = '1'; }, 6500);
}

// =====================================================================
// BUCLE PRINCIPAL
// =====================================================================
function movePlayer(dt) {
  const f = ((keys.KeyW || keys.ArrowUp) ? 1 : 0) - ((keys.KeyS || keys.ArrowDown) ? 1 : 0);
  const s = ((keys.KeyD || keys.ArrowRight) ? 1 : 0) - ((keys.KeyA || keys.ArrowLeft) ? 1 : 0);
  const fx = -Math.sin(P.yaw), fz = -Math.cos(P.yaw), rx = Math.cos(P.yaw), rz = -Math.sin(P.yaw);
  let ix = fx * f + rx * s, iz = fz * f + rz * s; const il = Math.hypot(ix, iz); if (il > 0) { ix /= il; iz /= il; }
  const running = (keys.ShiftLeft || keys.ShiftRight) && il > 0;
  P.running = running;
  const sp = running ? CFG.sprint : CFG.walk;
  const k = 1 - Math.exp(-dt * 10);
  P.vx = lerp(P.vx, ix * sp, k); P.vz = lerp(P.vz, iz * sp, k);
  const nx = P.x + P.vx * dt; if (walkable(nx, P.z)) P.x = nx; else P.vx *= 0.2;
  const nz = P.z + P.vz * dt; if (walkable(P.x, nz)) P.z = nz; else P.vz *= 0.2;
  P.speed = Math.hypot(P.vx, P.vz);
  P.stepAcc += P.speed * dt;
  if (P.stepAcc > (running ? 0.9 : 0.72)) { P.stepAcc = 0; playerStep(running); }
  P.bob += P.speed * dt * 2.1;
  const fovT = CFG.fov + (running ? 6 : 0);
  camera.fov = lerp(camera.fov, fovT, Math.min(1, dt * 4)); camera.updateProjectionMatrix();
}
function npcTick(dt) {
  if (worldBroken || phase === 'title') return;
  for (const n of npcs) {
    n.t += dt;
    if (n.walk) {
      const p = n.g.position;
      const ahead = (P.z - p.z) * n.dir > 0 && Math.hypot(P.x - p.x, P.z - p.z) < 1.2;
      if (!ahead) {
        p.z += n.dir * n.speed * dt;
        if (p.z < n.z1) { p.z = n.z1; n.dir = 1; } if (p.z > n.z2) { p.z = n.z2; n.dir = -1; }
      }
      n.g.rotation.y = n.dir > 0 ? 0 : Math.PI;
      const sw = ahead ? 0 : Math.sin(n.t * n.speed * 5) * 0.5;
      n.legs[0].rotation.x = sw; n.legs[1].rotation.x = -sw; n.arms[0].rotation.x = -sw * 0.7; n.arms[1].rotation.x = sw * 0.7;
    } else {
      n.head.rotation.y = Math.sin(n.t * 0.7) * 0.3;
      if (!n.phone) n.arms[0].rotation.x = -0.25 - Math.max(0, Math.sin(n.t * 1.9)) * 0.5;
      n.g.position.y = Math.sin(n.t * 1.3) * 0.005;
    }
  }
}
function update(dt) {
  T += dt;
  lightsTick(dt);
  animsTick(dt);
  const inS = P.z < -40.4 && Math.abs(P.x) < 1.6;
  fxTick(dt, inS);
  if (phase === 'caught') { updateCaught(dt); if (A.ctx) updateListener(); return; }
  reflTick();
  if (phase === 'final') { finalTick(dt); if (A.ctx) updateListener(); return; }
  if (phase === 'intro') { introTick(dt); if (A.ctx) updateListener(); return; }
  const canMove = phase === 'normal' || phase === 'office' || phase === 'delivered' || phase === 'dark' || phase === 'chase' || phase === 'vestibule';
  if (canMove) movePlayer(dt); else { P.vx = P.vz = 0; P.speed = 0; P.running = false; }
  npcTick(dt);

  let shake = 0;
  if (phase === 'normal' && P.x < -3.2 && P.z < -30) closeOffice();
  if (phase === 'dark') {
    if (!triedExit && P.z > 0.3) tryExit();
    if (LOOP.state === 0 && inS && P.z < -44.5) enterLoop();
    if (LOOP.state === 1) {
      if (P.z < -40 - 2 * MOD) { P.z += MOD; LOOP.count++; FX.spike = Math.max(FX.spike, 0.35); applyLoop(); }
      figTick();
    }
    if (flags.emDoorOpen && P.x > 3.6 && P.z < -7.5 && P.z > -12.5) { if (firstChase) startIntro(); else startChase(false); }
    if (LOOP.state !== 1) { phoneT -= dt; if (phoneT < 0) { phoneBuzz(); phoneT = 2.8; } }
    fogFarT = inS ? 9.5 : 16;
  }
  if (phase === 'chase') {
    fogFarT = 20;
    const dP = updateMonster(dt);
    if (phase === 'chase') {
      chaseEvents(dt, dP);
      shake = clamp(1 - dP / 9, 0, 1) * 0.016;
      if (P.x > 61.2 && P.z < -104 && P.z > -120) startVestibule();
    }
  }
  if (phase === 'vestibule') vestibuleTick(dt);
  if (worldBroken && phase !== 'office' && phase !== 'delivered' && phase !== 'vestibule') scene.fog.far = lerp(scene.fog.far, fogFarT, Math.min(1, dt * 2));

  const flashTarget = flashOn ? 1.6 : 0;
  flash.intensity = lerp(flash.intensity, flashTarget, Math.min(1, dt * 12));
  if (trayGlow.visible) trayGlow.material.opacity = 0.25 + 0.25 * Math.sin(T * 3);
  handPaper.position.y = -0.27 + Math.sin(P.bob * 2) * 0.008;

  const bobAmt = Math.min(1, P.speed / 3);
  camera.position.set(P.x + rand(-shake, shake), EYE + Math.sin(P.bob * 2) * 0.035 * bobAmt + rand(-shake, shake), P.z + rand(-shake, shake));
  camera.rotation.set(P.pitch, P.yaw, Math.sin(P.bob) * 0.006 * bobAmt + rand(-shake, shake) * 0.6);
  interactTick();
  if (A.ctx) updateListener();
}
let lastT = performance.now();
function loop(now) {
  requestAnimationFrame(loop);
  const dt = Math.min(0.05, (now - lastT) / 1000); lastT = now;
  if (!paused && phase !== 'title' && phase !== 'end') update(dt);
  post.uniforms.uTime.value = now / 1000;
  renderer.setRenderTarget(rt); renderer.render(scene, camera);
  renderer.setRenderTarget(null); renderer.render(postScene, postCam);
}
camera.position.set(P.x, EYE, P.z);
requestAnimationFrame(loop);
</script>
</body>
</html>
"""


def construir_html() -> str:
    """Inserta título, fecha, versión y parámetros de juego en la plantilla."""
    return (
        HTML_TEMPLATE
        .replace("__TITLE__", TITULO)
        .replace("__VERSION__", VERSION)
        .replace("__DATE__", datetime.now().strftime("%Y-%m-%d %H:%M"))
        .replace("__CONFIG__", json.dumps(CONFIG, ensure_ascii=False))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Genera la demo '{TITULO}' en un único archivo HTML.")
    parser.add_argument("-o", "--salida", default="index.html", help="archivo de salida (por defecto: index.html)")
    parser.add_argument("--abrir", action="store_true", help="abrir el juego en el navegador al terminar")
    args = parser.parse_args()

    destino = Path(args.salida).resolve()
    html = construir_html()
    destino.write_text(html, encoding="utf-8")

    print(f"[OK] '{TITULO}' v{VERSION} generado en: {destino}")
    print(f"     Tamaño: {len(html.encode('utf-8')) / 1024:.1f} KB")
    print("     Abre el archivo en Chrome, Edge o Firefox. Usa auriculares.")

    if args.abrir:
        webbrowser.open(destino.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
