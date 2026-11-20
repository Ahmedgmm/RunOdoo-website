// Runodoo homepage (generated from Data/mockups/home-calendly.js by port_to_odoo.py): light-background glass stack (3 layers = Your Odoo → Kept safe → Always on),
// accordion + tab auto-rotation, reveals. Stack based on initStack() in home.js / signup-stack.js, re-tuned for
// a white page: no additive glow, a bright studio environment, normal-blended darker edges, a soft floor shadow.
import * as THREE from 'three';

if (!document.querySelector('.ro-home')) throw new Error('not the Runodoo home');

const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
document.documentElement.classList.add('ro-js');

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
        const c = gradAt(t).multiplyScalar(boost * (0.92 + 0.08 * Math.sign(pos.getY(i))));
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
    const g = new THREE.ExtrudeGeometry(s, { depth, bevelEnabled: true, bevelThickness: 0.06, bevelSize: 0.06,
        bevelSegments: 4, curveSegments: 8 });
    g.rotateX(-Math.PI / 2);
    g.center();
    return g;
}
// Bright "daylight" studio: pale sky, white softboxes, tinted side cards → crisp highlights on a light page.
function studio(renderer) {
    const env = new THREE.Scene();
    env.background = new THREE.Color('#dfe7f2');
    const panel = (w, h, color, k, pos, rot) => {
        const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({
            color: new THREE.Color(color).multiplyScalar(k), side: THREE.DoubleSide }));
        m.position.set(...pos); m.rotation.set(...rot); env.add(m);
    };
    panel(8, 3, '#ffffff', 2.6, [0, 6, 0], [Math.PI / 2, 0, 0]);
    panel(4, 6, '#ffffff', 1.6, [-7, 1, 2], [0, Math.PI / 2, 0]);
    panel(4, 6, '#e55cff', 0.9, [7, 1, -2], [0, -Math.PI / 2, 0]);
    panel(8, 3, '#0099ff', 0.8, [0, -1, -8], [0, 0, 0]);
    panel(3, 3, '#ffffff', 1.8, [3, 3, 7], [0, Math.PI, 0]);
    panel(20, 20, '#9fb3c8', 0.6, [0, -6, 0], [Math.PI / 2, 0, 0]);
    const pm = new THREE.PMREMGenerator(renderer);
    const tex = pm.fromScene(env, 0.04).texture;
    pm.dispose();
    return tex;
}

const stacks = [];
function makeStack(canvas, opts) {
    const stage = canvas.parentElement;
    let renderer;
    try {
        renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    } catch (e) {
        return null;  // fallback logo image stays
    }
    stage.classList.add('ro-gl-on');
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, window.innerWidth < 700 ? 1.5 : 2));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.0;

    const scene = new THREE.Scene();
    scene.environment = studio(renderer);
    scene.add(new THREE.HemisphereLight('#ffffff', '#b9c8da', 0.9));
    const key = new THREE.DirectionalLight('#ffffff', 1.4);
    key.position.set(3, 6, 5);
    scene.add(key);
    const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100);
    camera.position.set(0, 0, 13.5);
    const tilt = new THREE.Group(), spin = new THREE.Group();
    tilt.add(spin); scene.add(tilt);

    const SIZE = 3.1, DEPTH = 0.5, HALF = SIZE / 2, layers = [];
    for (let i = 0; i < 3; i++) {
        const g = slab(SIZE, DEPTH, 0.3);
        paint(g, HALF);
        // Frosted coloured glass: no transmission (it samples the transparent canvas → dark on a white page).
        const mesh = new THREE.Mesh(g, new THREE.MeshPhysicalMaterial({
            vertexColors: true, roughness: 0.22, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.06,
            iridescence: 0.35, iridescenceIOR: 1.3,
            envMapIntensity: 0.9, emissive: new THREE.Color('#ffffff'), emissiveIntensity: 0,
            transparent: true, opacity: 0.94, depthWrite: true }));
        const eg = new THREE.EdgesGeometry(g, 25);
        paint(eg, HALF, opts.dark ? 1.5 : 0.62);  // darker edges on white, bright ones on navy
        const edges = new THREE.LineSegments(eg, new THREE.LineBasicMaterial({ vertexColors: true,
            transparent: true, opacity: 0.9, toneMapped: false, depthWrite: false,
            blending: opts.dark ? THREE.AdditiveBlending : THREE.NormalBlending }));
        const group = new THREE.Group();
        group.add(mesh, edges);
        spin.add(group);
        layers.push({ group, mesh, edges, hl: 0 });
    }
    const coreGeo = new THREE.BoxGeometry(1.25, 0.42, 1.25);
    paint(coreGeo, 0.62, 1.05);
    const core = new THREE.Mesh(coreGeo, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.35,
        emissive: new THREE.Color('#4FC8E8'), emissiveIntensity: 0.25 }));
    layers[1].group.add(core);

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

    // scroll-driven inputs: spin (extra turn), lift (world units), tiltX (extra pitch) — eased in frame()
    const st = { gap: opts.gap, target: opts.gap, idle: 0, visible: true, cycle: -1, spin: 0, lift: 0, tiltX: 0, _spin: 0, _lift: 0, _tiltX: 0 };
    new IntersectionObserver(([e]) => { st.visible = e.isIntersecting; }).observe(stage);

    function frame(t, dt, mouse) {
        st.idle += dt * (REDUCED ? 0 : 0.2);
        const k = Math.min(1, dt * 4);
        st.gap += (st.target - st.gap) * Math.min(1, dt * 3);
        st._spin += (st.spin - st._spin) * k; st._lift += (st.lift - st._lift) * k; st._tiltX += (st.tiltX - st._tiltX) * k;
        const s = Math.min(1, W / 480) * Math.min(1, H / 400) * opts.scale;
        tilt.scale.setScalar(s);
        tilt.position.set(opts.x || 0, (opts.y || 0) + st._lift + Math.sin(t * 0.9) * 0.12, 0);
        tilt.rotation.x = 0.6 + st._tiltX + mouse.y * 0.18;
        tilt.rotation.z = -mouse.x * 0.08;
        spin.rotation.y = Math.PI / 4 + st.idle + st._spin + mouse.x * 0.35;
        const step = DEPTH + 0.14 + st.gap * 0.9;
        layers.forEach((L, i) => {
            const want = i === st.cycle ? 1 : 0;
            L.hl += (want - L.hl) * Math.min(1, dt * 4);
            const wobble = REDUCED ? 0 : Math.sin(t * 1.3 + i * 1.7) * 0.04 * (0.3 + st.gap);
            L.group.position.y = (i - 1) * step + wobble + L.hl * 0.18;
            L.group.position.x = L.hl * 0.12;
            L.group.rotation.y = (i - 1) * st.gap * 0.12;
            L.mesh.material.emissiveIntensity = L.hl * 0.22;
            L.mesh.material.opacity = 0.92 + L.hl * 0.08;
        });
        core.scale.setScalar(0.85 + 0.15 * (1 - st.gap) + Math.sin(t * 2) * 0.03);
        renderer.render(scene, camera);
    }
    const S = { st, frame };
    stacks.push(S);
    return S;
}

