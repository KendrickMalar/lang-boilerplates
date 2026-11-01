// Verification-only sources for the architecture choices. None belong to a preset.
// Each case: files that follow the rules, and violations with the rule that must report them.

const exportOf = (name, from) =>
  "import { " +
  name +
  " } from " +
  JSON.stringify(from) +
  ";\nexport const copy = " +
  name +
  ";\n";
const typeOf = (name, from) =>
  "import type { " +
  name +
  " } from " +
  JSON.stringify(from) +
  ";\nexport type Copy = " +
  name +
  ";\n";
const stray = {
  path: "src/stray.ts",
  source: "export const stray = 1;\n",
  rule: "boundaries/no-unknown-files",
};
const dependency = (path, source) => ({
  path,
  source,
  rule: "boundaries/dependencies",
});
const global = (path, source) => ({
  path,
  source,
  rule: "no-restricted-globals",
});

const nodeOnion = {
  "src/domain/price.ts":
    "export interface Price {\n  readonly amount: number;\n}\nexport function total(prices: readonly Price[]): number {\n  return prices.reduce((sum, price) => sum + price.amount, 0);\n}\n",
  "src/application/checkout.ts":
    'import { total, type Price } from "../domain/price.js";\nexport interface PriceSource {\n  load(): Promise<Price[]>;\n}\nexport async function checkout(source: PriceSource): Promise<number> {\n  return total(await source.load());\n}\n',
  "src/infrastructure/file-prices.ts":
    'import { readFile } from "node:fs/promises";\nimport type { PriceSource } from "../application/checkout.js";\nimport type { Price } from "../domain/price.js";\nexport function filePrices(path: string): PriceSource {\n  return {\n    load: async (): Promise<Price[]> => JSON.parse(await readFile(path, "utf8")) as Price[],\n  };\n}\n',
  "src/presentation/cli.ts":
    'import { checkout, type PriceSource } from "../application/checkout.js";\nexport async function run(source: PriceSource): Promise<string> {\n  return String(await checkout(source));\n}\n',
  "src/main.ts":
    'import { filePrices } from "./infrastructure/file-prices.js";\nimport { run } from "./presentation/cli.js";\nexport async function main(path: string): Promise<string> {\n  return run(filePrices(path));\n}\n',
};

const browserOnion = {
  "src/domain/score.ts":
    "export interface Score {\n  readonly points: number;\n}\nexport function add(score: Score, points: number): Score {\n  return { points: score.points + points };\n}\n",
  "src/application/play.ts":
    'import { add, type Score } from "../domain/score";\nexport interface ScoreStore {\n  save(score: Score): void;\n}\nexport function play(store: ScoreStore, score: Score): Score {\n  const next = add(score, 1);\n  store.save(next);\n  return next;\n}\n',
  "src/infrastructure/storage.ts":
    'import type { ScoreStore } from "../application/play.js";\nexport const storage: ScoreStore = {\n  save: (score) => {\n    localStorage.setItem("score", String(score.points));\n  },\n};\n',
  "src/presentation/logo.svg":
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"></svg>\n',
  "src/presentation/view.ts":
    'import type { Score } from "../domain/score";\nimport logo from "./logo.svg";\nexport function show(score: Score): void {\n  document.title = logo + String(score.points);\n}\n',
  "src/main.ts":
    'import { play } from "./application/play";\nimport { storage } from "./infrastructure/storage";\nimport { show } from "./presentation/view";\nshow(play(storage, { points: 0 }));\n',
};

const gameCore = {
  "src/domain/state.ts":
    "export interface State {\n  readonly x: number;\n}\nexport interface Input {\n  readonly right: boolean;\n}\nexport function step(state: State, input: Input, dt: number): State {\n  return { x: state.x + (input.right ? dt : 0) };\n}\n",
  "src/application/loop.ts":
    'import { step, type Input, type State } from "../domain/state.js";\nexport function advance(state: State, input: Input, elapsed: number): State {\n  let next = state;\n  for (let time = 0; time + 1 / 60 <= elapsed; time += 1 / 60) next = step(next, input, 1 / 60);\n  return next;\n}\n',
  "src/infrastructure/physics.ts":
    'import RAPIER from "@dimforge/rapier3d-compat";\nexport async function createWorld(): Promise<RAPIER.World> {\n  await RAPIER.init();\n  return new RAPIER.World({ x: 0, y: -9.81, z: 0 });\n}\n',
  "src/presentation/render.ts":
    'import * as THREE from "three";\nimport type { State } from "../domain/state.js";\nexport function place(mesh: THREE.Object3D, state: State): void {\n  mesh.position.copy(new THREE.Vector3(state.x, 0, 0));\n}\n',
  "src/main.ts":
    'import * as THREE from "three";\nimport { advance } from "./application/loop.js";\nimport { createWorld } from "./infrastructure/physics.js";\nimport { place } from "./presentation/render.js";\nconst mesh = new THREE.Object3D();\nvoid createWorld().then(() => {\n  place(mesh, advance({ x: 0 }, { right: true }, 1));\n});\n',
};

