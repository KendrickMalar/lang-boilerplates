import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";
import globals from "globals";
import prettier from "eslint-config-prettier";

export function createConfig({ environment }) {
  if (environment !== "node" && environment !== "browser") {
    throw new Error("Choose node or browser for the ESLint environment.");
  }
  return defineConfig(
    { ignores: ["node_modules/**", "dist/**", "coverage/**", ".husky/_/**"] },
    {
      files: ["**/*.{js,mjs,cjs}"],
      extends: [js.configs.recommended],
      languageOptions: { globals: globals.node },
    },
    {
      files: ["**/*.{ts,tsx}"],
      extends: [
        js.configs.recommended,
        tseslint.configs.recommendedTypeChecked,
      ],
      languageOptions: {
        globals: environment === "browser" ? globals.browser : globals.node,
        parserOptions: { projectService: true, tsconfigRootDir: process.cwd() },
      },
      rules: {
        "@typescript-eslint/no-explicit-any": "error",
        "@typescript-eslint/no-floating-promises": "error",
      },
    },
    {
      files: ["*.config.ts", "tests/**/*.{ts,tsx}"],
      languageOptions: { globals: globals.node },
    },
    prettier,
  );
}