// ================= wiring + motion (GSAP 3.15: ScrollTrigger, SplitText) =================
// Selectors go through q()/qa() (port_to_odoo.py prefixes them); JS-only classes are written with ro- already.
const gsap = window.gsap, ScrollTrigger = window.ScrollTrigger, SplitText = window.SplitText;
const MOTION = !REDUCED && !!(gsap && ScrollTrigger && SplitText);
if (MOTION) gsap.registerPlugin(ScrollTrigger, SplitText);
const FINE = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
const DESK = window.innerWidth > 900;
const q = (s, r = document) => r.querySelector(s);
const qa = (s, r = document) => [...r.querySelectorAll(s)];

// ---------- stacks ----------
const hero = document.getElementById('ro-gl-hero') && makeStack(document.getElementById('ro-gl-hero'), { gap: 0.4, scale: 0.8, x: 0.5, y: 0.35 });
const fin = document.getElementById('ro-gl-final') && makeStack(document.getElementById('ro-gl-final'), { gap: 0.6, scale: 1.7, dark: true });
const how = document.getElementById('ro-gl-how') && makeStack(document.getElementById('ro-gl-how'), { gap: 0.3, scale: 1.75 });
const envRows = qa('.ro-env-rows li');

const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
window.addEventListener('pointermove', (e) => {
    mouse.tx = (e.clientX / window.innerWidth) * 2 - 1;
    mouse.ty = (e.clientY / window.innerHeight) * 2 - 1;
}, { passive: true });

const clock = new THREE.Clock();
let lastCycle = -2;
function render() {
    const dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime;
    mouse.x += (mouse.tx - mouse.x) * 0.06;
    mouse.y += (mouse.ty - mouse.y) * 0.06;
    // Hero: one layer lit every 1.8 s, synced with the env card rows (Running / Backed up / Online).
    const cycle = REDUCED ? -1 : Math.floor(t / 1.8) % 3;
    if (hero) hero.st.cycle = 2 - cycle;
    if (fin) fin.st.cycle = -1;
    if (cycle !== lastCycle) {
        lastCycle = cycle;
        envRows.forEach((li) => li.classList.toggle('ro-on', Number(li.dataset.i) === cycle));
    }
    stacks.forEach((S) => { if (S.st.visible) S.frame(t, dt, mouse); });
}
(function loop() {
    requestAnimationFrame(loop);
    if (!document.hidden) render();
})();

