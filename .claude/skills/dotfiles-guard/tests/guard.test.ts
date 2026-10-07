import { expect, test } from 'claude-code/testing'

const bash = (command: string) => ({ tool: 'Bash', command, description: 'test' }) as const

test('refuses the reserved checks', async ($, on) => {
  on('tool.call', () => ({ result: {} as never }))
  for (const command of ['make check-full', 'make test', 'make -C . test', 'make -C ${ROOT} test', 'cd x && make -j4 check-full', './bin/check --full', 'CHECK_FULL=1 python3 scripts/check.py --full', 'python3 scripts/test_runner.py', 'uv run scripts/test_runner.py', 'uv run scripts/check.py --full', 'python3 -u scripts/check.py --full']) {
    expect((await $.tool.call(bash(command))).deny, command).toMatch(/reserves make check-full/)
  }
})

test('reads them as commands, not as text', async ($, on) => {
  on('tool.call', () => ({ result: {} as never }))
  for (const command of ['make check', 'git add scripts/test_runner.py', 'git diff -- scripts/test_runner.py', 'rg -n "make test" docs', 'git commit -m "docs: say make test is for the human"', 'bin/check', 'python3 scripts/check.py']) {
    expect((await $.tool.call(bash(command))).deny, command).toBeUndefined()
  }
})
