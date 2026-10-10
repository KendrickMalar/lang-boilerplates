export default {
  "*.{js,mjs,cjs,ts,tsx}": ["prettier --write", "eslint --max-warnings 0"],
  "*.{json,md,yml,yaml,css,html}": ["prettier --write"],
};
