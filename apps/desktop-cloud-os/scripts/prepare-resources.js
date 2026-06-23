const fs = require("fs");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const appsRoot = path.resolve(projectRoot, "..");
const repoRoot = path.resolve(appsRoot, "..");
const outputRoot = path.join(projectRoot, "build-resources");

const ignoredNames = new Set([
  ".git",
  ".pytest_cache",
  "__pycache__",
  "node_modules",
  "dist",
  ".venv",
  "venv",
  "work"
]);

const ignoredFiles = new Set([
  "server.log",
  "server.err.log",
  "license-cache.json"
]);

function shouldSkip(sourcePath) {
  const name = path.basename(sourcePath);
  if (ignoredNames.has(name)) return true;
  if (ignoredFiles.has(name)) return true;
  if (name.endsWith(".pyc") || name.endsWith(".tmp")) return true;
  return false;
}

function copyTree(source, target) {
  if (shouldSkip(source)) return;
  const stat = fs.statSync(source);
  if (stat.isDirectory()) {
    fs.mkdirSync(target, { recursive: true });
    for (const entry of fs.readdirSync(source)) {
      copyTree(path.join(source, entry), path.join(target, entry));
    }
    return;
  }
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(source, target);
}

fs.rmSync(outputRoot, { recursive: true, force: true });
fs.mkdirSync(outputRoot, { recursive: true });

copyTree(path.join(appsRoot, "decision-hub"), path.join(outputRoot, "decision-hub"));
copyTree(path.join(repoRoot, "backend"), path.join(outputRoot, "backend"));

console.log(`Prepared desktop resources at ${outputRoot}`);
