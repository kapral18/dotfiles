import { execFileSync } from "node:child_process";
import { closeSync, existsSync, openSync, readdirSync, readFileSync, readSync, realpathSync } from "node:fs";
import { createRequire } from "node:module";
import { homedir } from "node:os";
import { join, relative } from "node:path";

const links = join(homedir(), ".local/share/pnpm-global-links/node_modules");
const mason = join(homedir(), ".local/share/nvim/mason/packages");
const semver = createRequire(join(links, "index.js"))("semver");

const mise = (...args) => execFileSync("mise", args, { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] });

const requested = new Map(process.argv.slice(2).map((arg) => arg.split("@")));
const outdated = JSON.parse(mise("outdated", "--global", "--bump", "--json", ...requested.keys()) || "{}");
// Held and multi-version tools never reach `mise upgrade --bump`; ,mise-bump passes them here.
for (const tool of (process.env.MISE_BUMP_EXCLUDE ?? "").split(/\s+/).filter(Boolean)) delete outdated[tool];
const unchecked = Object.keys(outdated).filter((tool) => !["node", "bun"].includes(tool));
if (!Object.keys(outdated).length) console.log("No outdated global mise tools to check");
for (const tool of requested.keys()) {
  if (["node", "bun"].includes(tool) && !outdated[tool]) console.log(`${tool}: not outdated; impact not checked`);
}
for (const tool of ["node", "bun"]) {
  if (outdated[tool] && !semver.valid(outdated[tool].current)) {
    console.log(`${tool}: no installed version; impact not checked`);
  }
}
const reportUnchecked = () => {
  if (unchecked.length) console.log(`Dependents not checked for: ${unchecked.join(", ")}`);
};
if (!["node", "bun"].some((tool) => semver.valid(outdated[tool]?.current))) {
  reportUnchecked();
  process.exit(0);
}

// The ABI of the global node being upgraded; the node running this script may be a project's.
const nodeAbi = semver.valid(outdated.node?.current)
  ? mise("exec", `node@${outdated.node.current}`, "--", "node", "-p", "process.versions.modules").trim()
  : null;

// A path reached only through node_modules/<name> segments (pnpm adds .pnpm/<id>/) is installed;
// a node_modules under any other directory, such as test fixtures, is not.
const installedPrefix = "(node_modules\\/(\\.pnpm\\/[^/]+\\/node_modules\\/)?(@[^/]+\\/)?[^/.@][^/]*\\/)";
const installedPackage = new RegExp(`^${installedPrefix}+package\\.json$`);
const installedAddon = new RegExp(`^${installedPrefix}+.*\\.node$`);

// Walks real directories only; pnpm's node_modules symlinks point into .pnpm, which is walked directly.
function* walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(path);
    else if (entry.isFile()) yield path;
  }
}

const machoCpu = { arm64: 0x0100000c, x64: 0x01000007 }[process.arch];
const elfMachine = { arm64: 0xb7, x64: 0x3e }[process.arch];

// Thin Mach-O or ELF files for another CPU, and other formats, never load on this host.
function loadsHere(addon) {
  const fd = openSync(addon, "r");
  const head = Buffer.alloc(20);
  readSync(fd, head, 0, 20, 0);
  closeSync(fd);
  const magic = head.toString("hex", 0, 4);
  if (process.platform === "darwin") {
    return magic === "cafebabe" || (magic === "cffaedfe" && head.readUInt32LE(4) === machoCpu);
  }
  return process.platform === "linux" && magic === "7f454c46" && head.readUInt16LE(18) === elfMachine;
}

