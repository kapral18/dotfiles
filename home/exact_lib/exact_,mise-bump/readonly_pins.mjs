import { execFileSync } from "node:child_process";
import { openSync, readFileSync, writeFileSync } from "node:fs";
import { createInterface } from "node:readline/promises";
import { ReadStream } from "node:tty";

const [command, config, ...requested] = process.argv.slice(2);
const lines = readFileSync(config, "utf8").split("\n");

// [tools] entries: name, line index, quoted versions on that line, and a hold reason from
// a `# @mise-bump-hold: <reason>` line in the comment block directly above.
function tools() {
  const found = [];
  let inTools = false;
  let comments = [];
  lines.forEach((line, index) => {
    const header = line.match(/^\s*\[([^\]]+)\]\s*(#.*)?$/);
    if (header) {
      const name = header[1].trim();
      inTools = name === "tools";
      if (name.startsWith("tools.")) console.error(`Warning: ,mise-bump does not read [${name}] tables; holds and multi-version pins there are ignored`);
      comments = [];
      return;
    }
    if (!inTools) return;
    if (/^\s*#/.test(line)) {
      comments.push(line);
      return;
    }
    const entry = line.match(/^\s*("?)([^"=\s]+)\1\s*=\s*(.*)$/);
    if (entry) {
      const holdLine = comments.find((c) => /#\s*@mise-bump-hold:/.test(c));
      const hold = holdLine ? holdLine.replace(/^.*@mise-bump-hold:\s*/, "") || "held" : undefined;
      const value = entry[3].trimStart();
      if (value.startsWith("[") && !value.includes("]")) {
        console.error(`Warning: ,mise-bump does not read the multi-line ${entry[2]} pin; write it on one line`);
      }
      const versions = value.startsWith("[") ? [...value.matchAll(/(["'])([^"']+)\1/g)].map((m) => m[2]) : [];
      found.push({ name: entry[2], index, hold, versions });
    }
    comments = [];
  });
  return found;
}

const parse = (version) => (/^\d+(\.\d+)*$/.test(version) ? version.split(".").map(Number) : null);
const newer = (a, b) => {
  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) > (b[i] ?? 0);
  }
  return false;
};

// Held tools and tools pinned to several versions stay out of `mise upgrade --bump`,
// which cannot write a new version into a multi-version pin.
if (command === "excluded") {
  for (const tool of tools()) {
    if (tool.hold) {
      console.error(`Held: ${tool.name} (${tool.hold})`);
      console.log(tool.name);
    } else if (tool.versions.length > 1) {
      console.log(tool.name);
    }
  }
  process.exit(0);
}

// Each version of a multi-version pin is its own series: offer the newest release that
// keeps its major.minor (5.4.7 -> 5.4.9), never a merge into one version.
if (command === "series") {
  const offers = [];
  for (const tool of tools()) {
    if (tool.hold || tool.versions.length < 2) continue;
    if (requested.length && !requested.includes(tool.name)) continue;
    const releases = execFileSync("mise", ["ls-remote", tool.name], { encoding: "utf8" })
      .split("\n")
      .filter((v) => parse(v));
    for (const version of tool.versions) {
      const current = parse(version);
      if (!current) continue;
      const series = current.slice(0, 2).join(".");
      const best = releases
        .filter((v) => v.startsWith(`${series}.`) || v === series)
        .reduce((top, v) => (newer(parse(v), parse(top)) ? v : top), version);
      if (best !== version) offers.push({ tool, version, best });
    }
  }
  if (!offers.length) process.exit(0);

  // A tty stream, not fs.createReadStream: a pending fs read of /dev/tty blocks process exit.
  const tty = new ReadStream(openSync("/dev/tty", "r"));
  const prompt = createInterface({ input: tty, output: process.stderr });
  let closed = false;
  prompt.once("close", () => {
    closed = true;
  });
  // A closed terminal answers "no" to every remaining offer.
  const ask = (question) =>
    closed
      ? Promise.resolve("")
      : new Promise((resolve) => {
          prompt.once("close", () => resolve(""));
          prompt.question(question).then(resolve, () => resolve(""));
        });
  const chosen = [];
  for (const offer of offers) {
    const answer = await ask(`${offer.tool.name} ${offer.version} -> ${offer.best}? [y/N] `);
    if (/^y(es)?$/i.test(answer.trim())) chosen.push(offer);
  }
  prompt.close();
  tty.destroy();

  for (const { tool, version, best } of chosen) {
    execFileSync("mise", ["install", `${tool.name}@${best}`], { stdio: "inherit" });
    lines[tool.index] = lines[tool.index].replace(new RegExp(`(["'])${version.replaceAll(".", "\\.")}\\1`), `$1${best}$1`);
    writeFileSync(config, lines.join("\n"));
  }
  process.exit(0);
}

console.error(`usage: pins.mjs excluded|series <config> [tool...]`);
process.exit(2);
