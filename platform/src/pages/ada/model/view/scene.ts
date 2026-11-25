import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { ModelMap } from '@/api/ada';
import type { Ink } from '@/lib/tokens';
import { cloud, decodeBits } from './glyphs';
import { EXPLODE_SCALE, Layout, layoutRadius } from './layout';

/**
 * A glyph's point cloud spans this much of the scene (the old viewer's 0.41 cloud at 0.2 scale), grown with the
 * layout's radius past the old viewer's 200 glyphs, so a cloud looks the same size however many are shown.
 */
const CLOUD_SCALE = 0.41 * 0.2;
const POINT_SIZE = 0.03;
const grown = (n: number) => layoutRadius(n) / layoutRadius(1);
/** Laid out without being drawn when the person asked for less motion: this many steps, then drawn once. */
const QUIET_STEPS = 400;
const SETTLED = 0.0005;

const vertex = /* glsl */ `
  attribute float node;
  uniform sampler2D places;
  uniform sampler2D tints;
  uniform vec2 size;
  uniform float scale;
  uniform float pointSize;
  varying vec4 tint;
  void main() {
    vec2 uv = (vec2(mod(node, size.x), floor(node / size.x)) + 0.5) / size;
    vec4 at = texture2D(places, uv);
    tint = texture2D(tints, uv);
    vec4 mv = modelViewMatrix * vec4(at.xyz + position, 1.0);
    gl_PointSize = max(1.0, pointSize * scale / -mv.z);
    gl_Position = projectionMatrix * mv;
  }`;
const fragment = /* glsl */ `
  varying vec4 tint;
  void main() {
    if (tint.a < 0.01) discard;
    gl_FragColor = tint;
  }`;

export type Look = { colours: string[]; same: boolean[]; showSame: boolean; showDifferent: boolean; highlight: Set<number> | null; explode: boolean; ink: Ink };

/**
 * The 3D view, ported from the old GlyphViewer: each precedent a point cloud of its glyph's bits (one draw for them
 * all, each cloud placed by a texture of the layout's positions), its nearest joined by lines (same outcome, and
 * different, each shown or not), a highlighted point's neighbourhood bright and the rest dimmed, and an exploded view.
 */
export class GlyphScene {
  readonly renderer: THREE.WebGLRenderer;
  readonly camera: THREE.PerspectiveCamera;
  readonly controls: OrbitControls;
  readonly layout: Layout;
  private readonly scene = new THREE.Scene();
  private readonly places: THREE.DataTexture;
  private readonly tints: THREE.DataTexture;
  private readonly material: THREE.ShaderMaterial;
  private readonly lines: { same: THREE.LineSegments; different: THREE.LineSegments; bright: THREE.LineSegments };
  private readonly edges: ModelMap['edges'];
  private look: Look | null = null;
  private frame = 0;
  private quiet: boolean;
  frozen = false;
  /** Called each frame the scene is drawn, for the labels over it. */
  onDraw: () => void = () => {};

