// 入口1つ＋internal の循環禁止。`depcruise src --config architecture/single-entry.depcruise.mjs`
/** @type {import("dependency-cruiser").IConfiguration} */
export default {
  forbidden: [
    {
      name: "no-circular",
      comment:
        "src の中で import が循環しています。依存の向きを一方向にしてください。",
      severity: "error",
      from: {},
      to: { circular: true },
    },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    exclude: { path: "\\.(test|spec)\\.[cm]?[jt]sx?$|/__tests__/" },
    tsPreCompilationDeps: true,
    tsConfig: { fileName: "tsconfig.json" },
  },
};
