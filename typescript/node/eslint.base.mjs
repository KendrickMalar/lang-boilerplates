import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";
import globals from "globals";
import prettier from "eslint-config-prettier";

export function createConfig({ environment }) {
  if (environment !== "node" && environment !== "browser") {
    throw new Error("Choose node or browser for the ESLint environment.");
  }
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
    { ignores: ["node_modules/**", "dist/**", "coverage/**", ".husky/_/**"] },
    {
      files: ["**/*.{js,mjs,cjs}"],
      extends: [js.configs.recommended],
    },
    {
      files: ["**/*.{ts,tsx}"],
      extends: [
        js.configs.recommended,
        tseslint.configs.recommendedTypeChecked,
      ],
      languageOptions: {
        parserOptions: { projectService: true, tsconfigRootDir: process.cwd() },
      },
      rules: {
        "@typescript-eslint/no-explicit-any": "error",
        "@typescript-eslint/no-floating-promises": "error",
      },
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
    prettier,
  );
}
