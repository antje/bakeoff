/**
 * Structural lint for the bakeoff skills.
 *
 *   node scripts/check-skills.mjs
 *
 * A skill's description is the entire retrieval surface: it is all the model
 * sees when deciding whether to load the file. Everything below the frontmatter
 * only matters if the description got the skill invoked in the first place, so
 * the description rules are the strict ones.
 *
 * Exemptions require an entry in EXEMPT below, with a written reason. A skill
 * cannot exempt itself from frontmatter, because then every skill would.
 *
 * Adapted from product-coach (github.com/antje/product-coach).
 */
import { readdirSync, readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const SKILLS_DIR = new URL('../skills/', import.meta.url).pathname

/** skill -> { sections: [...], why } */
const EXEMPT = {}

const REQUIRED_SECTIONS = [
  '## When to use',
  '## Stage gate',
  '## Common rationalizations',
  '## Red flags',
  '## Verification',
  '## Output contract',
]

/**
 * Verbs that mean the description is narrating the method. A description that
 * summarises the process invites the agent to follow the summary instead of
 * loading the skill, which silently skips the refusals.
 */
const PROCESS_VERBS =
  /\b(selects|walks|traces|screens|scores|audits|forces|translates|fits|identifies|structures|drafts|prepares|maps|runs the|applies the|picks the)\b/i

/**
 * Lints every skill directory under `dir` and returns what it found. Taking the
 * directory as an argument is what makes the linter itself testable: the test
 * points it at fixtures that are deliberately broken.
 */
export function lintSkills(dir = SKILLS_DIR) {
const errors = []
const warnings = []
const skills = readdirSync(dir, { withFileTypes: true })
  .filter((d) => d.isDirectory())
  .map((d) => d.name)
  .sort()

/** skill -> { gates: Set, writes: Set } */
const graph = {}

for (const name of skills) {
  const file = join(dir, name, 'SKILL.md')
  const fail = (msg) => errors.push(`${name}: ${msg}`)
  const warn = (msg) => warnings.push(`${name}: ${msg}`)

  if (!existsSync(file)) {
    fail('has no SKILL.md')
    continue
  }
  const text = readFileSync(file, 'utf8')
  const exempt = EXEMPT[name]?.sections ?? []

  // --- frontmatter -------------------------------------------------------
  const fm = text.match(/^---\n([\s\S]*?)\n---\n/)
  if (!fm) {
    fail('has no frontmatter')
    continue
  }
  const nameField = fm[1].match(/^name:\s*(.+)$/m)?.[1]?.trim()
  if (nameField !== name) fail(`frontmatter name "${nameField}" does not match directory`)

  const desc = fm[1].match(/^description:\s*([\s\S]*?)(?=\n[a-z-]+:|$)/m)?.[1]
  if (!desc) {
    fail('has no description')
    continue
  }
  const d = desc.replace(/\s+/g, ' ').trim()

  if (d.length > 1024) fail(`description is ${d.length} chars, over the 1024 limit`)

  const triggers = (d.match(/\bUse (when|after|before)\b/g) ?? []).length
  if (triggers === 0) fail('description has no "Use when" trigger')
  else if (triggers < 2) fail(`description has ${triggers} "Use when" sentence, needs 2 or more so different phrasings can land`)

  // Only the text before the first trigger should describe what it does.
  const preamble = d.split(/\bUse (?:when|after|before)\b/)[0]
  if (PROCESS_VERBS.test(preamble)) {
    fail(`description narrates the method ("${preamble.match(PROCESS_VERBS)[0]}"), so the agent may follow the summary instead of loading the skill`)
  }

  if (/\b(do not|don't|never) use\b/i.test(d)) {
    fail('description contains a negative trigger, and those belong in the "When not to use" part of the body')
  }

  // --- body --------------------------------------------------------------
  if (!/^# \/[a-z-]+, your /m.test(text)) warn('H1 is not the "# /name, your <role>" form')
  if (!/\*\*What you refuse to do:\*\*/.test(text)) fail('has no "What you refuse to do" line')
  if (!/\*\*When not to use:?\*\*/i.test(text)) fail('has no "When not to use" guidance in the body')

  for (const section of REQUIRED_SECTIONS) {
    if (exempt.includes(section)) continue
    if (!text.includes(`\n${section}`)) fail(`missing required section "${section}"`)
  }

  if (text.includes('—')) fail('contains an em dash')

  // Verification must be checkboxes carrying evidence, not prose.
  const verification = text.split('\n## Verification')[1]?.split('\n## ')[0] ?? ''
  if (verification && !verification.includes('- [ ]')) {
    fail('Verification section has no checkboxes')
  }

  // Rationalizations must be a table of excuse against reality.
  if (!exempt.includes('## Common rationalizations')) {
    const rats = text.split('\n## Common rationalizations')[1]?.split('\n## ')[0] ?? ''
    const rows = (rats.match(/^\|.*\|.*\|$/gm) ?? []).length
    if (rows < 5) fail(`Common rationalizations has ${Math.max(0, rows - 2)} rows, wants at least 3`)
  }

  // --- the chain graph ---------------------------------------------------
  // Artifacts live under bench/ here (product/ kept so shared fixtures still lint).
  const paths = (s) => new Set((s ?? '').match(/(?:bench|product)\/[\w./-]+\.md/g) ?? [])
  graph[name] = {
    gates: paths(text.split('\n## Stage gate')[1]?.split('\n## ')[0]),
    writes: paths(text.split('\n## Output contract')[1]?.split('\n## ')[0]),
  }
}

// Every artifact a gate depends on must be written by some skill's contract.
const written = new Set(Object.values(graph).flatMap((g) => [...g.writes]))
for (const [name, g] of Object.entries(graph)) {
  for (const p of g.gates) {
    if (!written.has(p)) errors.push(`${name}: stage gate needs ${p}, which no skill's output contract writes`)
  }
}

return { skills, errors, warnings }
}

// --- report ---------------------------------------------------------------
// Only when run directly, so importing this from a test prints nothing and
// exits nothing.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const { skills, errors, warnings } = lintSkills()
  console.log(`checked ${skills.length} skills`)
  for (const w of warnings) console.log(`  warn  ${w}`)
  for (const e of errors) console.log(`  FAIL  ${e}`)
  console.log(
    errors.length === 0
      ? `\nall ${skills.length} pass`
      : `\n${errors.length} problem(s) across ${new Set(errors.map((e) => e.split(':')[0])).size} skill(s)`
  )
  process.exit(errors.length === 0 ? 0 : 1)
}