// ---------- nav: shadow, progress bar, hide on scroll down ----------
const nav = q('.ro-nav');
const bar = q('.ro-progress');
let lastY = window.scrollY;
function onScroll() {
    const y = window.scrollY, h = document.documentElement.scrollHeight - window.innerHeight;
    nav.classList.toggle('ro-is-scrolled', y > 8);
    if (bar) bar.style.setProperty('--p', h > 0 ? (y / h).toFixed(4) : 0);
    if (MOTION) nav.classList.toggle('ro-hide', y > lastY + 2 && y > 700);
    else if (y < lastY) nav.classList.remove('ro-hide');
    if (y < lastY - 2) nav.classList.remove('ro-hide');
    lastY = y;
    if (!MOTION) {  // simple fallback: hero box opens a little, finale closes
        if (hero) hero.st.target = 0.4 + Math.min(1, y / 500) * 0.5;
        const fs = q('.ro-final-stage');
        if (fin && fs) {
            const r = fs.getBoundingClientRect();
            fin.st.target = 0.9 * (1 - Math.min(1, Math.max(0, (window.innerHeight - r.top) / (window.innerHeight * 0.8))));
        }
    }
}
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

// ---------- pane switching (How accordion + Developer tabs) ----------
function swapIn(pane) {
    if (!MOTION || !pane) return;
    gsap.fromTo(pane.children, { opacity: 0, y: 22, filter: 'blur(8px)' },
        { opacity: 1, y: 0, filter: 'blur(0px)', duration: 0.7, stagger: 0.07, ease: 'power3.out', clearProps: 'filter,transform,opacity' });
}
function rotator(root, items, panes, ms, onShow) {
    if (!root) return null;
    let i = 0, timer = null, live = false;
    const dur = (n) => (typeof ms === 'function' ? ms(n) : ms);
    const show = (n, quiet) => {
        i = n;
        items.forEach((b, k) => b.classList.toggle('ro-is-on', k === n));
        panes.forEach((p, k) => p.classList.toggle('ro-is-on', k === n));
        if (!quiet) swapIn(panes[n]);
        if (onShow) onShow(n, panes[n]);
    };
    const tick = () => { clearTimeout(timer); timer = setTimeout(() => { show((i + 1) % items.length); tick(); }, dur(i)); };
    const R = {
        show, get i() { return i; },
        auto(on) { live = on; clearTimeout(timer); if (on && !root.classList.contains('ro-paused')) tick(); },
    };
    items.forEach((b, k) => b.addEventListener('click', () => {
        if (R.onClick) return R.onClick(k);
        clearTimeout(timer); root.classList.add('ro-paused'); show(k);
    }));
    if (!REDUCED) {
        new IntersectionObserver(([e]) => {
            if (R.manual) return;
            clearTimeout(timer);
            if (e.isIntersecting && !root.classList.contains('ro-paused')) { show(i, true); tick(); }
        }, { threshold: 0.4 }).observe(root);
    }
    return R;
}

// How: accordion ↔ product card ↔ stack layer (Your Odoo = top layer, Always on = bottom)
const howRot = rotator(q('[data-acc]'), qa('.ro-acc-item'), qa('.ro-how-card .ro-pane'), 6000, (n) => {
    if (how) how.st.cycle = 2 - n;
});