export const architectureCases = [
  {
    leaf: "cli",
    option: "onion",
    heading: "オニオン（既定）",
    files: nodeOnion,
    violations: [
      dependency(
        "src/domain/uses-infrastructure.ts",
        exportOf("filePrices", "../infrastructure/file-prices.js"),
      ),
      dependency(
        "src/domain/uses-node.ts",
        exportOf("readFileSync", "node:fs"),
      ),
      dependency(
        "src/domain/uses-package.ts",
        exportOf("version", "typescript"),
      ),
      global("src/domain/uses-process.ts", "export const id = process.pid;\n"),
      global("src/domain/uses-fetch.ts", "export const load = fetch;\n"),
      dependency(
        "src/application/uses-presentation.ts",
        exportOf("run", "../presentation/cli.js"),
      ),
      dependency(
        "src/application/uses-node.ts",
        exportOf("readFileSync", "node:fs"),
      ),
      dependency(
        "src/presentation/uses-infrastructure.ts",
        exportOf("filePrices", "../infrastructure/file-prices.js"),
      ),
      dependency("src/domain/uses-stray.ts", exportOf("stray", "../stray.js")),
      stray,
    ],
  },
  {
    leaf: "cli",
    option: "functional-core",
    heading: "機能コア＋命令的シェル",
    files: {
      "src/core/total.ts":
        "export function total(values: readonly number[]): number {\n  return values.reduce((sum, value) => sum + value, 0);\n}\n",
      "src/shell/read.ts":
        'import { readFile } from "node:fs/promises";\nimport { total } from "../core/total.js";\nexport async function readTotal(path: string): Promise<number> {\n  return total(JSON.parse(await readFile(path, "utf8")) as number[]);\n}\n',
      "src/main.ts":
        'import { readTotal } from "./shell/read.js";\nexport async function main(path: string): Promise<number> {\n  return readTotal(path);\n}\n',
    },
    violations: [
      dependency(
        "src/core/uses-shell.ts",
        exportOf("readTotal", "../shell/read.js"),
      ),
      dependency("src/core/uses-node.ts", exportOf("readFileSync", "node:fs")),
      global("src/core/uses-process.ts", "export const args = process.argv;\n"),
      stray,
    ],
  },
  {
    leaf: "cli",
    option: "vertical-slices",
    heading: "機能別の縦割り",
    files: {
      "src/shared/id.ts":
        'export type Id = string & { readonly brand: "Id" };\nexport function toId(value: string): Id {\n  return value as Id;\n}\n',
      "src/features/users/domain/user.ts":
        'import type { Id } from "../../../shared/id.js";\nexport interface User {\n  readonly id: Id;\n  readonly name: string;\n}\n',
      "src/features/users/application/describe.ts":
        'import type { User } from "../domain/user.js";\nexport function describe(user: User): string {\n  return user.name;\n}\n',
      "src/features/users/index.ts":
        'export { describe } from "./application/describe.js";\nexport type { User } from "./domain/user.js";\n',
      "src/features/orders/domain/order.ts":
        "export interface Order {\n  readonly total: number;\n}\n",
      "src/features/orders/application/summary.ts":
        'import { describe, type User } from "../../users/index.js";\nimport type { Order } from "../domain/order.js";\nexport function summary(user: User, order: Order): string {\n  return describe(user) + ": " + String(order.total);\n}\n',
      "src/features/orders/infrastructure/store.ts":
        'import { readFile } from "node:fs/promises";\nimport type { Order } from "../domain/order.js";\nexport async function load(path: string): Promise<Order> {\n  return JSON.parse(await readFile(path, "utf8")) as Order;\n}\n',
      "src/features/orders/index.ts":
        'export { summary } from "./application/summary.js";\nexport { load } from "./infrastructure/store.js";\n',
      "src/main.ts":
        'import { load, summary } from "./features/orders/index.js";\nimport { toId } from "./shared/id.js";\nexport async function main(path: string): Promise<string> {\n  return summary({ id: toId("u"), name: "n" }, await load(path));\n}\n',
    },
    violations: [
      dependency(
        "src/features/orders/application/uses-other-internal.ts",
        exportOf("describe", "../../users/application/describe.js"),
      ),
      dependency(
        "src/features/orders/application/uses-other-domain.ts",
        typeOf("User", "../../users/domain/user.js"),
      ),
      dependency(
        "src/features/orders/domain/uses-other-entry.ts",
        exportOf("describe", "../../users/index.js"),
      ),
      dependency(
        "src/features/orders/domain/uses-infrastructure.ts",
        exportOf("load", "../infrastructure/store.js"),
      ),
      global(
        "src/features/orders/domain/uses-process.ts",
        "export const id = process.pid;\n",
      ),
      stray,
    ],
    entryViolation: dependency(
      "src/main.ts",
      'import { load } from "./features/orders/infrastructure/store.js";\nexport const copy = load;\n',
    ),
  },
  {
    leaf: "web",
    option: "onion",
    heading: "オニオン（既定）",
    files: browserOnion,
    violations: [
      dependency(
        "src/domain/uses-infrastructure.ts",
        exportOf("storage", "../infrastructure/storage.js"),
      ),
      dependency(
        "src/domain/uses-package.ts",
        exportOf("defineConfig", "vite"),
      ),
      global(
        "src/domain/uses-dom.ts",
        "export const title = document.title;\n",
      ),
      global("src/domain/uses-fetch.ts", "export const load = fetch;\n"),
      dependency(
        "src/application/uses-presentation.ts",
        exportOf("show", "../presentation/view"),
      ),
      dependency(
        "src/presentation/uses-infrastructure.ts",
        exportOf("storage", "../infrastructure/storage"),
      ),
      stray,
    ],
  },
  {
    leaf: "web-game",
    option: "pure-core",
    heading: "ルールの純粋コア（既定）",
    files: gameCore,
    violations: [
      dependency("src/domain/uses-three.ts", exportOf("Vector3", "three")),
      dependency(
        "src/domain/uses-physics.ts",
        'import RAPIER from "@dimforge/rapier3d-compat";\nexport const physics = RAPIER;\n',
      ),
      global(
        "src/domain/uses-frame.ts",
        "export const frame = requestAnimationFrame;\n",
      ),
      dependency(
        "src/domain/uses-application.ts",
        exportOf("advance", "../application/loop.js"),
      ),
      dependency("src/application/uses-three.ts", exportOf("Vector3", "three")),
      dependency(
        "src/presentation/uses-infrastructure.ts",
        exportOf("createWorld", "../infrastructure/physics.js"),
      ),
      stray,
    ],
  },
  {
    leaf: "web-game",
    option: "ecs",
    heading: "ECS",
    files: {
      "src/ecs/components/position.ts":
        "export interface Position {\n  x: number;\n}\n",
      "src/ecs/systems/movement.ts":
        'import type { Position } from "../components/position.js";\nexport function move(position: Position, dt: number): void {\n  position.x += dt;\n}\n',
      "src/ecs/render/scene.ts":
        'import * as THREE from "three";\nimport type { Position } from "../components/position.js";\nexport function draw(mesh: THREE.Object3D, position: Position): void {\n  mesh.position.copy(new THREE.Vector3(position.x, 0, 0));\n}\n',
      "src/main.ts":
        'import * as THREE from "three";\nimport { draw } from "./ecs/render/scene.js";\nimport { move } from "./ecs/systems/movement.js";\nconst position = { x: 0 };\nmove(position, 1);\ndraw(new THREE.Object3D(), position);\n',
    },
    violations: [
      dependency(
        "src/ecs/components/uses-systems.ts",
        exportOf("move", "../systems/movement.js"),
      ),
      dependency(
        "src/ecs/components/uses-three.ts",
        exportOf("Vector3", "three"),
      ),
      dependency("src/ecs/systems/uses-three.ts", exportOf("Vector3", "three")),
      dependency(
        "src/ecs/systems/uses-render.ts",
        exportOf("draw", "../render/scene.js"),
      ),
      global(
        "src/ecs/systems/uses-dom.ts",
        "export const title = document.title;\n",
      ),
      stray,
    ],
  },
  {
    leaf: "web-game",
    option: "engine-shell",
    heading: "コア＋エンジンの殻",
    files: {
      "src/core/rules.ts":
        "export function next(x: number, dt: number): number {\n  return x + dt;\n}\n",
      "src/shell/engine.ts":
        'import * as THREE from "three";\nimport { next } from "../core/rules.js";\nexport function tick(mesh: THREE.Object3D, dt: number): void {\n  mesh.position.copy(new THREE.Vector3(next(mesh.position.x, dt), 0, 0));\n}\n',
      "src/main.ts":
        'import * as THREE from "three";\nimport { tick } from "./shell/engine.js";\ntick(new THREE.Object3D(), 1);\n',
    },
    violations: [
      dependency("src/core/uses-three.ts", exportOf("Vector3", "three")),
      dependency(
        "src/core/uses-shell.ts",
        exportOf("tick", "../shell/engine.js"),
      ),
      global(
        "src/core/uses-window.ts",
        "export const width = window.innerWidth;\n",
      ),
      stray,
    ],
  },
  {
    leaf: "ts-library",
    option: "single-entry",
    heading: "入口1つ＋internal（既定）",
    files: {
      "src/internal/sum.ts":
        "export function sum(values: readonly number[]): number {\n  return values.reduce((total, value) => total + value, 0);\n}\n",
      "src/internal/average.ts":
        'import { sum } from "./sum.js";\nexport function average(values: readonly number[]): number {\n  return values.length === 0 ? 0 : sum(values) / values.length;\n}\n',
      "src/index.ts":
        'export { average } from "./internal/average.js";\nexport { sum } from "./internal/sum.js";\n',
    },
    violations: [
      dependency("src/internal/uses-entry.ts", exportOf("sum", "../index.js")),
      stray,
    ],
    cycle: {
      "src/internal/sum.ts":
        'import { average } from "./average.js";\nexport function sum(values: readonly number[]): number {\n  return values.length < 0 ? average(values) : values.reduce((total, value) => total + value, 0);\n}\n',
    },
  },
  {
    leaf: "ts-library",
    option: "core-adapters",
    heading: "コア＋実行環境アダプター",
    files: {
      "src/core/format.ts":
        'export function format(name: string): string {\n  return "Hello, " + name;\n}\n',
      "src/adapters/node/index.ts":
        'import { writeFileSync } from "node:fs";\nimport { format } from "../../core/format.js";\nexport function save(path: string, name: string): void {\n  writeFileSync(path, format(name));\n}\n',
      "src/adapters/memory/index.ts":
        'import { format } from "../../core/format.js";\nexport function remember(names: string[], name: string): string[] {\n  return [...names, format(name)];\n}\n',
      "src/index.ts": 'export { format } from "./core/format.js";\n',
    },
    violations: [
      dependency("src/core/uses-node.ts", exportOf("readFileSync", "node:fs")),
      global(
        "src/core/uses-process.ts",
        "export const id: number = process.pid;\n",
      ),
      dependency(
        "src/core/uses-adapter.ts",
        exportOf("save", "../adapters/node/index.js"),
      ),
      dependency(
        "src/adapters/memory/uses-other-adapter.ts",
        exportOf("save", "../node/index.js"),
      ),
      { ...stray, path: "src/adapters/loose.ts" },
      stray,
    ],
    cycle: {
      "src/core/format.ts":
        'import { greet } from "./greet.js";\nexport function format(name: string): string {\n  return greet + name;\n}\n',
      "src/core/greet.ts":
        'import { format } from "./format.js";\nexport const greet = format.name.length > 99 ? "" : "Hello, ";\n',
    },
    entryViolation: dependency(
      "src/index.ts",
      'export { format } from "./core/format.js";\nexport { save } from "./adapters/node/index.js";\n',
    ),
  },
  {
    leaf: "ts-library",
    option: "multi-entry",
    heading: "機能別の複数入口",
    files: {
      "src/shared/text.ts":
        "export function trim(value: string): string {\n  return value.trim();\n}\n",
      "src/features/parse/split.ts":
        'import { trim } from "../../shared/text.js";\nexport function split(value: string): string[] {\n  return value.split(",").map(trim);\n}\n',
      "src/features/parse/index.ts": 'export { split } from "./split.js";\n',
      "src/features/format/index.ts":
        'export function join(values: readonly string[]): string {\n  return values.join(", ");\n}\n',
      "src/index.ts":
        'export { join } from "./features/format/index.js";\nexport { split } from "./features/parse/index.js";\n',
    },
    violations: [
      dependency(
        "src/features/format/uses-other-feature.ts",
        exportOf("split", "../parse/index.js"),
      ),
      dependency(
        "src/shared/uses-feature.ts",
        exportOf("split", "../features/parse/index.js"),
      ),
      stray,
    ],
    cycle: {
      "src/features/parse/split.ts":
        'import { trim } from "../../shared/text.js";\nimport { separator } from "./separator.js";\nexport function split(value: string): string[] {\n  return value.split(separator()).map(trim);\n}\n',
      "src/features/parse/separator.ts":
        'import { split } from "./split.js";\nexport function separator(): string {\n  return split.length > 9 ? ";" : ",";\n}\n',
    },
    entryViolation: dependency(
      "src/index.ts",
      'export { split } from "./features/parse/split.js";\n',
    ),
  },
];
