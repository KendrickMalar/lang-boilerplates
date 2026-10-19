import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";
import globals from "globals";
import prettier from "eslint-config-prettier";
import vitest from "@vitest/eslint-plugin";
import n from "eslint-plugin-n";
import regexp from "eslint-plugin-regexp";

export function createConfig({
  environment,
  testFiles = ["tests/**/*.test.ts"],
}) {
  if (environment !== "node" && environment !== "browser") {
    throw new Error("Choose node or browser for the ESLint environment.");
  }
  const sourceFiles = ["**/*.{js,mjs,cjs,ts,tsx}"];
  const nodeFiles = [
    "*.config.{js,mjs,cjs,ts,tsx}",
    "tests/**/*.{js,mjs,cjs,ts,tsx}",
    "src/**/*.{test,spec}.{js,mjs,cjs,ts,tsx}",
    "src/**/__tests__/**/*.{js,mjs,cjs,ts,tsx}",
  ];
  const browserOnly = Object.keys(globals.browser).filter(
    (name) => !(name in globals.node),
  );
  return defineConfig(
    {
      ignores: [
        "node_modules/**",
        "dist/**",
        "coverage/**",
        ".husky/_/**",
        "test-results/**",
        "playwright-report/**",
        ".playwright/**",
      ],
    },
    { linterOptions: { reportUnusedDisableDirectives: "error" } },
    {
      files: ["**/*.{js,mjs,cjs}"],
      extends: [js.configs.recommended],
    },
    {
      files: ["**/*.{ts,tsx}"],
      extends: [
        js.configs.recommended,
        tseslint.configs.strictTypeChecked,
        tseslint.configs.stylisticTypeChecked,
      ],
      languageOptions: {
        parserOptions: { projectService: true, tsconfigRootDir: process.cwd() },
      },
      rules: {
        "@typescript-eslint/no-explicit-any": "error",
        "@typescript-eslint/no-floating-promises": "error",
        "@typescript-eslint/consistent-type-imports": [
          "error",
          { prefer: "type-imports", disallowTypeAnnotations: true },
        ],
      },
    },
    {
      files: sourceFiles,
      plugins: { regexp },
      rules: regexp.configs["flat/recommended"].rules,
    },
    {
      files: ["**/*.{js,mjs,cjs}"],
      ignores: ["src/**"],
      languageOptions: { globals: globals.node },
    },
    {
      files: ["src/**/*.{js,mjs,cjs,ts,tsx}"],
      ignores: nodeFiles,
      languageOptions: {
        globals: environment === "browser" ? globals.browser : globals.node,
      },
    },
    {
      files: nodeFiles,
      languageOptions: { globals: globals.node },
      rules: {
        "no-restricted-globals": [
          "error",
          { globals: browserOnly, checkGlobalObject: true },
        ],
      },
    },
    {
      files: environment === "node" ? sourceFiles : nodeFiles,
      plugins: { n },
      rules: {
        "n/no-unsupported-features/node-builtins": [
          "error",
          { allowExperimental: false },
        ],
      },
    },
    {
      files: testFiles,
      plugins: vitest.configs.recommended.plugins,
      rules: {
        ...vitest.configs.recommended.rules,
        "vitest/no-focused-tests": ["error", { fixable: false }],
        "vitest/no-disabled-tests": "error",
      },
    },
    prettier,
  );
}