// Node-API addons (napi_register_module_v1, or napi_module_register in old builds) load on every Node major.
// Classic addons register through node_module_register (NODE_MODULE) or node_register_module_v<ABI>
// (NODE_MODULE_INIT) and load only on the Node ABI they were built for. Prebuilds for another ABI
// (node_register_module_v<N> or *.abi<N>.node) are not the copy the global node loads.
function abiBound(addon) {
  if (!loadsHere(addon)) return false;
  const named = addon.match(/\.abi(\d+)\.node$/)?.[1];
  if (named && named !== nodeAbi) return false;
  const symbols = execFileSync("nm", ["-g", addon], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  if (/napi_register_module_v1|napi_module_register/.test(symbols)) return false;
  const exported = symbols.match(/node_register_module_v(\d+)/)?.[1];
  if (exported) return exported === nodeAbi;
  return /node_module_register/.test(symbols);
}

// Tools that run on mise's node: pnpm globals (one install root each) and Mason's npm packages.
// A global linked from a source checkout counts only through its own package.json; its
// node_modules holds dev dependencies that never ship.
function dependentRoots() {
  const roots = [];
  for (const entry of readdirSync(links).filter((name) => !name.startsWith("."))) {
    const owners = entry.startsWith("@") ? readdirSync(join(links, entry)).map((name) => `${entry}/${name}`) : [entry];
    for (const owner of owners) {
      const dir = realpathSync(join(links, owner));
      const cut = dir.indexOf("/node_modules/");
      roots.push(cut < 0 ? { owner, root: dir, linked: true } : { owner, root: dir.slice(0, cut) });
    }
  }
  if (existsSync(mason)) {
    for (const name of readdirSync(mason)) {
      if (existsSync(join(mason, name, "node_modules"))) roots.push({ owner: `mason:${name}`, root: join(mason, name) });
    }
  }
  return roots;
}

const engines = { node: new Map(), bun: new Map() };
const abiBoundAddons = new Set();
const scanned = new Set();

function addEngines(file, owner) {
  let manifest;
  try {
    manifest = JSON.parse(readFileSync(file, "utf8"));
  } catch {
    return;
  }
  scanned.add(`${manifest.name}@${manifest.version}`);
  for (const [tool, ranges] of Object.entries(engines)) {
    const range = manifest.engines?.[tool];
    if (typeof range !== "string" || !semver.validRange(range)) continue;
    const users = ranges.get(range) ?? new Set();
    users.add(`${manifest.name}@${manifest.version} (via ${owner})`);
    ranges.set(range, users);
  }
}

for (const { owner, root, linked } of dependentRoots()) {
  if (linked) {
    addEngines(join(root, "package.json"), owner);
    continue;
  }
  for (const file of walk(root)) {
    const path = relative(root, file);
    if (installedPackage.test(path)) addEngines(file, owner);
    else if (nodeAbi && installedAddon.test(path) && abiBound(file)) abiBoundAddons.add(`${path} (via ${owner})`);
  }
}

function resolve(tool, version) {
  if (semver.valid(version)) return version;
  try {
    return mise("latest", `${tool}@${version}`).trim();
  } catch {
    return "";
  }
}

for (const [tool, info] of Object.entries(outdated)) {
  const ranges = engines[tool];
  if (!ranges) continue;
  const current = semver.valid(info.current);
  if (!current) continue;
  const wanted = requested.get(tool) ?? info.bump ?? info.latest;
  const target = resolve(tool, wanted);
  if (!semver.valid(target)) {
    console.log(`${tool}: mise resolves no release for ${wanted}; impact not checked`);
    continue;
  }
  // Only ranges the current version meets can be broken by the upgrade.
  const held = [...ranges].filter(([range]) => semver.satisfies(current, range));
  const crossesAbi = tool === "node" && abiBoundAddons.size > 0 && semver.major(target) !== semver.major(current);
  const conflicts = held.filter(([range]) => !semver.satisfies(target, range));
  if (!conflicts.length && !crossesAbi) {
    console.log(`${tool} ${current} -> ${target}: no declared conflicts in ${scanned.size} installed packages`);
    continue;
  }

  const fits = (version) =>
    held.every(([range]) => semver.satisfies(version, range)) &&
    !(crossesAbi && semver.major(version) !== semver.major(current));
  const safe = mise("ls-remote", tool)
    .split("\n")
    .filter((v) => semver.valid(v) && !semver.prerelease(v) && semver.gt(v, current) && semver.lte(v, target))
    .sort(semver.compare)
    .filter(fits)
    .at(-1);

  console.log(`${tool} ${current} -> ${target} breaks:`);
  for (const [range, users] of conflicts) {
    for (const user of users) console.log(`  ${user} needs ${tool} "${range}"`);
  }
  if (crossesAbi) {
    for (const addon of abiBoundAddons) console.log(`  ${addon} loads only on Node ${semver.major(current)}`);
  }
  console.log(
    safe
      ? `  highest safe: ${safe} (,mise-bump ${tool}@${safe})`
      : `  no newer version fits every dependent; stay on ${current}`,
  );
}
reportUnchecked();
