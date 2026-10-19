/* AIRWISE: lightweight local 3D Earth hero */
(() => {
  "use strict";

  function initEarthHero() {
    const host = document.querySelector(".earth-hero-visual");
    const canvas = document.getElementById("earth-canvas");

    if (!host || !canvas || !window.THREE) return;

    let renderer;

    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        alpha: true,
        antialias: true,
        powerPreference: "low-power"
      });
    } catch (_) {
      host.classList.add("earth-renderer-fallback");
      return;
    }

    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.25));
    renderer.setClearColor(0x000000, 0);
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.95;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
    camera.position.set(0, 0, 3.65);

    scene.add(new THREE.AmbientLight(0x9bb9c7, 0.65));

    const keyLight = new THREE.DirectionalLight(0xf3f8ff, 1.15);
    keyLight.position.set(-3, 2, 4);
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0x3dd5e6, 0.95);
    rimLight.position.set(3, 0.6, -2);
    scene.add(rimLight);

    const warmLight = new THREE.DirectionalLight(0xffd6ac, 0.20);
    warmLight.position.set(2, -1, 2);
    scene.add(warmLight);

    const globe = new THREE.Group();
    globe.rotation.z = -0.13;
    globe.rotation.x = 0.06;
    scene.add(globe);

    const loader = new THREE.TextureLoader();
    const maxAnisotropy = Math.min(
      renderer.capabilities.getMaxAnisotropy(), 8
    );

    function loadTexture(url, isColour) {
      return new Promise((resolve, reject) => {
        loader.load(
          url,
          texture => {
            texture.encoding = isColour
              ? THREE.sRGBEncoding
              : THREE.LinearEncoding;
            texture.anisotropy = maxAnisotropy;
            resolve(texture);
          },
          undefined,
          reject
        );
      });
    }

    const base = "/static/earth/";

    Promise.all([
      loadTexture(base + "earth-surface.jpg", true),
      loadTexture(base + "earth-clouds.png", true),
      loadTexture(base + "earth-normal.jpg", false),
      loadTexture(base + "earth-specular.jpg", false)
    ]).then(([surfaceMap, cloudMap, normalMap, specularMap]) => {
      const earth = new THREE.Mesh(
        new THREE.SphereGeometry(1.08, 64, 48),
        new THREE.MeshPhongMaterial({
          map: surfaceMap,
          normalMap,
          normalScale: new THREE.Vector2(0.28, 0.28),
          specularMap,
          specular: new THREE.Color(0x193d4a),
          shininess: 8
        })
      );

      // The source map is centred near the Asia-Pacific region.
      earth.rotation.y = -4.2;
      globe.add(earth);

      const clouds = new THREE.Mesh(
        new THREE.SphereGeometry(1.095, 64, 48),
        new THREE.MeshPhongMaterial({
          map: cloudMap,
          transparent: true,
          opacity: 0.17,
          depthWrite: false
        })
      );
      clouds.rotation.y = earth.rotation.y + 0.02;
      globe.add(clouds);

      const atmosphere = new THREE.Mesh(
        new THREE.SphereGeometry(1.135, 64, 48),
        new THREE.ShaderMaterial({
          uniforms: {},
          vertexShader: `
            varying vec3 vNormal;
            varying vec3 vViewPosition;
            void main() {
              vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
              vNormal = normalize(normalMatrix * normal);
              vViewPosition = -viewPosition.xyz;
              gl_Position = projectionMatrix * viewPosition;
            }
          `,
          fragmentShader: `
            varying vec3 vNormal;
            varying vec3 vViewPosition;
            void main() {
              float facing = abs(dot(
                normalize(vNormal),
                normalize(vViewPosition)
              ));
              float rim = pow(1.0 - facing, 2.4);
              gl_FragColor = vec4(0.12, 0.58, 0.78, 0.45) * rim;
            }
          `,
          side: THREE.BackSide,
          blending: THREE.AdditiveBlending,
          transparent: true,
          depthWrite: false
        })
      );
      globe.add(atmosphere);

      host.classList.add("earth-renderer-ready");

      function resize() {
        const width = Math.max(1, host.clientWidth);
        const height = Math.max(1, host.clientHeight);
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
      }

      resize();
      window.addEventListener("resize", resize, { passive: true });

      if ("ResizeObserver" in window) {
        new ResizeObserver(resize).observe(host);
      }

      const rotationSpeed = reducedMotion ? 0 : 0.00075;

      function renderFrame() {
        if (!document.hidden) {
          earth.rotation.y += rotationSpeed;
          clouds.rotation.y += rotationSpeed * 1.18;
          renderer.render(scene, camera);
        }
        window.requestAnimationFrame(renderFrame);
      }

      renderFrame();
    }).catch(() => {
      // The CSS starfield and atmospheric background remain as a fallback.
      host.classList.add("earth-renderer-fallback");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initEarthHero, { once: true });
  } else {
    initEarthHero();
  }
})();
