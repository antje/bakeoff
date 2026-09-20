/**
 * Tests for the skill linter.
 *
 *   node --test scripts/check-skills-test.mjs
 *
 * A linter nobody tests is a linter that quietly stops checking. Each case here
 * takes a skill that passes, breaks exactly one thing, and asserts the linter
 * notices. If a rule is ever weakened by accident, one of these goes red.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { lintSkills } from './check-skills.mjs'

/** A skill that passes every rule. Each test mutates one thing about it. */
const GOOD = `---
name: sample
description: Turns a question into a decision. Use when a decision is due and nobody has written it down. Use when two people disagree about what was decided. Triggers on "what did we decide", "who owns this".
---

# /sample, your sample coach

You do the thing.

**What you refuse to do:** accept a decision with no owner.

## When to use

- A decision is due

**When not to use:**

- There is no decision yet

## Stage gate

Requires nothing. Writes \`bench/sample.md\`.

## 1. Do the thing

Do it.

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "We all know who owns it" | Then writing it down costs nothing. |
| "We will decide later" | Later is after the cost is sunk. |
| "It is obvious" | Then it is quick to write. |

## Red flags

- No owner named

## Verification

- [ ] The decision has an owner

## Output contract

Writes \`bench/sample.md\`.
`

/** Writes a one-skill tree and lints it. `edit` mutates the SKILL.md text. */
function lintOne(edit = (s) => s, name = 'sample') {
  const dir = mkdtempSync(join(tmpdir(), 'skills-'))
  try {
    mkdirSync(join(dir, name))
    writeFileSync(join(dir, name, 'SKILL.md'), edit(GOOD))
    return lintSkills(dir)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

const failedOn = (result, fragment) => result.errors.some((e) => e.includes(fragment))

test('a well-formed skill passes', () => {
  const { errors, warnings } = lintOne()
  assert.deepEqual(errors, [], errors.join('\n'))
  assert.deepEqual(warnings, [], warnings.join('\n'))
})

test('catches a missing SKILL.md', () => {
  const dir = mkdtempSync(join(tmpdir(), 'skills-'))
  mkdirSync(join(dir, 'empty'))
  const { errors } = lintSkills(dir)
  rmSync(dir, { recursive: true, force: true })
  assert.ok(errors.some((e) => e.includes('has no SKILL.md')))
})

test('catches a frontmatter name that does not match the directory', () => {
  const r = lintOne((s) => s.replace('name: sample', 'name: something-else'))
  assert.ok(failedOn(r, 'does not match directory'))
})

test('catches a description with only one trigger sentence', () => {
  const r = lintOne((s) =>
    s.replace(' Use when two people disagree about what was decided.', '')
  )
  assert.ok(failedOn(r, 'needs 2 or more'))
})

test('catches a description that narrates the method', () => {
  const r = lintOne((s) => s.replace('Turns a question into', 'Walks the four steps and scores'))
  assert.ok(failedOn(r, 'narrates the method'))
})

test('allows a process verb after the trigger clause, where it is prose not a summary', () => {
  const r = lintOne((s) =>
    s.replace('Triggers on', 'Use when someone scores a backlog. Triggers on')
  )
  assert.deepEqual(r.errors, [], r.errors.join('\n'))
})

test('catches a negative trigger in the description', () => {
  const r = lintOne((s) =>
    s.replace('Triggers on', 'Do not use when the decision is reversible. Triggers on')
  )
  assert.ok(failedOn(r, 'negative trigger'))
})

test('catches a description over the 1024 char limit', () => {
  const r = lintOne((s) => s.replace('Turns a question into a decision.', 'x'.repeat(1100) + '.'))
  assert.ok(failedOn(r, 'over the 1024 limit'))
})

test('catches a missing refusal line', () => {
  const r = lintOne((s) => s.replace('**What you refuse to do:**', 'What you avoid:'))
  assert.ok(failedOn(r, 'no "What you refuse to do" line'))
})

test('catches missing "When not to use" guidance in the body', () => {
  const r = lintOne((s) => s.replace('**When not to use:**', '**Also:**'))
  assert.ok(failedOn(r, 'no "When not to use" guidance'))
})

for (const section of [
  '## When to use',
  '## Stage gate',
  '## Common rationalizations',
  '## Red flags',
  '## Verification',
  '## Output contract',
]) {
  test(`catches a missing "${section}"`, () => {
    const r = lintOne((s) => s.replace(`\n${section}\n`, '\n## Renamed\n'))
    assert.ok(failedOn(r, `missing required section "${section}"`))
  })
}

test('catches an em dash', () => {
  const r = lintOne((s) => s.replace('Do it.', 'Do it — carefully.'))
  assert.ok(failedOn(r, 'contains an em dash'))
})

test('catches a Verification section written as prose', () => {
  const r = lintOne((s) =>
    s.replace('- [ ] The decision has an owner', 'Make sure the decision has an owner.')
  )
  assert.ok(failedOn(r, 'Verification section has no checkboxes'))
})

test('catches a rationalizations table with too few rows', () => {
  const r = lintOne((s) => s.replace('| "It is obvious" | Then it is quick to write. |\n', ''))
  assert.ok(failedOn(r, 'wants at least 3'))
})

test('catches a stage gate needing an artifact no output contract writes', () => {
  const r = lintOne((s) =>
    s.replace(
      'Requires nothing. Writes `bench/sample.md`.',
      'Requires `bench/missing.md`. Writes `bench/sample.md`.'
    )
  )
  assert.ok(failedOn(r, 'which no skill'))
})

test('warns, without failing, on a non-standard H1', () => {
  const r = lintOne((s) => s.replace('# /sample, your sample coach', '# Sample'))
  assert.deepEqual(r.errors, [], r.errors.join('\n'))
  assert.ok(r.warnings.some((w) => w.includes('H1 is not')))
})
