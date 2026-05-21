---
name: marp-slides
description: "Trigger: generate slides, presentation, marp, deck, slides from markdown, crear presentación. Convert a slide-delimited markdown file into a professional Marp presentation with validation."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

You are converting a slide-delimited markdown file into a professional Marp presentation and validating the result.

## Activation Contract

Activate when the user wants to:
- Generate a Marp presentation from a markdown file
- Convert `_slides*.md` or similar slide markdown to PDF/PPTX/HTML
- Create a professional deck from existing slide content

Do NOT activate for general markdown editing (use your own judgment).

## Hard Rules

- ALWAYS add Marp frontmatter (theme, paginate, header, footer, size) before the first slide.
- ALWAYS read the full input file before generating.
- ALWAYS run validation after generating. Fix CRITICAL issues immediately. Present WARNING issues to the user.
- NEVER modify the original source markdown — create a NEW file with `_marp` suffix.
- NEVER add/remove/pad slide content unless the user explicitly asks. Preserve their wording and structure.
- ALWAYS use the `energizados` theme from `assets/energizados-theme.css`. Pass it with `--theme`.
- ALWAYS copy any images referenced in the source markdown to the output directory before running Marp.
- The `---` separator inside source markdown already separates slides — do NOT duplicate it.

## Decision Gates

| Need | Action |
|------|--------|
| Source has `## Slide N:` headings per slide | Strip `## Slide N:` prefix from each heading — use the heading text as the slide title |
| Source has a title block before first `---` | Convert to a `<!-- _class: lead -->` title slide |
| Source has tables | Keep tables as-is; ensure column counts are consistent across rows |
| Source has blockquotes | Keep as blockquotes — the CSS styles them elegantly |
| User wants dark-themed slides | Add `<!-- _class: invert -->` to specific slides |
| User wants KPI-focused slides | Add `<!-- _class: kpi -->` to slides with single big metrics |
| Output format not specified | Default to PDF |
| User asks for editable PPTX | Use `--pptx --pptx-editable` |

## Execution Steps

### Step 1: Read and Understand

1. Read the full source markdown file.
2. Identify:
   - Total number of slides (count `---` separators + 1)
   - Whether content has per-slide `## Slide N:` prefixes
   - Tables, blockquotes, lists, and code blocks
   - Any referenced local images

### Step 2: Generate Marp Markdown

Create a new file `{output_dir}/{base_name}_marp.md` with:

1. **Frontmatter** (between `---` delimiters):
```yaml
---
marp: true
theme: energizados
size: 16:9
paginate: true
header: '{Subtitle or project name}'
footer: '{Author or company} | %'
---
```

2. **Title slide**: Convert the first heading into a centered title slide:
```markdown
<!-- _class: lead -->

# {Title}

{Subtitle or date}
```

3. **Content slides**: For each slide section (separated by `---`):
   - If heading has `## Slide N: Title` pattern → strip `Slide N:` prefix, use plain title
   - Add `<!-- _class: invert -->` before closing/Q&A slides
   - Keep all tables, blockquotes, lists, and emphasis as-is

4. **Closing slide**: The last slide with questions/thanks gets:
```markdown
<!-- _class: closing -->

# Gracias

¿Preguntas?
```

### Step 3: Render with Marp CLI

```bash
marp {marp_md} --theme {theme_css} --{format} -o {output_file} --allow-local-files
```

Where:
- `theme_css` = `assets/energizados-theme.css` (relative to this skill)
- `format` = `pdf` (default) | `pptx` | `html`

For PPTX editable: `marp {marp_md} --theme {theme_css} --pptx --pptx-editable -o {output_file} --allow-local-files`

### Step 4: Validate

Run the validation script:

```bash
python {skill_dir}/assets/validate_slides.py {marp_md} --output-dir {output_dir} --format {format}
```

**CRITICAL** issues → fix the markdown and re-render immediately.
**WARNING** issues → show the user and ask if they want to address them.

### Step 5: Report

Tell the user:
1. Output file path
2. Number of slides
3. Validation summary (criticals / warnings / OK)
4. Preview command: `marp {marp_md} --theme {theme_css} --preview`

## Output Contract

Returns:
- Path to generated `_marp.md` file
- Path to rendered PDF/PPTX/HTML file
- Validation results (pass/warn/fail)
- Any CRITICAL issues that were auto-fixed
- Preview command string

## References

- `assets/energizados-theme.css` — custom Marp theme with `lead`, `invert`, `kpi`, `closing` slide classes
- `assets/validate_slides.py` — validation script for structure, frontmatter, content quality, tables, and output file