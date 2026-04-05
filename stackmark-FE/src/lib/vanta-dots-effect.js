/**
 * Vanta "DOTS" effect — forked from vanta/src/vanta.dots.js with slightly
 * faster surface wave + camera follow (upstream hardcodes these rates).
 */
import VantaBase, { VANTA } from "vanta/src/_base.js";
import { rn } from "vanta/src/helpers.js";

const win = typeof window == "object";
let THREE = win && window.THREE;

/** Wider than upstream ±30 so the field reaches further toward the horizon */
const GRID_HALF = 54;
/** Fog fades distant dots into the background — lower = you see farther */
const FOG_DENSITY = 0.00038;

class Effect extends VantaBase {
  static initClass() {
    this.prototype.defaultOptions = {
      color: 0xff671f,
      color2: 0xb4c5ff,
      backgroundColor: 0x051424,
      size: 3,
      spacing: 35,
      showLines: true,
    };
  }

  onInit() {
    var camera = (this.camera = new THREE.PerspectiveCamera(
      50,
      this.width / this.height,
      0.1,
      5000
    ));
    camera.position.x = 0;
    camera.position.y = 250;
    camera.position.z = 50;
    camera.tx = 0;
    camera.ty = 50;
    camera.tz = 350;
    camera.lookAt(0, 0, 0);
    this.scene.add(camera);

    const bg = this.options.backgroundColor;
    if (bg != null) {
      this.scene.fog = new THREE.FogExp2(bg, FOG_DENSITY);
    }

    var starsGeometry = (this.starsGeometry = new THREE.BufferGeometry());
    var i, j, k, l, star, starsMaterial, starField;
    var space = this.options.spacing;
    const points = [];

    for (i = k = -GRID_HALF; k <= GRID_HALF; i = ++k) {
      for (j = l = -GRID_HALF; l <= GRID_HALF; j = ++l) {
        star = new THREE.Vector3();
        star.x = i * space + space / 2;
        star.y = rn(0, 5) - 150;
        star.z = j * space + space / 2;
        points.push(star);
      }
    }
    starsGeometry.setFromPoints(points);

    starsMaterial = new THREE.PointsMaterial({
      color: this.options.color,
      size: this.options.size,
      fog: true,
    });
    starField = this.starField = new THREE.Points(starsGeometry, starsMaterial);
    this.scene.add(starField);

    if (this.options.showLines) {
      var material = new THREE.LineBasicMaterial({ color: this.options.color2 });
      var linesGeo = new THREE.BufferGeometry();
      const linePoints = [];
      for (i = 0; i < 200; i++) {
        var f1 = rn(40, 60);
        var f2 = f1 + rn(12, 20);
        var z = rn(-1, 1);
        var r = Math.sqrt(1 - z * z);
        var theta = rn(0, Math.PI * 2);
        var y = Math.sin(theta) * r;
        var x = Math.cos(theta) * r;
        linePoints.push(new THREE.Vector3(x * f1, y * f1, z * f1));
        linePoints.push(new THREE.Vector3(x * f2, y * f2, z * f2));
      }
      linesGeo.setFromPoints(linePoints);
      this.linesMesh = new THREE.LineSegments(linesGeo, material);
      this.scene.add(this.linesMesh);
    }
  }

  onUpdate() {
    const starsGeometry = this.starsGeometry;
    for (var j = 0; j < starsGeometry.attributes.position.array.length; j += 3) {
      const x = starsGeometry.attributes.position.array[j];
      const y = starsGeometry.attributes.position.array[j + 1];
      const z = starsGeometry.attributes.position.array[j + 2];
      /* upstream: this.t*0.02 — bumped for a slightly faster wave */
      const newY = y + 0.1 * Math.sin(z * 0.02 + x * 0.015 + this.t * 0.032);
      starsGeometry.attributes.position.array[j + 1] = newY;
    }

    starsGeometry.attributes.position.setUsage(THREE.DynamicDrawUsage);
    starsGeometry.computeVertexNormals();
    starsGeometry.attributes.position.needsUpdate = true;

    const c = this.camera;
    /* Higher = camera reaches mouse target faster (upstream 0.003) */
    const rate = 0.012;
    c.position.x += (c.tx - c.position.x) * rate;
    c.position.y += (c.ty - c.position.y) * rate;
    c.position.z += (c.tz - c.position.z) * rate;
    c.lookAt(0, 0, 0);

    if (this.linesMesh) {
      this.linesMesh.rotation.z += 0.002;
      this.linesMesh.rotation.x += 0.0008;
      this.linesMesh.rotation.y += 0.0005;
    }
  }

  onMouseMove(x, y) {
    /* Stronger targets = more parallax per pixel (upstream: *100, + y*50) */
    this.camera.tx = (x - 0.5) * 175;
    this.camera.ty = 42 + y * 78;
  }

  onRestart() {
    this.scene.remove(this.starField);
  }
}
Effect.initClass();
export default VANTA.register("DOTS", Effect);
