/**
 * aqi-dust.js
 * ────────────
 * AQI-reactive WebGL particle (dust haze) background for the AIRWISE home hero.
 * Built from scratch with plain Three.js r149 UMD (no modules, no bundler).
 *
 * Exposes:  window.AQIDust = { setAQI(value), setCity(name), pause(), resume() }
 *
 * Design notes
 * ─────────────
 * - Single full-screen <canvas id="aqi-dust-canvas">, pointer-events:none, z-index below hero text.
 * - THREE.Points with custom ShaderMaterial - additive blending, depthWrite:false.
 * - 4000-6000 particles (desktop), ~40% on narrow screens.
 * - Per-particle random seed attribute drives size, phase & visibility threshold.
 * - Vertex shader: slow curl-like sway (sin/cos of position + time) + very slow global rotation.
 * - AQI mapped smoothly (~1 s lerp) to: density, drift speed, particle size, alpha, tint.
 * - CPCB 6-band palette with inter-band blending.
 * - Gentle pointer parallax on camera, smoothed.
 * - IntersectionObserver + MutationObserver - render loop runs ONLY while hero is active.
 * - prefers-reduced-motion -> one static frame, no animation loop.
 * - try/catch guard: if WebGL is unavailable, canvas is hidden, page continues normally.
 */

