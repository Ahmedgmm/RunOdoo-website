// Sign-in / sign-up / reset pages (views/auth_templates.xml): the Runodoo glass stack (3 layers = Code → Build →
// Run), same look as the homepage hero. Idle spin + mouse parallax; the layers light up in turn (synced with the
// labels); typing in the form opens the stack, submitting snaps it shut. Falls back to the logo image without WebGL.
// Ported from the panel's sign-up page (odoo-host branch claude/open-signup).
import * as THREE from '/website_runodoo/static/lib/three/three.module.min.js';

const canvas = document.getElementById('su-gl');
const stage = canvas && canvas.parentElement;
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const labels = [...document.querySelectorAll('.su-layers li')];

const C = ['#7EF0C8', '#4FC8E8', '#8FA4F0', '#B28CF0'].map((c) => new THREE.Color(c));
function gradAt(t) {
    const c = new THREE.Color();
    if (t < 0.38) return c.lerpColors(C[0], C[1], t / 0.38);
    if (t < 0.68) return c.lerpColors(C[1], C[2], (t - 0.38) / 0.3);
    return c.lerpColors(C[2], C[3], (t - 0.68) / 0.32);
}
function paint(geo, half, boost = 1) {
    const pos = geo.attributes.position, col = new Float32Array(pos.count * 3);
    for (let i = 0; i < pos.count; i++) {
        const t = Math.min(1, Math.max(0, (pos.getX(i) - pos.getZ(i) + 2 * half) / (4 * half)));
        const c = gradAt(t).multiplyScalar(boost * (0.9 + 0.1 * Math.sign(pos.getY(i))));
        col.set([c.r, c.g, c.b], i * 3);
    }
    geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
}
function slab(size, depth, r) {
    const h = size / 2, s = new THREE.Shape();
    s.moveTo(-h + r, -h);
    s.lineTo(h - r, -h); s.quadraticCurveTo(h, -h, h, -h + r);
    s.lineTo(h, h - r); s.quadraticCurveTo(h, h, h - r, h);
    s.lineTo(-h + r, h); s.quadraticCurveTo(-h, h, -h, h - r);
    s.lineTo(-h, -h + r); s.quadraticCurveTo(-h, -h, -h + r, -h);
    const g = new THREE.ExtrudeGeometry(s, { depth, bevelEnabled: true, bevelThickness: 0.05, bevelSize: 0.05,
        bevelSegments: 3, curveSegments: 6 });
    g.rotateX(-Math.PI / 2);
    g.center();
    return g;
}
function studio(renderer) {
    const env = new THREE.Scene();
    env.background = new THREE.Color('#0d1016');
    const panel = (w, h, color, k, pos, rot) => {
        const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({
            color: new THREE.Color(color).multiplyScalar(k), side: THREE.DoubleSide }));
        m.position.set(...pos); m.rotation.set(...rot); env.add(m);
    };
    panel(6, 2, '#ffffff', 3.2, [0, 6, 0], [Math.PI / 2, 0, 0]);
    panel(4, 6, '#7EF0C8', 1.8, [-7, 1, 2], [0, Math.PI / 2, 0]);
    panel(4, 6, '#B28CF0', 2.0, [7, 1, -2], [0, -Math.PI / 2, 0]);
    panel(8, 3, '#4FC8E8', 1.2, [0, -1, -8], [0, 0, 0]);
    panel(3, 3, '#ffffff', 1.4, [3, 3, 7], [0, Math.PI, 0]);
    const pm = new THREE.PMREMGenerator(renderer);
    const tex = pm.fromScene(env, 0.035).texture;
    pm.dispose();
    return tex;
}