  constructor(canvas: HTMLCanvasElement, map: ModelMap, groups: number[], quiet: boolean) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.quiet = quiet;
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 4000);
    this.camera.position.set(0, 30, 70);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = !quiet;
    this.controls.dampingFactor = 0.1;
    this.edges = map.edges;
    const shown = map.points.map((p) => p.bits !== null);
    this.layout = new Layout(groups, map.edges.filter(([a, b]) => shown[a] && shown[b]));

    const n = Math.max(1, map.points.length);
    const width = Math.min(n, 1024);
    const height = Math.ceil(n / width);
    this.places = new THREE.DataTexture(new Float32Array(width * height * 4), width, height, THREE.RGBAFormat, THREE.FloatType);
    this.tints = new THREE.DataTexture(new Uint8Array(width * height * 4), width, height, THREE.RGBAFormat, THREE.UnsignedByteType);
    this.material = new THREE.ShaderMaterial({
      vertexShader: vertex,
      fragmentShader: fragment,
      transparent: true,
      depthWrite: false,
      uniforms: { places: { value: this.places }, tints: { value: this.tints }, size: { value: new THREE.Vector2(width, height) }, scale: { value: 300 }, pointSize: { value: POINT_SIZE * grown(n) } },
    });
    this.scene.add(new THREE.Points(this.clouds(map), this.material));
    const lines = () => new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ transparent: true, depthTest: false }));
    this.lines = { same: lines(), different: lines(), bright: lines() };
    for (const line of Object.values(this.lines)) this.scene.add(line);
  }

  /** Every glyph's cloud in one geometry, each vertex naming its point. */
  private clouds(map: ModelMap): THREE.BufferGeometry {
    const parts = map.points.map((p) => (p.bits ? cloud(decodeBits(p.bits, map.dim), CLOUD_SCALE * grown(map.points.length)) : new Float32Array([0, 0, 0])));
    const total = parts.reduce((sum, part) => sum + part.length, 0);
    const position = new Float32Array(total);
    const node = new Float32Array(total / 3);
    let at = 0;
    parts.forEach((part, i) => {
      position.set(part, at);
      node.fill(i, at / 3, (at + part.length) / 3);
      at += part.length;
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(position, 3));
    geometry.setAttribute('node', new THREE.BufferAttribute(node, 1));
    geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(), Infinity); // placed in the shader: never culled
    return geometry;
  }

  /** Where point i is drawn now (the layout's place, spread when exploded). */
  placeOf(i: number, into = new THREE.Vector3()): THREE.Vector3 {
    const p = this.layout.positions;
    const spread = this.look?.explode ? EXPLODE_SCALE : 1;
    return into.set(p[i * 3]! * spread, p[i * 3 + 1]! * spread, p[i * 3 + 2]! * spread);
  }

  setLook(look: Look): void {
    this.look = look;
    const { ink } = look;
    this.scene.background = new THREE.Color(ink.bg);
    const data = this.tints.image.data as Uint8Array;
    const colour = new THREE.Color();
    const rgb = { r: 0, g: 0, b: 0 };
    look.colours.forEach((css, i) => {
      // The shader writes what it is given to the page as it is: the token's own sRGB, not three's linear.
      colour.set(css).getRGB(rgb, THREE.SRGBColorSpace);
      const dim = look.highlight !== null && !look.highlight.has(i);
      data.set([rgb.r * 255, rgb.g * 255, rgb.b * 255, dim ? 30 : 255], i * 4);
    });
    this.tints.needsUpdate = true;
    const tone = (line: THREE.LineSegments, css: string, opacity: number, visible: boolean) => {
      const material = line.material as THREE.LineBasicMaterial;
      material.color.set(css);
      material.opacity = opacity;
      line.visible = visible;
    };
    const lit = look.highlight !== null;
    tone(this.lines.same, ink.lineStrong, lit ? 0.08 : 0.6, look.showSame);
    tone(this.lines.different, ink.series[3]!, lit ? 0.08 : 0.5, look.showDifferent);
    tone(this.lines.bright, ink.text, 1, lit);
    this.placeLines();
  }

  private shownEdge(e: number): boolean {
    const look = this.look;
    return Boolean(look && (look.same[e] ? look.showSame : look.showDifferent));
  }

  private placeLines(): void {
    const sets = { same: [] as number[], different: [] as number[], bright: [] as number[] };
    const a = new THREE.Vector3();
    const b = new THREE.Vector3();
    const highlight = this.look?.highlight ?? null;
    this.edges.forEach(([i, j], e) => {
      if (!this.look) return;
      this.placeOf(i, a);
      this.placeOf(j, b);
      const into = this.look.same[e] ? sets.same : sets.different;
      into.push(a.x, a.y, a.z, b.x, b.y, b.z);
      if (highlight && this.shownEdge(e) && highlight.has(i) && highlight.has(j)) sets.bright.push(a.x, a.y, a.z, b.x, b.y, b.z);
    });
    for (const [name, values] of Object.entries(sets)) {
      const line = this.lines[name as keyof typeof sets];
      line.geometry.setAttribute('position', new THREE.Float32BufferAttribute(values, 3));
    }
  }

  private placePoints(): void {
    const data = this.places.image.data as Float32Array;
    const v = new THREE.Vector3();
    for (let i = 0; i < this.layout.n; i++) {
      this.placeOf(i, v);
      data.set([v.x, v.y, v.z, 1], i * 4);
    }
    this.places.needsUpdate = true;
    this.placeLines();
  }

  resize(width: number, height: number): void {
    if (!width || !height) return;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.material.uniforms.scale!.value = height / 2;
  }

  /** The camera back far enough to see every point, looking at the middle. */
  fit(): void {
    let far = 0;
    const v = new THREE.Vector3();
    for (let i = 0; i < this.layout.n; i++) far = Math.max(far, this.placeOf(i, v).length());
    const distance = Math.max(30, (far + 2) / Math.sin(THREE.MathUtils.degToRad(this.camera.fov / 2)));
    this.camera.position.set(0, distance * 0.35, distance * 0.94);
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }

  /** The camera turns about point i. */
  focus(i: number): void {
    this.controls.target.copy(this.placeOf(i));
  }

  /** Each point's place on screen in pixels (x, y) and its depth (z > 1: behind the camera). */
  onScreen(width: number, height: number): Float32Array {
    const out = new Float32Array(this.layout.n * 3);
    const v = new THREE.Vector3();
    for (let i = 0; i < this.layout.n; i++) {
      this.placeOf(i, v).project(this.camera);
      out.set([(v.x * 0.5 + 0.5) * width, (-v.y * 0.5 + 0.5) * height, v.z], i * 3);
    }
    return out;
  }

  /**
   * Lays out and draws, a frame at a time, until stopped; the layout rests once it settles. Quiet (less motion): laid
   * out unseen, then drawn still.
   */
  start(): void {
    let steps = 0;
    this.fit();
    const tick = () => {
      this.frame = requestAnimationFrame(tick);
      if (this.quiet) {
        for (let s = 0; s < 20; s++) this.layout.step();
        steps += 20;
        if (steps < QUIET_STEPS && this.layout.moved >= SETTLED) return;
        this.quiet = false; // laid out: drawn from now, and moved again only when the person unfreezes it
        this.fit();
      } else if (!this.frozen && this.layout.moved >= SETTLED) {
        this.layout.step();
      }
      this.placePoints();
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
      this.onDraw();
    };
    tick();
  }

  dispose(): void {
    cancelAnimationFrame(this.frame);
    this.controls.dispose();
    this.scene.traverse((object) => {
      const held = object as THREE.Mesh;
      held.geometry?.dispose();
      (held.material as THREE.Material | undefined)?.dispose?.();
    });
    this.places.dispose();
    this.tints.dispose();
    this.renderer.dispose();
  }
}
