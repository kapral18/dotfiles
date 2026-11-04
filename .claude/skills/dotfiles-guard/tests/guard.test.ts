import { expect, test } from 'claude-code/testing'

const bash = (command: string) => ({ tool: 'Bash', command, description: 'test' }) as const

test('refuses direct literal reserved checks', async ($, on) => {
  on('tool.call', () => ({ result: {} as never }))
  for (const command of [
    'make check-full',
    'make test',
    'make -C . test',
    'make -C -f test',
    "'make' 'test'",
    'ma\\ke check-full',
    './bin/check --full',
    'python3 scripts/check.py --full',
    'python3 scripts/test_runner.py',
    'uv run scripts/test_runner.py',
    'uv run scripts/check.py --full',
    'python3 -u scripts/check.py --full',
    'timeout 900 make check-full',
    'timeout -k 5 --signal=TERM 600 python3 scripts/test_runner.py',
    'gtimeout -- 600 timeout 500 make test',
    'timeout -vk 5 600 make test',
    'timeout -k5s 600 make test',
    'timeout --kill 5 600 make test',
  ]) {
    expect((await $.tool.call(bash(command))).deny, command).toMatch(/reserves make check-full/)
  }
})

test('reads reserved checks as commands rather than text', async ($, on) => {
  on('tool.call', () => ({ result: {} as never }))
  for (const command of [
    'make check',
    'make -C test check',
    'git add scripts/test_runner.py',
    'git diff -- scripts/test_runner.py',
    'rg -n "make test" docs',
    'git commit -m "docs: say make test is for the human"',
    'bin/check',
    'python3 scripts/check.py',
    'timeout 600 make check',
  ]) {
    expect((await $.tool.call(bash(command))).deny, command).toBeUndefined()
  }
})

test('allows reserved script paths used as Python or uv data arguments', async ($, on) => {
  on('tool.call', () => ({ result: {} as never }))
  for (const command of [
    "python3 -c 'print(1)' scripts/test_runner.py",
    "python3 -c 'print(1)' scripts/check.py --full",
    'uv run echo scripts/test_runner.py',
    'uv run echo scripts/check.py --full',
  ]) {
    expect((await $.tool.call(bash(command))).deny, command).toBeUndefined()
  }
})

test('leaves unsupported shell syntax and wrappers to Bash', async ($, on) => {
  on('tool.call', () => ({ result: {} as never }))
  for (const command of [
    'make check-full && true',
    'make "$TARGET" test',
    'CHECK_FULL=1 make test',
    'make test # human check',
    'make test *.ts',
    'make test {one,two}',
    'make test ~/repo',
    "make test 'unterminated",
    "cat <<'EOF'\nbody\nEOF\nmake check-full",
    'env make check-full',
  ]) {
    expect((await $.tool.call(bash(command))).deny, command).toBeUndefined()
  }
})

test('keeps ordinary quoted and escaped text as arguments', async ($, on) => {
  on('tool.call', () => ({ result: {} as never }))
  for (const command of [
    "printf '%s' 'make test; $HOME *?[{}]~#'",
    'printf "%s" "make test; \\$HOME"',
    'printf make\\ test',
  ]) {
    expect((await $.tool.call(bash(command))).deny, command).toBeUndefined()
  }
})