// Developers: tabs; each pane plays its own little story when shown
let devToken = 0;
const devRot = rotator(q('[data-tabs]'), qa('[data-tabs] button'), qa('.ro-dpane'), (n) => [7000, 10000, 6500, 6500][n], (n, pane) => {
    const token = ++devToken;
    if (n === 0) branchList(pane, token);
    if (n === 1) buildLog(pane, token);
    if (n === 2 && MOTION) gsap.from(qa('.ro-sbx > div', pane), { x: -24, opacity: 0, duration: 0.5, stagger: 0.09, ease: 'power2.out', clearProps: 'all' });
    if (n === 3 && MOTION) gsap.from(qa('.ro-sv', pane), { scale: 0.85, opacity: 0, duration: 0.6, stagger: 0.25, ease: 'back.out(1.6)', clearProps: 'all' });
});
function later(ms, token, fn) { setTimeout(() => { if (token === devToken) fn(); }, ms); }
function branchList(pane, token) {
    const rows = qa('[data-branches] li', pane);
    const em = rows[2] && q('em', rows[2]);
    if (em) { em.textContent = 'building…'; em.classList.add('ro-bld'); }
    if (MOTION) gsap.fromTo(rows, { x: -20, opacity: 0 }, { x: 0, opacity: 1, duration: 0.5, stagger: 0.35, delay: 0.6, ease: 'power2.out', clearProps: 'all' });
    later(3200, token, () => { if (em) { em.textContent = 'development · running'; em.classList.remove('ro-bld'); } });
}
const LOG = [
    ['$ ', 'git clone --branch feature/invoices', 'c'], ['  ✓ ', '41a9c2e · 12 files changed', 'g'],
    ['$ ', 'pip install -r requirements.txt', 'c'], ['  ✓ ', '3 packages installed', 'g'],
    ['$ ', 'docker build -t shop:feature-invoices .', 'c'], ['  ✓ ', 'image built in 38 s', 'g'],
    ['$ ', 'odoo -u sale_custom,account_custom', 'c'], ['  ✓ ', '2 modules upgraded', 'g'],
    ['→ ', 'live at feature-invoices.shop.runodoo.online', 'd'],
];
function buildLog(pane, token) {
    const pre = q('[data-log]', pane), state = q('[data-build-state]', pane), barEl = q('[data-build-bar]', pane);
    if (!pre) return;
    pre.innerHTML = ''; state.textContent = 'running'; state.classList.remove('ro-ok'); barEl.style.width = '0%';
    if (!MOTION) {  // static, finished log
        pre.innerHTML = LOG.map(([p, t, c]) => `<span class="${c}">${p}</span>${t}`).join('\n');
        state.textContent = 'live'; state.classList.add('ro-ok'); barEl.style.width = '100%';
        return;
    }
    const cur = '<span class="ro-cur"></span>';
    let line = 0, html = '';
    const typeLine = () => {
        if (token !== devToken) return;
        if (line >= LOG.length) { pre.innerHTML = html; state.textContent = 'live'; state.classList.add('ro-ok'); return; }
        const [p, text, c] = LOG[line];
        const head = `${html}${line ? '\n' : ''}<span class="${c}">${p}</span>`;
        const typed = c === 'c';
        let k = typed ? 0 : text.length;
        const step = () => {
            if (token !== devToken) return;
            pre.innerHTML = head + text.slice(0, k) + cur;
            if (k < text.length) { k += 2; setTimeout(step, 22); return; }
            html = head + text;
            line += 1;
            barEl.style.width = `${Math.round((line / LOG.length) * 100)}%`;
            setTimeout(typeLine, typed ? 260 : 420);
        };
        step();
    };
    later(350, token, typeLine);
}

// ---------- live env card + rotating chip ----------
(function liveHero() {
    const val = q('[data-live]'), line = q('.ro-spark-line'), fill = q('.ro-spark-fill');
    const pts = Array.from({ length: 24 }, (_, i) => 110 + Math.sin(i / 2) * 20 + Math.random() * 14);
    const draw = () => {
        const max = 200, min = 60, W = 120, H = 32;
        const xy = pts.map((v, i) => [(i / (pts.length - 1)) * W, H - ((v - min) / (max - min)) * H]);
        const d = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
        if (line) line.setAttribute('d', d);
        if (fill) fill.setAttribute('d', `${d} L${W} ${H} L0 ${H} Z`);
        if (val) val.textContent = Math.round(pts[pts.length - 1]);
    };
    draw();
    if (REDUCED) return;
    setInterval(() => {
        if (document.hidden) return;
        const last = pts[pts.length - 1];
        pts.push(Math.max(70, Math.min(190, last + (Math.random() - 0.48) * 26)));
        pts.shift();
        draw();
    }, 1100);

    // status tag: every ~12 s a short "updating…" moment
    const status = q('[data-env-status]'), tag = status && status.parentElement;
    setInterval(() => {
        if (!status || document.hidden) return;
        status.textContent = 'updating…'; tag.classList.add('ro-deploying');
        setTimeout(() => { status.textContent = 'production'; tag.classList.remove('ro-deploying'); }, 2600);
    }, 12000);

    // chip: cycles through what the platform just did
    const chip = q('[data-chip]'), ic = q('[data-chip-ic]');
    const MSG = [['⧉', 'Update tested on a copy', 'Ready to go live'], ['✓', 'Backup done', 'Today · 03:00'],
        ['⎇', 'feature/vat built', 'Live on its own link'], ['✉', 'Invoice delivered', 'INV/2026/0142 · inbox']];
    let m = 0;
    setInterval(() => {
        if (!chip || document.hidden) return;
        m = (m + 1) % MSG.length;
        const swap = () => { ic.textContent = MSG[m][0]; chip.innerHTML = `<b>${MSG[m][1]}</b><small>${MSG[m][2]}</small>`; };
        if (!MOTION) return swap();
        gsap.timeline()
            .to([chip, ic], { rotationX: 90, opacity: 0, duration: 0.3, ease: 'power2.in', stagger: 0.04 })
            .add(swap)
            .fromTo([chip, ic], { rotationX: -90, opacity: 0 }, { rotationX: 0, opacity: 1, duration: 0.45, ease: 'back.out(1.8)', stagger: 0.04 });
    }, 3600);
})();