function start() {
    let renderer;
    try {
        renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    } catch (e) {
        return;  // the fallback logo image stays
    }
    document.body.classList.add('su-gl-on');
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;

    const scene = new THREE.Scene();
    scene.environment = studio(renderer);
    const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100);
    camera.position.set(0, 0, 13.5);
    const tilt = new THREE.Group(), spin = new THREE.Group();
    tilt.add(spin); scene.add(tilt);

    const SIZE = 3.1, DEPTH = 0.5, HALF = SIZE / 2, layers = [];
    for (let i = 0; i < 3; i++) {
        const g = slab(SIZE, DEPTH, 0.28);
        paint(g, HALF);
        const mesh = new THREE.Mesh(g, new THREE.MeshPhysicalMaterial({
            vertexColors: true, roughness: 0.12, transmission: 0.92, thickness: 1.1, ior: 1.42, iridescence: 0.7,
            iridescenceIOR: 1.3, clearcoat: 1, clearcoatRoughness: 0.08, envMapIntensity: 1.5,
            emissive: new THREE.Color('#4FC8E8'), emissiveIntensity: 0, transparent: true, opacity: 0.95 }));
        const eg = new THREE.EdgesGeometry(g, 25);
        paint(eg, HALF, 1.6);
        const line = (op) => new THREE.LineSegments(eg, new THREE.LineBasicMaterial({ vertexColors: true,
            transparent: true, opacity: op, toneMapped: false, blending: THREE.AdditiveBlending, depthWrite: false }));
        const edges = line(0.95), halo = line(0.35);
        halo.scale.setScalar(1.012);
        const group = new THREE.Group();
        group.add(mesh, edges, halo);
        spin.add(group);
        layers.push({ group, mesh, edges, halo, hl: 0 });
    }
    const coreGeo = new THREE.BoxGeometry(1.25, 0.42, 1.25);
    paint(coreGeo, 0.62, 1.4);
    const core = new THREE.Mesh(coreGeo, new THREE.MeshBasicMaterial({ vertexColors: true, toneMapped: false }));
    layers[1].group.add(core);

    // gap: 0 = closed box, 1 = wide open. `target` eases toward typing / sent states.
    const state = { gap: 0.35, target: 0.35, glow: 0, glowTarget: 0 };
    const sent = !!document.querySelector('.su-form-wrap .alert-success');
    if (sent) { state.gap = 0.9; state.target = 0; state.glowTarget = 1; }
    const form = document.querySelector('.su-form-wrap form');
    const inputs = form ? [...form.querySelectorAll('input:not([type=hidden])')] : [];
    const filled = () => inputs.some((i) => i.value);
    inputs.forEach((i) => {
        const open = () => { state.target = filled() ? 0.85 : 0.6; };
        i.addEventListener('focus', open);
        i.addEventListener('input', open);
        i.addEventListener('blur', () => { if (!filled()) state.target = 0.35; });
    });
    if (form) form.addEventListener('submit', () => { state.target = 0; state.glowTarget = 1; });

    let W = 1, H = 1;
    function resize() {
        const r = stage.getBoundingClientRect();
        W = Math.max(1, r.width); H = Math.max(1, r.height);
        renderer.setSize(W, H, false);
        camera.aspect = W / H;
        camera.updateProjectionMatrix();
    }
    resize();
    new ResizeObserver(resize).observe(stage);

    const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
    window.addEventListener('pointermove', (e) => {
        mouse.tx = (e.clientX / window.innerWidth) * 2 - 1;
        mouse.ty = (e.clientY / window.innerHeight) * 2 - 1;
    }, { passive: true });

    const clock = new THREE.Clock();
    let idle = 0, active = null;
    function frame() {
        const dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime;
        idle += dt * (REDUCED ? 0 : 0.22);
        mouse.x += (mouse.tx - mouse.x) * 0.05;
        mouse.y += (mouse.ty - mouse.y) * 0.05;
        state.gap += (state.target - state.gap) * Math.min(1, dt * 3);
        state.glow += (state.glowTarget - state.glow) * Math.min(1, dt * 2);

        // fit the stack into the stage (smaller on narrow stages)
        const s = Math.min(1, W / 520) * (H < 340 ? 0.75 : 1);
        tilt.scale.setScalar(s);
        tilt.position.set(W > 560 ? -0.9 : -0.6, Math.sin(t * 0.9) * 0.12, 0);
        tilt.rotation.x = 0.6 + mouse.y * 0.12;
        tilt.rotation.z = -mouse.x * 0.06;
        spin.rotation.y = Math.PI / 4 + idle + mouse.x * 0.25;

        // Code → Build → Run: one layer lit every 1.6 s, top to bottom (not while closed after sending)
        const cycle = REDUCED || state.glowTarget ? -1 : 2 - (Math.floor(t / 1.6) % 3);
        const step = DEPTH + 0.14 + state.gap * 0.9;
        layers.forEach((L, i) => {
            const want = state.glow > 0.05 ? state.glow : (i === cycle ? 1 : 0);
            L.hl += (want - L.hl) * Math.min(1, dt * 4);
            const wobble = REDUCED ? 0 : Math.sin(t * 1.3 + i * 1.7) * 0.04 * (0.3 + state.gap);
            L.group.position.y = (i - 1) * step + wobble;
            L.group.rotation.y = (i - 1) * state.gap * 0.12;
            L.mesh.material.emissiveIntensity = 0.06 + L.hl * 0.55;
            L.edges.material.opacity = 0.75 + L.hl * 0.25;
            L.halo.material.opacity = 0.25 + L.hl * 0.5;
        });
        core.scale.setScalar(0.85 + 0.15 * (1 - state.gap) + Math.sin(t * 2) * 0.03);
        if (cycle !== active) {
            active = cycle;
            labels.forEach((li) => li.classList.toggle('on', Number(li.dataset.i) === cycle || state.glowTarget > 0));
        }
        renderer.render(scene, camera);
    }
    (function loop() {
        requestAnimationFrame(loop);
        if (!document.hidden) frame();
    })();
    window.__su = { state, render: frame };  // debug hook: render one frame on demand
}

if (canvas) start();
