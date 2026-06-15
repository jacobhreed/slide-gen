# slide-gen

Generate **production-ready slide decks** (LaTeX Beamer → PDF) from your source
documents in a single command, using AI to plan the narrative, write every slide,
design a fitting theme, and optionally generate embedded graphics.

```
slide-gen notes.md report.pdf -o deck.pdf
```

## How it works

slide-gen runs a small multi-stage pipeline for one-shot quality:

1. **Ingest** — read `.txt`, `.md`, `.pdf`, `.docx` (and whole folders) into one corpus.
2. **Plan** — an LLM designs the deck structure and a deck-wide visual style (palette, fonts, motif).
3. **Write** — the LLM expands the plan into full slides: titles, bullets, speaker notes, and a *visual* per slide.
4. **Generate images** *(optional, `--images`)* — abstract decorative accents are produced concurrently.
5. **Render** — slides become a self-contained Beamer `.tex` with a clean, modern, LLM-themed design.
6. **Compile + auto-repair** — compiled to PDF; if LaTeX errors, the source + error log are sent back to the LLM to fix, then recompiled.

### How visuals are chosen (this drives quality)

Factual content is rendered **natively** for accuracy and a clean look — never as an AI image:

- **Metric cards** for headline numbers (revenue, customers, …).
- **Bar charts** (pgfplots) drawn from the real numbers in your source.
- **Timelines** for milestones.

AI image generation (`--images`) is reserved for **abstract, decorative accents only** — textures,
gradients, and shapes that match the deck's palette. Image prompts are guard‑railed to contain no
text, logos, brands, charts, places, or products. This is deliberate: text‑to‑image models can't
render your specific brand or accurate labels and will otherwise hallucinate other companies'
logos and garbled text. So charts, numbers, and anything branded always use native rendering.

## Install

```bash
pip install -e ".[gpt]"        # default provider (OpenAI, for assembly + images)
# or pick what you need:
pip install -e ".[claude]"     # add Anthropic
pip install -e ".[gemini]"     # add Google Gemini
pip install -e ".[all,dev]"    # everything + test deps
```

### System prerequisite: LaTeX

You need a LaTeX distribution providing `pdflatex` (and ideally `latexmk`) on your `PATH`:

- **Windows:** [MiKTeX](https://miktex.org/) or [TeX Live](https://tug.org/texlive/)
- **macOS:** MacTeX (`brew install --cask mactex-no-gui`)
- **Linux:** `sudo apt-get install texlive-latex-recommended texlive-latex-extra latexmk`

slide-gen detects the engine at runtime and prints a clear message if none is found.

## API keys

Set the key for whichever provider(s) you use (or pass the matching `--*-api-key` flag):

| Provider | Env var |
|----------|---------|
| GPT (OpenAI) | `OPENAI_API_KEY` |
| Claude (Anthropic) | `ANTHROPIC_API_KEY` |
| Gemini (Google) | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |

## Usage

```bash
# Default: GPT assembles the deck (gpt-5.5), no images
slide-gen examples/sample_input.md -o deck.pdf

# Add AI-generated graphics (GPT gpt-image-2 by default)
slide-gen examples/sample_input.md -o deck.pdf --images

# Use a different assembly LLM, and pin a specific model name
slide-gen notes/ -o deck.pdf --llm claude --llm-model claude-opus-4-8

# Mix providers: Gemini writes, GPT draws
slide-gen notes/ --images --llm gemini --image-provider gpt

# Steer the content and design
slide-gen brief.docx -o pitch.pdf \
  --audience "investors" --tone "confident" --max-slides 12 \
  --theme-hint "dark, high-contrast, techy"

# Resume an interrupted run (reuses cached plan, content, and images)
slide-gen best-bank/ -o deck.pdf --images --resume -v
```

### Resuming & rate limits

Image generation can hit provider per-minute rate limits (e.g. `gpt-image-2`
allows a handful of images per minute). slide-gen handles this in two ways:

- **It waits out rate limits.** A `429` is treated as transient — the request
  backs off (honoring the provider's "try again in Ns" hint) and retries until
  the window clears, so a large deck just takes a little longer rather than
  losing images. (Genuine errors still fail fast and that one slide is skipped.)
- **`--resume` picks up where you left off.** Plan, written content, and already
  generated images are cached under `.slide-gen-<output-name>/` next to your
  output. Re-running with `--resume` reuses everything that succeeded and only
  redoes what's missing — no repeated planning/writing cost, and only the
  not-yet-generated images are requested.

If a compile fails, the LaTeX `.tex` and error log are preserved (and the error
tail is printed with `-v`) so you can see exactly what happened.

### Key options

| Option | Default | Description |
|--------|---------|-------------|
| `INPUTS...` | — | One or more files or folders (synthesized into one deck). |
| `-o, --output` | `deck.pdf` | Output PDF path. |
| `--llm {gpt,claude,gemini}` | `gpt` | Assembly LLM provider. |
| `--llm-model NAME` | per-provider | Override the exact model (names drift over time). |
| `--images / --no-images` | `--no-images` | Generate and embed AI graphics. |
| `--image-provider {gpt,gemini}` | `gpt` | Image-generation provider. |
| `--image-model NAME` | `gpt-image-2` / `gemini-3-pro-image` | Override the image model. |
| `--max-slides N` | — | Approximate upper bound on slide count. |
| `--audience / --tone / --instructions / --theme-hint` | — | Steer content and design. |
| `--resume` | off | Reuse cached plan/content/images from a prior run and finish what's left. |
| `--keep-tex` | off | Keep the generated `.tex` next to the PDF. |
| `-v, --verbose` | off | Show per-stage progress. |

Defaults live in `slide_gen/config.py` and are all overridable from the CLI.

## Development

```bash
pip install -e ".[all,dev]"
pytest          # runs fully offline (providers + LaTeX are mocked)
```

The model-facing data contract is in `slide_gen/models.py`; providers live under
`slide_gen/llm/` and `slide_gen/images/` behind small registries, so adding a
provider or swapping a default model is a one-line change.