// ---------- counters ----------
function countUp(el, dur = 1.6) {
    const txt = el.dataset.count != null ? el.dataset.count : el.textContent.trim();
    const m = txt.match(/^(\d+)(.*)$/);
    if (!m || !MOTION) return;
    const to = Number(m[1]), rest = el.dataset.count != null ? '' : m[2];
    const from = el.dataset.from != null ? Number(el.dataset.from) : (to === 0 ? 20 : 0);
    const o = { v: from };
    gsap.to(o, { v: to, duration: dur, ease: 'power2.out', onUpdate: () => { el.textContent = Math.round(o.v) + rest; } });
}

// ---------- stories hook (called by the carousel) ----------
function storyIn(slide) {
    if (!MOTION || !slide) return;
    gsap.fromTo(qa('.ro-st-copy > *', slide), { y: 24, opacity: 0 }, { y: 0, opacity: 1, duration: 0.7, stagger: 0.08, ease: 'power3.out', clearProps: 'all' });
    gsap.fromTo(q('.ro-st-art', slide), { clipPath: 'inset(0 0 0 100% round 20px)' }, { clipPath: 'inset(0 0 0 0% round 20px)', duration: 0.9, ease: 'expo.out', clearProps: 'clipPath' });
    const b = q('.ro-st-stat b', slide);
    if (b) { if (!b.dataset.orig) b.dataset.orig = b.textContent; b.textContent = b.dataset.orig; countUp(b, 1.2); }
}

// ---------- hover tilt + glow (desktop pointers) ----------
if (FINE && !REDUCED) {
    qa('.ro-who-card, .ro-tile, .ro-tb, .ro-stat, .ro-st-card, .ro-devcard, .ro-how-card').forEach((el) => {
        const big = el.offsetWidth > 600;
        const max = big ? 3 : 8;
        el.classList.add('ro-tilt');
        el.addEventListener('pointermove', (e) => {
            const r = el.getBoundingClientRect();
            const px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
            el.style.setProperty('--ry', `${((px - 0.5) * max).toFixed(2)}deg`);
            el.style.setProperty('--rx', `${(-(py - 0.5) * max).toFixed(2)}deg`);
            el.style.setProperty('--gx', `${(px * 100).toFixed(1)}%`);
            el.style.setProperty('--gy', `${(py * 100).toFixed(1)}%`);
            el.classList.add('ro-tilting');
        });
        el.addEventListener('pointerleave', () => {
            el.classList.remove('ro-tilting');
            el.style.setProperty('--rx', '0deg'); el.style.setProperty('--ry', '0deg');
        });
    });
}

// ---------- trusted-by marquee ----------
(function marquee() {
    const ul = q('.ro-trust .ro-logos');
    if (!ul || REDUCED) return;
    const wrap = document.createElement('div');
    wrap.className = 'ro-mq';
    ul.parentNode.insertBefore(wrap, ul);
    wrap.appendChild(ul);
    qa('li', ul).forEach((li) => { const c = li.cloneNode(true); c.setAttribute('aria-hidden', 'true'); ul.appendChild(c); });
    ul.classList.add('ro-marquee');
})();

