#!/usr/bin/env node

/**
 * This script is used to annotate the casks and formulas with the links to their homepages.
 *
 * @example
 * $ commentize --inFile /path/to/input/in.yaml --outFile /path/to/output/out.yaml
 *
 */

import fs from "fs";
import child_process from "child_process";
import { promisify } from "util"; // Node.js >= 10.0.0

const args = process.argv.slice(2);
const inFileIdx = args.indexOf("--inFile");
const outFileIdx = args.indexOf("--outFile");

if (inFileIdx === -1 || outFileIdx === -1) {
  console.error(
    "Usage: commentize --inFile <input-file> --outFile <output-file>",
  );

  throw new Error("Invalid arguments");
}

const inFile = args[inFileIdx + 1];
const outFile = args[outFileIdx + 1];

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const exec = promisify(child_process.exec);

async function fetchHomepage(line) {
  const pkg = line.match(/- (.*)$/)[1];
  try {
    const { stdout, stderr } = await exec(
      `brew info ${pkg} --json | jq -r '.[].homepage'`,
    );
    if (stderr) {
      await delay((Math.random() * 1000 * 3) | 0);
      const { stdout, stderr } = await exec(
        `brew info ${pkg} --json=v2 | jq -r '.casks.[].homepage'`,
      );
      if (stderr) {
        console.error(`Error: ${stderr}`);
        return line;
      }
      const padding = line.substr(0, line.indexOf('"'));
      const paddingLength = padding.length;
      return (
        " ".repeat(paddingLength - 2) +
        `# ${stdout.toString().trim()}` +
        "\n" +
        padding +
        pkg
      );
    }
    const padding = line.substr(0, line.indexOf('"'));
    const paddingLength = padding.length;
    return (
      " ".repeat(paddingLength - 2) +
      `# ${stdout.toString().trim()}` +
      "\n" +
      padding +
      pkg
    );
  } catch (err) {
    if (err) {
      console.error(`Error: ${err}`);
      return line;
    }
  }
}
(async () => {
  const fileContent = fs.readFileSync(inFile).toString();
  const lines = fileContent.split("\n");
  const tasks = lines
    .filter((x) => x.trim().startsWith("- "))
    .map((x) => fetchHomepage(x));
  const res = await Promise.all(tasks);
  fs.writeFileSync(
    outFile,
    lines
      .map((x, i) => (x.trim().startsWith("- ") ? res[i] : x))
      .join("\n")
      .trim(),
  );
})();
