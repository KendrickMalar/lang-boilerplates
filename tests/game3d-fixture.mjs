import { join } from "node:path";
import { ROOT, copyPreset, write, runAt } from "./helpers.mjs";

// Verification-only game. None of these sources belong to the copyable preset.
export async function createGame3dFixture() {
  const root = await copyPreset("web-game-3d", { sample: false });
  await write(
    root,
    "index.html",
    `<!doctype html>
<html lang="en"><head><meta charset="UTF-8"><title>3D verification</title></head>
<body><output data-testid="ready">loading</output><output data-testid="height"></output>
<output data-testid="contact"></output><output data-testid="position"></output>
<output data-testid="pixel"></output><output data-testid="viewport"></output>
<script type="module" src="/src/index.ts"></script></body></html>
`,
  );
  await write(
    root,
    "src/index.ts",
    `import * as THREE from "three";
import RAPIER from "@dimforge/rapier3d-compat";

function report(name: string, value: string): void {
  const output = document.querySelector('[data-testid="' + name + '"]');
  if (!output) throw new Error("Missing output " + name);
  output.textContent = value;
}
async function start(): Promise<void> {
  await RAPIER.init();
  const renderer = new THREE.WebGLRenderer({ preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  document.body.append(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x224466);
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
  camera.position.set(0, 3, 6);
  const cube = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: 0xff0000 }));
  scene.add(cube);
  const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  world.timestep = 1 / 60;
  const ground = world.createCollider(RAPIER.ColliderDesc.cuboid(10, 0.1, 10));
  const body = world.createRigidBody(RAPIER.RigidBodyDesc.dynamic().setTranslation(0, 3, 0));
  const collider = world.createCollider(RAPIER.ColliderDesc.cuboid(0.5, 0.5, 0.5), body);
  const size = new THREE.Vector2();
  const resize = (): void => {
    const width = window.innerWidth;
    const height = window.innerHeight;
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.getDrawingBufferSize(size);
    report("viewport", size.x.toString() + "x" + size.y.toString());
  };
  resize();
  window.addEventListener("resize", resize);
  window.addEventListener("keydown", (event: KeyboardEvent) => {
    if (event.code === "ArrowRight") {
      const current = body.translation();
      body.setTranslation({ ...current, x: current.x + 0.25 }, true);
    }
  });
  const gl = renderer.getContext();
  const pixel = new Uint8Array(4);
  const clock = new THREE.Timer();
  let accumulator = 0;
  renderer.setAnimationLoop(() => {
    clock.update();
    accumulator += Math.min(clock.getDelta(), 0.1);
    while (accumulator >= 1 / 60) {
      world.step();
      accumulator -= 1 / 60;
    }
    const position = body.translation();
    cube.position.set(position.x, position.y, position.z);
    camera.lookAt(cube.position);
    renderer.render(scene, camera);
    gl.readPixels(Math.floor(size.x / 2), Math.floor(size.y / 2), 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    report("pixel", Array.from(pixel).join(","));
    report("height", position.y.toFixed(2));
    report("position", position.x.toFixed(2));
    const contacts: boolean[] = [];
    world.contactPair(collider, ground, () => { contacts.push(true); });
    report("contact", contacts.length > 0 ? "yes" : "no");
    report("ready", "ready");
  });
}
void start().catch((error: unknown) => {
  report("ready", "error");
  throw error;
});
`,
  );
  await write(
    root,
    "tests/physics.test.ts",
    `import { expect, test } from "vitest";
import RAPIER from "@dimforge/rapier3d-compat";

test("copied preset executes real WASM physics", async () => {
  await RAPIER.init();
  const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  world.createCollider(RAPIER.ColliderDesc.cuboid(10, 0.1, 10));
  const body = world.createRigidBody(RAPIER.RigidBodyDesc.dynamic().setTranslation(0, 3, 0));
  world.createCollider(RAPIER.ColliderDesc.cuboid(0.5, 0.5, 0.5), body);
  for (let step = 0; step < 240; step += 1) world.step();
  expect(body.translation().y).toBeGreaterThan(0.55);
  expect(body.translation().y).toBeLessThan(0.65);
  world.free();
});
`,
  );
  await write(
    root,
    "tests/e2e/game.spec.ts",
    `import { expect, test } from "@playwright/test";

test("renders, collides, responds to keys and resizes", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  page.on("requestfailed", (request) => errors.push("request failed: " + request.url()));
  page.on("response", (response) => { if (response.status() >= 400) errors.push("HTTP " + response.status().toString() + ": " + response.url()); });
  await page.goto("/");
  await expect(page.getByTestId("ready")).toHaveText("ready");
  await expect(page.getByTestId("pixel")).toHaveText("255,0,0,255");
  await expect(page.getByTestId("contact")).toHaveText("yes");
  await expect(page.getByTestId("height")).toHaveText("0.60");
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("position")).toHaveText("0.25");
  await page.setViewportSize({ width: 640, height: 480 });
  await expect(page.getByTestId("viewport")).toHaveText("640x480");
  const canvas = page.locator("canvas");
  await expect(canvas).toHaveAttribute("width", "640");
  await expect(canvas).toHaveAttribute("height", "480");
  await canvas.screenshot({ path: testInfo.outputPath("game.png") });
  expect(errors).toEqual([]);
});
`,
  );
  const formatted = runAt(root, "pnpm", ["format"]);
  if (formatted.status !== 0) throw new Error(formatted.output);
  return root;
}

export const browserPath = join(ROOT, ".verification", "playwright");
export const browserEnv = { PLAYWRIGHT_BROWSERS_PATH: browserPath };
