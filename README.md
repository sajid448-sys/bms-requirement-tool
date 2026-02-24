# BMS Requirement Snippet Tool

Takes mission inputs (orbital period, eclipse duration, average payload power, nominal battery voltage) and spits out **BMS (Battery Management System)** requirement snippets. You get required usable capacity, average C-rate during eclipse, and a SOC operating window for two mission types: short-lived high-power (e.g. LEO) and long-lived low-power (e.g. GEO). Output is Markdown or JSON so you can drop it into docs or feed it to other tools.

Background reading: [NASA BMS (MSC-TOPS-40)](https://technology.nasa.gov/patent/MSC-TOPS-40), [Aerospace TOR-2013-00295](https://aerospace.org/sites/default/files/maiw/TOR-2013-00295.pdf) (Li-ion power subsystem architectures).

---

## How to run

From the `bms_requirement_tool/` directory.

**CLI (no install):**

```powershell
python bms_calculator.py --period 90 --eclipse 35 --power 200 --voltage 28
```

Optional: add `--format both` or `--format json` or `--format md` (default is both). Add `--out ./snippets` to write `.json` and `.md` files into that folder.

- `--period` / `--eclipse` — orbital period and eclipse duration (minutes)
- `--power` — average payload power (W), `--voltage` — nominal battery voltage (V)
- `--format` — `both`, `json`, or `md`
- `--out` — optional; writes `.json` and `.md` per case into that folder

**Web UI:**

From the repo folder you can either run Docker yourself or use the helper script:

- **Option A — Double-click (Windows):** Run **`start-bms-tool-web.bat`**. It builds the image, starts the app in the background (`docker compose up -d`), waits a few seconds, then opens http://localhost:5000 in your browser. To stop the server later, run `docker compose down` in the same folder.
- **Option B — Manual:** Run `docker compose build`, then `docker compose up`, then open http://localhost:5000 yourself.

Open http://localhost:5000. There’s an **Advanced** section at the bottom (toggle to open it). That part does the extra sizing (pack loss, cell divergence, N+1, ageing/temp derating, anomaly reserve), cell-level stuff (cell count, string config, pack capacity), and charge/discharge limits with the REQ-BMS-001 … 007 requirements. It’s all driven by `POST /api/advanced` and `adv_calculator.compute_advanced()` in Python.

---

## What’s in the repo

- **bms_calculator.py** — Main logic: eclipse energy, usable capacity, C-rate, SOC window for the two mission cases. Has a CLI and `calculate_api()` used by the server.
- **adv_calculator.py** — The “advanced” chain: sizing terms, cell-level outputs, charge/discharge limits, named requirements. Entry point is `compute_advanced()`. Used by the server for `/api/advanced`; you can also call it from scripts.
- **server.py** — Flask: serves the page, `POST /api/calculate` (bms_calculator), `POST /api/advanced` (adv_calculator).
- **index.html** — The web form and results (including the Advanced panel).
- **Dockerfile** + **docker-compose.yml** — For running the app in Docker.
- **start-bms-tool-web.bat** — Windows helper: builds with Docker Compose, starts the web app in the background, and opens the browser at http://localhost:5000.

---

## Quick check that it works

**CLI:** Run the command above with 90 / 35 / 200 / 28. You should see short-lived ≈ 128.33 Wh (4.58 Ah), 1.558 C, SOC 20–100%, and long-lived 140 Wh (5 Ah), 1.429 C, SOC 30–90%.

**Web:** Same numbers when you plug 90, 35, 200, 28 into the form. Download .md / .json and confirm the files look right.

**API:** With the app up (Docker or `python server.py`):

```powershell
Invoke-RestMethod -Uri http://localhost:5000/api/calculate -Method POST -ContentType "application/json" -Body '{"period":90,"eclipse":35,"power":200,"voltage":28}'
```

You should get `short` and `long` with those capacities and `snippet_md`.

---

## Tech notes

### Choice of language

**Python 3** was chosen so the requirement logic stays readable and auditable: formulas and margins are in one place, and reviewers can follow the math without fighting the language. The standard library covers what we need: `dataclasses` for inputs and outputs, `json` for snippets, `argparse` for the CLI. The core calculator and CLI have **no external dependencies**, so they run in any environment (CI, command line, or a minimal container) without a heavy stack. Flask is only used for the web server. This keeps the “requirement engine” separate from delivery, so we can later add YAML/TOML configs, a template engine, or other tooling without rewriting the core.

### Data structures

Inputs, configuration, and outputs are split into clear types so the same logic is reused from CLI, server, and tests, and so traceability is obvious.

- **MissionInputs** — The four user inputs: orbital period (min), eclipse duration (min), average payload power (W), nominal battery voltage (V). Nothing derived, just what the user provides.
- **MissionCaseConfig** — Defines one mission class (e.g. short-lived vs long-lived): name, description, capacity margin, SOC min at end of eclipse, SOC max at end of charge, reserve fraction. The two built-in cases encode different margins and SOC windows (e.g. 20–100% vs 30–90%) so we don’t hardcode mission policy inside the formulas.
- **BMSRequirementSnippet** — The result for one case: echoed inputs, required usable capacity (Wh and Ah), average C-rate during eclipse, SOC operating window (min/max/min at end of eclipse), margin/reserve summary, and the preformatted `snippet_md` and `snippet_json`. Everything needed for a single requirement snippet lives in one structure.

On the advanced side, `adv_calculator` works over plain dicts and a single entry point `compute_advanced()` that returns `sizing_summary`, `cell_level`, `charge_discharge_limits`, and `named_requirements`. That keeps the “mission-level” calculator and the “pack/cell-level” calculator independent: the server (or a future script) can feed a base capacity into the advanced chain without the two modules depending on each other.

**Formulas (core):** Eclipse energy = P × (eclipse_min / 60). Required usable capacity = that × capacity_margin (per case). Ah = Wh / V_nom. C-rate = (P / V_nom) / C_Ah. SOC limits are read from the case config so they stay consistent with guidance (e.g. min SOC at end of eclipse, reduced top SOC for long life).

### Extending to a more detailed requirement generator

The current layout is already set up for extension without turning the tool into a monolith.

1. **Config-driven cases** — Move mission cases out of code into YAML or JSON (margins, SOC limits, reserve, mission class names). Add schema validation (e.g. Pydantic or jsonschema) so new or edited cases don’t break the pipeline. The existing `MissionCaseConfig` and `BMSRequirementSnippet` stay the same; only the source of config changes.
2. **Sizing and limits** — The “more detailed” sizing (pack loss, divergence, redundancy, ageing/temp, anomaly reserve), cell-level outputs, and charge/discharge limits (including REQ-BMS-001 … 007) are already in `adv_calculator.py` and exposed via the UI and `/api/advanced`. To go further, add more terms as small functions and feed a single sizing summary so traceability stays clear.
3. **Templates and stable IDs** — Use a template engine (e.g. Jinja2) or structured blocks to generate requirement text. Store snippets as structured records (e.g. `id`, `title`, `body`, `rationale`, `source_equation`) so each requirement has a stable ID and can be traced back to the formula or config that produced it.
4. **Verification** — Attach a “verified_by” (test procedure ID or analysis ID) to each derived requirement. Optionally generate stub verification tables (CSV or Markdown) for test planning so the same data drives both the requirement text and the verification matrix.
5. **Export** — Add export to Word (e.g. python-docx), ReqIF, or a simple HTML report so the same data drives machine-readable (JSON) and human-readable documents.

Keeping **inputs → config → derived values → snippets** in separate layers (as in `bms_calculator.py` and `adv_calculator.py`) means each of these extensions can be added in one place without duplicating the core math.