(function () {
  'use strict';

  // Guard: require Three.js
  if (typeof THREE === 'undefined') {
    console.warn('[AQIDust] THREE.js not loaded - dust effect disabled.');
    window.AQIDust = { setAQI: function(){}, setCity: function(){}, pause: function(){}, resume: function(){} };
    return;
  }

  // CPCB AQI Palette (hex values mirror the CSS vars in styles.css)
  // Desaturated / darkened slightly so they read as refined haze tint.
  var AQI_BANDS = [
    { max:  50, r: 0.04, g: 0.55, b: 0.35 },  // Good        #10b981 -> muted
    { max: 100, r: 0.35, g: 0.62, b: 0.08 },  // Satisfactory #84cc16 -> muted
    { max: 200, r: 0.70, g: 0.46, b: 0.02 },  // Moderate     #f59e0b -> muted
    { max: 300, r: 0.72, g: 0.28, b: 0.04 },  // Poor         #f97316 -> muted
    { max: 400, r: 0.65, g: 0.12, b: 0.12 },  // Very Poor    #ef4444 -> muted
    { max: 500, r: 0.40, g: 0.05, b: 0.05 },  // Severe       #991b1b -> muted
  ];

  function aqiToColor(aqi) {
    var v = Math.max(0, Math.min(500, aqi));
    for (var i = 0; i < AQI_BANDS.length; i++) {
      var lo = i === 0 ? 0 : AQI_BANDS[i - 1].max;
      var hi = AQI_BANDS[i].max;
      if (v <= hi) {
        var t = (v - lo) / (hi - lo);
        var prev = i === 0 ? AQI_BANDS[0] : AQI_BANDS[i - 1];
        var next = AQI_BANDS[i];
        return {
          r: prev.r + (next.r - prev.r) * t,
          g: prev.g + (next.g - prev.g) * t,
          b: prev.b + (next.b - prev.b) * t,
        };
      }
    }
    return AQI_BANDS[AQI_BANDS.length - 1];
  }

  // Shaders
  var VERT_SHADER = [
    'attribute float aSeed;',
    'attribute float aThreshold;',
    '',
    'uniform float uTime;',
    'uniform float uDensity;',
    'uniform float uDriftSpeed;',
    'uniform float uPointSize;',
    'uniform float uPixelRatio;',
    '',
    'varying float vAlpha;',
    'varying float vSeed;',
    '',
    'vec3 drift(vec3 pos, float t) {',
    '  float px = pos.x * 0.18 + t * uDriftSpeed;',
    '  float py = pos.y * 0.14 + t * uDriftSpeed * 0.7;',
    '  float pz = pos.z * 0.12 + t * uDriftSpeed * 0.55;',
    '  float dx = sin(py + t * 0.31) * 0.9 + cos(pz + t * 0.19) * 0.5;',
    '  float dy = sin(pz + t * 0.23) * 0.7 + cos(px + t * 0.27) * 0.4;',
    '  float dz = sin(px + t * 0.17) * 0.6 + cos(py + t * 0.21) * 0.35;',
    '  return vec3(dx, dy, dz) * 0.4;',
    '}',
    '',
    'vec3 rotateY(vec3 p, float angle) {',
    '  float c = cos(angle); float s = sin(angle);',
    '  return vec3(p.x * c + p.z * s, p.y, -p.x * s + p.z * c);',
    '}',
    '',
    'void main() {',
    '  vSeed = aSeed;',
    '  if (aThreshold > uDensity) {',
    '    vAlpha = 0.0;',
    '    gl_Position = vec4(9999.0, 9999.0, 9999.0, 1.0);',
    '    gl_PointSize = 0.0;',
    '    return;',
    '  }',
    '  vec3 pos = position;',
    '  pos += drift(position, uTime);',
    '  pos = rotateY(pos, uTime * 0.0052);',
    '  vec4 mvPos = modelViewMatrix * vec4(pos, 1.0);',
    '  gl_Position = projectionMatrix * mvPos;',
    '  float sizeVar = 0.6 + aSeed * 0.8;',
    '  gl_PointSize = uPointSize * sizeVar * uPixelRatio * (180.0 / -mvPos.z);',
    '  gl_PointSize = clamp(gl_PointSize, 1.0, 22.0);',
    '  float edgeDist = (uDensity - aThreshold) * 6.0;',
    '  float fade = clamp(edgeDist, 0.0, 1.0);',
    '  float depthFade = clamp(1.0 + mvPos.z * 0.012, 0.2, 1.0);',
    '  vAlpha = fade * depthFade;',
    '}',
  ].join('\n');

  var FRAG_SHADER = [
    'uniform vec3  uTint;',
    'uniform float uBaseAlpha;',
    '',
    'varying float vAlpha;',
    'varying float vSeed;',
    '',
    'void main() {',
    '  vec2 uv = gl_PointCoord - 0.5;',
    '  float d = length(uv) * 2.0;',
    '  float circle = 1.0 - smoothstep(0.5, 1.0, d);',
    '  if (circle < 0.01) discard;',
    '  float core = 1.0 - smoothstep(0.0, 0.5, d);',
    '  vec3 col = uTint + core * 0.08 * vec3(vSeed, vSeed * 0.7, vSeed * 0.5);',
    '  float a = circle * vAlpha * uBaseAlpha;',
    '  gl_FragColor = vec4(col, a);',
    '}',
  ].join('\n');

  // State
  var state = {
    aqiTarget:   120,
    aqiCurrent:  120,
    densityCur:  0.0,
    densityTgt:  0.0,
    driftCur:    1.0,
    driftTgt:    1.0,
    sizeCur:     2.8,
    sizeTgt:     2.8,
    alphaCur:    0.55,
    alphaTgt:    0.55,
    tintCur:     { r: 0.70, g: 0.46, b: 0.02 },
    tintTgt:     { r: 0.70, g: 0.46, b: 0.02 },
    running:     false,
    rafId:       null,
    reducedMotion: false,
  };

  function aqiToDensity(aqi)    { return 0.25 + 0.75 * Math.min(1, aqi / 500); }
  function aqiToDrift(aqi)      { return 0.28 + 0.72 * (1 - Math.min(1, aqi / 500)); }
  function aqiToSize(aqi)       { return 2.4  + 2.2  * Math.min(1, aqi / 500); }
  function aqiToAlpha(aqi)      { return 0.38 + 0.42 * Math.min(1, aqi / 500); }

  function lerp(a, b, t)        { return a + (b - a) * t; }
  function lerpCol(a, b, t) {
    return { r: lerp(a.r, b.r, t), g: lerp(a.g, b.g, t), b: lerp(a.b, b.b, t) };
  }

  // Three.js objects
  var renderer, scene, camera, points, material, starPoints, starMaterial;
  var canvas;
  var W = 0, H = 0;
  var resizeTimer = null;
  var pointer = { x: 0, y: 0, tx: 0, ty: 0 };
  var clockStart = null;
  var lastTime   = 0;

  function particleCount() {
    return window.innerWidth < 768 ? 1800 : 5000;
  }

  function buildGeometry(count) {
    var geo    = new THREE.BufferGeometry();
    var pos    = new Float32Array(count * 3);
    var seeds  = new Float32Array(count);
    var thresh = new Float32Array(count);
    var W2 = 22, H2 = 7, D2 = 9;

    for (var i = 0; i < count; i++) {
      var rx = Math.random();
      var bx = rx * rx * 0.3 + rx * 0.7; // bias toward right side
      pos[i * 3]     = (bx * 2 - 1) * W2;
      pos[i * 3 + 1] = (Math.random() * 2 - 1) * H2;
      pos[i * 3 + 2] = (Math.random() * 2 - 1) * D2;
      seeds[i]  = Math.random();
      thresh[i] = Math.random();
    }

    geo.setAttribute('position',   new THREE.BufferAttribute(pos,    3));
    geo.setAttribute('aSeed',      new THREE.BufferAttribute(seeds,  1));
    geo.setAttribute('aThreshold', new THREE.BufferAttribute(thresh, 1));
    return geo;
  }

  function buildStarGeometry(count) {
    var geo    = new THREE.BufferGeometry();
    var pos    = new Float32Array(count * 3);
    var seeds  = new Float32Array(count);
    var thresh = new Float32Array(count);
    for (var i = 0; i < count; i++) {
      pos[i * 3]     = (Math.random() * 2 - 1) * 40;
      pos[i * 3 + 1] = (Math.random() * 2 - 1) * 20;
      pos[i * 3 + 2] = (Math.random() * 2 - 1) * 5 - 12;
      seeds[i]  = Math.random();
      thresh[i] = 0;
    }
    geo.setAttribute('position',   new THREE.BufferAttribute(pos,    3));
    geo.setAttribute('aSeed',      new THREE.BufferAttribute(seeds,  1));
    geo.setAttribute('aThreshold', new THREE.BufferAttribute(thresh, 1));
    return geo;
  }

  function init() {
    canvas = document.createElement('canvas');
    canvas.id = 'aqi-dust-canvas';

    var section = document.getElementById('section-home');
    if (!section) return;
    section.insertBefore(canvas, section.firstChild);

    var mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    state.reducedMotion = mq.matches;

    renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: false });
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(dpr);
    renderer.setClearColor(0x000000, 0);

    scene  = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(55, 1, 0.1, 200);
    camera.position.set(0, 0, 18);

    updateTargets(state.aqiCurrent);
    state.densityCur = state.densityTgt;
    state.driftCur   = state.driftTgt;
    state.sizeCur    = state.sizeTgt;
    state.alphaCur   = state.alphaTgt;
    state.tintCur    = { r: state.tintTgt.r, g: state.tintTgt.g, b: state.tintTgt.b };

    material = new THREE.ShaderMaterial({
      vertexShader:   VERT_SHADER,
      fragmentShader: FRAG_SHADER,
      uniforms: {
        uTime:       { value: 0 },
        uDensity:    { value: state.densityCur },
        uDriftSpeed: { value: state.driftCur   },
        uPointSize:  { value: state.sizeCur    },
        uBaseAlpha:  { value: state.alphaCur   },
        uTint:       { value: new THREE.Color(state.tintCur.r, state.tintCur.g, state.tintCur.b) },
        uPixelRatio: { value: dpr },
      },
      transparent: true,
      depthWrite:  false,
      blending:    THREE.AdditiveBlending,
    });

    starMaterial = new THREE.ShaderMaterial({
      vertexShader:   VERT_SHADER,
      fragmentShader: FRAG_SHADER,
      uniforms: {
        uTime:       { value: 0 },
        uDensity:    { value: 1.0 },
        uDriftSpeed: { value: 0.04 },
        uPointSize:  { value: 0.8 },
        uBaseAlpha:  { value: 0.06 },
        uTint:       { value: new THREE.Color(0.85, 0.90, 1.0) },
        uPixelRatio: { value: dpr },
      },
      transparent: true,
      depthWrite:  false,
      blending:    THREE.AdditiveBlending,
    });

    var count   = particleCount();
    var geo     = buildGeometry(count);
    var starGeo = buildStarGeometry(Math.floor(count * 0.18));

    points     = new THREE.Points(geo,     material);
    starPoints = new THREE.Points(starGeo, starMaterial);
    scene.add(starPoints);
    scene.add(points);

    resize();

    if (!state.reducedMotion) {
      window.addEventListener('pointermove', onPointerMove, { passive: true });
    }
    window.addEventListener('resize', onResize, { passive: true });

    setupVisibilityObservers(section);
  }

  function resize() {
    var section = document.getElementById('section-home');
    if (!section || !renderer) return;
    W = section.offsetWidth  || window.innerWidth;
    H = section.offsetHeight || window.innerHeight;
    renderer.setSize(W, H, false);
    camera.aspect = W / H;
    camera.updateProjectionMatrix();
  }

  function onResize() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(resize, 150);
  }

  function onPointerMove(e) {
    pointer.tx = ((e.clientX / window.innerWidth)  - 0.5) * 2.4;
    pointer.ty = ((e.clientY / window.innerHeight) - 0.5) * -1.4;
  }

  function updateTargets(aqi) {
    var v = Math.max(0, Math.min(500, aqi));
    state.densityTgt = aqiToDensity(v);
    state.driftTgt   = aqiToDrift(v);
    state.sizeTgt    = aqiToSize(v);
    state.alphaTgt   = aqiToAlpha(v);
    state.tintTgt    = aqiToColor(v);
  }

  function renderFrame(now) {
    if (!renderer) return;
    if (clockStart === null) clockStart = now;
    var t  = (now - clockStart) * 0.001;
    var dt = Math.min((now - lastTime) * 0.001, 0.05);
    lastTime = now;

    // ~1 second lerp time constant
    var k = 1 - Math.exp(-dt * 3.0);
    state.densityCur = lerp(state.densityCur, state.densityTgt, k);
    state.driftCur   = lerp(state.driftCur,   state.driftTgt,   k);
    state.sizeCur    = lerp(state.sizeCur,     state.sizeTgt,    k);
    state.alphaCur   = lerp(state.alphaCur,    state.alphaTgt,   k);
    state.tintCur    = lerpCol(state.tintCur,  state.tintTgt,    k);

    material.uniforms.uTime.value       = t;
    material.uniforms.uDensity.value    = state.densityCur;
    material.uniforms.uDriftSpeed.value = state.driftCur;
    material.uniforms.uPointSize.value  = state.sizeCur;
    material.uniforms.uBaseAlpha.value  = state.alphaCur;
    material.uniforms.uTint.value.setRGB(state.tintCur.r, state.tintCur.g, state.tintCur.b);
    starMaterial.uniforms.uTime.value = t;

    if (!state.reducedMotion) {
      pointer.x += (pointer.tx - pointer.x) * 0.04;
      pointer.y += (pointer.ty - pointer.y) * 0.04;
      camera.position.x = pointer.x * 0.9;
      camera.position.y = pointer.y * 0.5;
    }

    renderer.render(scene, camera);

    if (state.running && !state.reducedMotion) {
      state.rafId = requestAnimationFrame(renderFrame);
    }
  }

  function renderStatic() {
    if (!renderer) return;
    material.uniforms.uTime.value       = 0;
    material.uniforms.uDensity.value    = state.densityCur;
    material.uniforms.uDriftSpeed.value = state.driftCur;
    material.uniforms.uPointSize.value  = state.sizeCur;
    material.uniforms.uBaseAlpha.value  = state.alphaCur;
    material.uniforms.uTint.value.setRGB(state.tintCur.r, state.tintCur.g, state.tintCur.b);
    starMaterial.uniforms.uTime.value = 0;
    renderer.render(scene, camera);
  }

  function startLoop() {
    if (!renderer) return;
    if (state.running) return;
    state.running = true;
    if (state.reducedMotion) {
      renderStatic();
      return;
    }
    lastTime = performance.now();
    state.rafId = requestAnimationFrame(renderFrame);
    canvas.style.display = '';
  }

  function stopLoop() {
    state.running = false;
    if (state.rafId !== null) {
      cancelAnimationFrame(state.rafId);
      state.rafId = null;
    }
    if (canvas) canvas.style.display = 'none';
  }

  function setupVisibilityObservers(section) {
    var mutObs = new MutationObserver(function () {
      var isActive  = section.classList.contains('active');
      var isVisible = !document.hidden;
      if (isActive && isVisible) {
        startLoop();
      } else {
        stopLoop();
      }
    });
    mutObs.observe(section, { attributes: true, attributeFilter: ['class'] });

    document.addEventListener('visibilitychange', function () {
      var isActive = section.classList.contains('active');
      if (!document.hidden && isActive) {
        startLoop();
      } else {
        stopLoop();
      }
    });

    if (section.classList.contains('active')) {
      startLoop();
    }
  }

  // Public API
  window.AQIDust = {
    /**
     * setAQI(value)
     * Smoothly transition all visual properties to match the new AQI.
     * Typing AQIDust.setAQI(450) in the browser console will visibly change the effect.
     */
    setAQI: function (value) {
      var v = parseFloat(value);
      if (isNaN(v)) return;
      state.aqiTarget  = v;
      state.aqiCurrent = v;
      updateTargets(v);
      if (state.reducedMotion && renderer) renderStatic();
    },

    setCity: function (name) {
      // City name is informational only for this effect; no visual change needed here
    },

    pause:  function () { stopLoop();  },
    resume: function () { startLoop(); },
  };

  // Bootstrap
  function bootstrap() {
    try {
      init();
    } catch (err) {
      console.warn('[AQIDust] Initialization failed - dust effect disabled.', err);
      if (canvas) canvas.style.display = 'none';
      window.AQIDust = { setAQI: function(){}, setCity: function(){}, pause: function(){}, resume: function(){} };
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
  } else {
    bootstrap();
  }

}());
