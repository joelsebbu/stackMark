/**
 * Vanta.js "DOTS" background (https://www.vantajs.com/?effect=dots).
 * Requires window.THREE before importing the effect module.
 */
let instance: { destroy: () => void } | null = null;

type VantaWindow = Window &
  typeof globalThis & {
    THREE: object;
    VANTA: { DOTS: (opts: Record<string, unknown>) => { destroy: () => void } };
  };

export async function initVantaDots(): Promise<void> {
  const el = document.getElementById("vanta-bg");
  if (!el) return;

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    el.style.display = "none";
    if (instance) {
      instance.destroy();
      instance = null;
    }
    return;
  }

  el.style.display = "";
  if (el.dataset.vantaReady === "1") return;

  const THREE = await import("three");
  const w = window as unknown as VantaWindow;
  w.THREE = THREE as unknown as object;
  await import("./vanta-dots-effect.js");

  instance = w.VANTA.DOTS({
    el,
    mouseControls: true,
    touchControls: true,
    gyroControls: false,
    minHeight: 200,
    minWidth: 200,
    scale: 1,
    scaleMobile: 1,
    color: 0xff671f,
    color2: 0xb4c5ff,
    backgroundColor: 0x051424,
    showLines: false,
  });

  el.dataset.vantaReady = "1";
}