// ---------- scroll choreography ----------
function motion() {
    // hero intro
    const h1 = q('.ro-hero h1');
    const split = SplitText.create(h1, { type: 'words', mask: 'words', wordsClass: 'ro-w' });
    const heroCopy = q('.ro-hero-copy');
    const tl = gsap.timeline({ defaults: { ease: 'expo.out' } });
    tl.from(q('.ro-badge', heroCopy), { y: 16, opacity: 0, duration: 0.8 })
        .from(split.words, { yPercent: 115, duration: 1.1, stagger: 0.07 }, 0.1)
        .from([q('.ro-lead', heroCopy), ...qa('.ro-hero-btns .ro-btn', heroCopy), q('.ro-fine', heroCopy)], { y: 26, opacity: 0, duration: 0.9, stagger: 0.08 }, 0.55)
        .from(qa('.ro-hero-visual .ro-blob'), { scale: 0.3, opacity: 0, duration: 1.6, stagger: 0.12 }, 0.1)
        .from(q('.ro-hero .ro-stage'), { y: 60, scale: 0.85, opacity: 0, duration: 1.5 }, 0.25)
        .from(q('.ro-env-card'), { y: 80, rotationX: -30, opacity: 0, duration: 1.2, transformOrigin: '50% 100%' }, 0.55)
        .from(q('.ro-chip'), { y: -30, scale: 0.85, opacity: 0, duration: 1, ease: 'back.out(1.7)' }, 0.85)
        .from(qa('.ro-trust p, .ro-stat'), { y: 30, opacity: 0, duration: 0.9, stagger: 0.06, clearProps: 'transform,opacity' }, 0.9);

    // hero on scroll: the box opens, spins and lifts; cards drift at different depths
    const heroSec = q('.ro-hero');
    if (hero) {
        ScrollTrigger.create({ trigger: heroSec, start: 'top top', end: 'bottom top', scrub: true, onUpdate: (s) => {
            const p = s.progress;
            hero.st.target = 0.4 + p * 1.0; hero.st.spin = p * 1.6; hero.st.lift = p * 1.2; hero.st.tiltX = p * 0.35;
        } });
    }
    const scrub = { trigger: heroSec, start: 'top top', end: 'bottom top', scrub: 0.6 };
    // scroll parallax uses yPercent so it never fights the intro / cursor tweens (y, x, rotation)
    gsap.to(q('.ro-env-card'), { yPercent: -28, ease: 'none', scrollTrigger: scrub });
    gsap.to(q('.ro-chip'), { yPercent: -220, ease: 'none', scrollTrigger: scrub });
    gsap.to(q('.ro-blob-a'), { y: 120, ease: 'none', scrollTrigger: scrub });
    gsap.to(q('.ro-blob-b'), { y: -60, ease: 'none', scrollTrigger: scrub });
    gsap.to(heroCopy, { y: 80, opacity: 0.25, ease: 'none', scrollTrigger: { ...scrub, start: 'top+=120 top' } });

    // cursor: spotlight + 3D parallax in the hero, magnetic CTAs
    if (FINE) {
        // quickTo tweens are created after the intro, otherwise they overwrite its x/y/rotation tweens
        let cardX, cardRY, cardRX, chipX, aX, bX;
        const ready = () => {
            if (cardX || tl.isActive()) return !!cardX;
            const qt = (el, prop, d) => gsap.quickTo(el, prop, { duration: d, ease: 'power3' });
            cardX = qt(q('.ro-env-card'), 'x', 0.8); cardRY = qt(q('.ro-env-card'), 'rotationY', 0.8); cardRX = qt(q('.ro-env-card'), 'rotationX', 0.8);
            chipX = qt(q('.ro-chip'), 'x', 1); aX = qt(q('.ro-blob-a'), 'x', 1.6); bX = qt(q('.ro-blob-b'), 'x', 1.6);
            return true;
        };
        heroSec.addEventListener('pointermove', (e) => {
            const r = heroSec.getBoundingClientRect();
            const px = (e.clientX - r.left) / r.width - 0.5, py = (e.clientY - r.top) / r.height - 0.5;
            heroSec.style.setProperty('--mx', `${e.clientX - r.left}px`);
            heroSec.style.setProperty('--my', `${e.clientY - r.top}px`);
            heroSec.style.setProperty('--spot', 1);
            if (!ready()) return;
            cardX(px * 30); cardRY(px * 14); cardRX(-py * 10); chipX(px * -40); aX(px * -40); bX(px * 50);
        });
        heroSec.addEventListener('pointerleave', () => {
            heroSec.style.setProperty('--spot', 0);
            if (!cardX) return;
            cardX(0); cardRY(0); cardRX(0); chipX(0); aX(0); bX(0);
        });
        qa('.ro-hero-btns .ro-btn, .ro-final .ro-btn, .ro-nav-cta .ro-btn').forEach((b) => {
            let bx, by;
            b.addEventListener('pointermove', (e) => {
                if (tl.isActive()) return;
                if (!bx) { bx = gsap.quickTo(b, 'x', { duration: 0.5, ease: 'power3' }); by = gsap.quickTo(b, 'y', { duration: 0.5, ease: 'power3' }); }
                const r = b.getBoundingClientRect();
                bx((e.clientX - r.left - r.width / 2) * 0.25); by((e.clientY - r.top - r.height / 2) * 0.35);
            });
            b.addEventListener('pointerleave', () => { if (bx) { bx(0); by(0); } });
        });
    }

    // How: pinned scene on desktop (created before every trigger below it, so their positions include the pin spacer) — scroll walks through the 3 layers, the stack opens and turns
    if (DESK && howRot && how) {
        const acc = q('[data-acc]');
        acc.classList.add('ro-scroll');
        const prog = document.createElement('span');
        prog.className = 'ro-acc-prog';
        prog.innerHTML = '<i></i>';
        acc.prepend(prog);
        howRot.manual = true;
        let cur = -1;
        const st = ScrollTrigger.create({
            trigger: q('#ro-how'), start: 'top top', end: '+=170%', pin: true, anticipatePin: 1,
            onUpdate: (s) => {
                const p = s.progress, step = Math.min(2, Math.floor(p * 3));
                prog.style.setProperty('--p', p.toFixed(4));
                how.st.target = 0.25 + Math.sin(Math.min(1, p * 1.15) * Math.PI) * 0.9;
                how.st.spin = p * Math.PI * 1.1;
                how.st.tiltX = Math.sin(p * Math.PI) * 0.25;
                if (step !== cur) { cur = step; howRot.show(step); }
            },
        });
        howRot.onClick = (k) => window.scrollTo({ top: st.start + ((k + 0.5) / 3) * (st.end - st.start), behavior: 'smooth' });
        howRot.show(0, true);
    }

    // headings: word by word, behind a mask
    qa('.ro-head h2, .ro-feat h2, .ro-faq-grid h2, .ro-final h2, .ro-stories h2').forEach((h) => {
        const s = SplitText.create(h, { type: 'words', mask: 'words', wordsClass: 'ro-w' });
        gsap.from(s.words, { yPercent: 115, duration: 1, stagger: 0.05, ease: 'expo.out', scrollTrigger: { trigger: h, start: 'top 86%' } });
    });
    qa('.ro-head .ro-eyebrow, .ro-head > p, .ro-head .ro-btn, .ro-head .ro-arrow-link, .ro-feat .ro-eyebrow, .ro-feat .ro-sub, .ro-faq-grid .ro-sub, .ro-faq-grid .ro-btn, .ro-final p, .ro-final .ro-hero-btns').forEach((el) => {
        gsap.from(el, { y: 24, opacity: 0, duration: 0.9, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 90%' } });
    });

    // cards: staggered entrances (transforms cleared afterwards so hover tilt takes over)
    const batch = (sel, from, opts = {}) => {
        const els = qa(sel);
        if (!els.length) return;
        gsap.set(els, from);
        ScrollTrigger.batch(els, { start: 'top 90%', once: true, onEnter: (b) => gsap.to(b, {
            x: 0, y: 0, scale: 1, rotationX: 0, opacity: 1, duration: 1, stagger: 0.12, ease: 'expo.out', clearProps: 'transform,opacity', ...opts }) });
    };
    batch('.who-card', { y: 80, rotationX: -14, opacity: 0, transformPerspective: 900 });
    batch('.jr-card', { y: 90, opacity: 0 });
    batch('.tile', { y: 70, opacity: 0, scale: 0.94 });
    batch('.tb', { y: 50, opacity: 0 });
    batch('.faq details', { y: 30, opacity: 0 }, { stagger: 0.07 });
    batch('.acc-item', { x: -30, opacity: 0 }, { stagger: 0.1 });
    batch('.tabs button', { y: 20, opacity: 0 }, { stagger: 0.06 });
    // tech tiles pop in (the inner mark: the tile itself runs a CSS wave)
    ScrollTrigger.create({ trigger: q('[data-tech]'), start: 'top 85%', once: true, onEnter: () => {
        gsap.from(qa('.ro-tile-t'), { opacity: 0, duration: 0.6, stagger: { each: 0.04, from: 'center' } });
        gsap.from(qa('.ro-tile-t span'), { scale: 0, rotation: -25, duration: 0.9, stagger: { each: 0.04, from: 'center' }, ease: 'back.out(2)', clearProps: 'transform' });
    } });

    // product visuals rise into place; blobs drift slower than the page (depth)
    qa('.ro-feat-visual .ro-pcard, .ro-devwrap .ro-pcard').forEach((el) => {
        gsap.from(el, { y: 100, rotationX: 10, scale: 0.94, opacity: 0, transformPerspective: 1200, duration: 1.3, ease: 'expo.out',
            scrollTrigger: { trigger: el, start: 'top 88%' }, clearProps: 'transform,opacity' });
    });
    qa('.ro-blob-c, .ro-blob-d, .ro-blob-e').forEach((b, i) => {
        gsap.fromTo(b, { yPercent: 25 }, { yPercent: -25, ease: 'none', scrollTrigger: { trigger: b.parentElement, start: 'top bottom', end: 'bottom top', scrub: true } });
        gsap.from(b, { scale: 0.4, opacity: 0, duration: 1.6, ease: 'expo.out', delay: i * 0.1, scrollTrigger: { trigger: b.parentElement, start: 'top 85%' } });
    });

    // stories: card scales up, side pills slide in
    const stCard = q('.ro-st-card');
    if (stCard) {
        gsap.from(stCard, { scale: 0.9, y: 80, opacity: 0, duration: 1.3, ease: 'expo.out', scrollTrigger: { trigger: stCard, start: 'top 85%' } });
        // side pills: set, then play once (a scroll-linked from-tween here could be dropped before it played)
        const left = qa('.ro-s-l1, .ro-s-l2'), right = qa('.ro-s-r1, .ro-s-r2');
        gsap.set(left, { x: 80, opacity: 0 });
        gsap.set(right, { x: -80, opacity: 0 });
        ScrollTrigger.create({ trigger: stCard, start: 'top 80%', once: true, onEnter: () => {
            gsap.to([...left, ...right], { x: 0, opacity: 1, duration: 1.2, stagger: 0.1, ease: 'expo.out', clearProps: 'transform,opacity' });
            storyIn(q('.ro-st-slide.ro-is-on'));
        } });
    }

    // counters
    qa('.ro-stat [data-count]').forEach((el) => {
        ScrollTrigger.create({ trigger: el, start: 'top 92%', once: true, onEnter: () => countUp(el) });
    });

    // finale: the box flies in and snaps shut as you arrive
    const fs = q('.ro-final-stage');
    if (fin && fs) {
        ScrollTrigger.create({ trigger: fs, start: 'top bottom', end: 'center 55%', scrub: true, onUpdate: (s) => {
            const p = s.progress;
            fin.st.target = 1.1 * (1 - p); fin.st.spin = (1 - p) * 3; fin.st.lift = (1 - p) * -1.5;
        } });
        gsap.from(q('.ro-final'), { scale: 0.94, y: 60, borderRadius: 60, duration: 1.3, ease: 'expo.out', scrollTrigger: { trigger: q('.ro-final'), start: 'top 88%' } });
    }

    ScrollTrigger.refresh();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => ScrollTrigger.refresh());
    window.addEventListener('load', () => ScrollTrigger.refresh());
}

window.__ro = { render, stacks, motion: MOTION };  // debug hook: render one frame on demand

// ---------- technology tiles: add entries here as the platform grows ----------
const TECH = [
    [['Odoo', 'Od', '#714B67'], ['GitHub', 'GH', '#24292f'], ['PostgreSQL', 'PG', '#336791'], ['Python', 'Py', '#3776AB'],
     ['Docker', 'Dk', '#2496ED'], ['Ubuntu', 'U', '#E95420'], ['Traefik', 'Tf', '#24A1C1'], ['Let\'s Encrypt', 'LE', '#003A70']],
    [['gVisor sandbox', 'gV', '#4285F4'], ['restic backups', 're', '#0f9d8a'], ['Amazon SES mail', 'SES', '#FF9900'],
     ['Tailscale', 'Ts', '#242424'], ['SSH', '>_', '#0b3558'], ['OAuth / GitHub App', 'OA', '#6a4fd8'], ['HTTPS', '🔒', '#19c48f']],
];
const techRoot = document.querySelector('[data-tech]');
if (techRoot) {
    let k = 0;
    techRoot.innerHTML = TECH.map((row) => `<div class="ro-tech-row">${row.map(([name, mark, color]) =>
        `<div class="ro-tile-t" style="--c:${color};--k:${k++}" title="${name}"><span>${mark}</span><small>${name}</small></div>`).join('')}</div>`).join('');
}

// ---------- journey cards: hover/click opens one; auto-advance while visible ----------
(function journey() {
    const root = document.querySelector('[data-jr]');
    if (!root) return;
    const cards = [...root.querySelectorAll('.ro-jr-card')];
    let i = 0, timer = null, hover = false, seen = false;
    const show = (n) => { i = n; cards.forEach((c, k) => c.classList.toggle('ro-is-on', k === n)); };
    const tick = () => { clearTimeout(timer); timer = setTimeout(() => { if (!hover) show((i + 1) % cards.length); tick(); }, 5000); };
    cards.forEach((c, k) => {
        c.addEventListener('mouseenter', () => { if (window.innerWidth > 900) { hover = true; show(k); } });
        c.addEventListener('click', () => { show(k); tick(); });
    });
    root.addEventListener('mouseleave', () => { hover = false; });
    if (!REDUCED) new IntersectionObserver(([e]) => {
        if (e.isIntersecting) { if (!seen) { seen = true; show(0); } tick(); } else clearTimeout(timer);
    }, { threshold: 0.3 }).observe(root);
})();

// ---------- stories carousel ----------
(function stories() {
    const root = document.querySelector('[data-st]');
    if (!root) return;
    const slides = [...root.querySelectorAll('.ro-st-slide')];
    const dots = [...document.querySelectorAll('.ro-st-dots i')];
    let i = 0, timer = null;
    const show = (n) => {
        i = (n + slides.length) % slides.length;
        slides.forEach((s, k) => s.classList.toggle('ro-is-on', k === i));
        dots.forEach((d, k) => d.classList.toggle('ro-is-on', k === i));
        storyIn(slides[i]);
    };
    const tick = () => { clearTimeout(timer); timer = setTimeout(() => { show(i + 1); tick(); }, 7000); };
    root.querySelectorAll('[data-go]').forEach((b) => b.addEventListener('click', () => { show(i + Number(b.dataset.go)); tick(); }));
    dots.forEach((d, k) => d.addEventListener('click', () => { show(k); tick(); }));
    if (!REDUCED) new IntersectionObserver(([e]) => { if (e.isIntersecting) tick(); else clearTimeout(timer); }, { threshold: 0.3 }).observe(root);
})();

if (MOTION) motion();

document.querySelectorAll('.ro-year').forEach((el) => { el.textContent = new Date().getFullYear(); });
window.__roReady = true;
