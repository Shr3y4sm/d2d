# Demand2Deal — The Autonomous Distributor

Agentic B2B commerce for the **webcmd Hackathon — Agentic Payments Edition**: a
customer RFQ comes in, an AI agent sources live supplier quotes across the open
web, optimizes the supply chain against a spending mandate, collects a real
Razorpay Test Mode payment, re-validates the mandate, and drives the supplier-side
procurement via webcmd browser automation — all with **zero starting inventory**.

> Commerce without inventory.

---

## Table of Contents

1. [About the Project](#about-the-project)
2. [About webcmd](#about-webcmd)
3. [How It Works](#how-it-works)
4. [Demo: One-Day Build & Three-Minute Script](#demo-one-day-build--three-minute-demo-script)
5. [Agent Spending Mandate & Payment Safety](#agent-spending-mandate--payment-safety)
6. [Setup](#setup)
7. [Running the Project](#running-the-project)
8. [Deployment](#deployment)
9. [Authoring a Custom Supplier Adapter](#authoring-a-custom-supplier-adapter)
10. [Honesty Notes & Caveats](#honesty-notes--caveats)
11. [Project Layout](#project-layout)

---

## About the Project

Demand2Deal turns an AI agent from a *shopping assistant* into a *digital
merchant*. Instead of helping a buyer locate a product, it enables a
distributor or SME to **accept demand for products it does not currently stock**
and then dynamically create the supply chain needed to fulfill that demand
profitably.

**One-line proposition:** *A customer asks for an item the business does not
stock. The AI finds supply, constructs a profitable offer, collects payment,
purchases from the optimal supplier, and closes the commercial loop.*

### The commercial problem

Small distributors routinely lose orders when a customer asks for a product,
quantity, or delivery commitment outside current inventory. Carrying a very
broad catalogue ties up working capital and creates inventory-obsolescence
risk. Supplier discovery, price comparison, lead-time checking, margin
calculation, customer quoting, and procurement are usually fragmented across
people and systems.

Demand2Deal reframes agentic payments from *"help me shop"* to
*"help me create and close a profitable trade."*

### The end-to-end commercial loop

```
Customer Demand (RFQ)
  → 1. Requirement parser (Gemini or regex)
  → 2. Supplier adapters & web-wide discovery (webcmd)
  → 3. Commercial optimizer (MOQ, SLA, margin, risk buffer)
  → 4. Customer quote + Razorpay Test Mode payment
  → 5. Spend-policy gate (re-validate everything live)
  → 6. Supplier checkout via webcmd browser automation
  → 7. Audit & margin report
```

### Hero use case

> *"I need 25 Raspberry Pi 5 8GB units delivered in Bengaluru by Monday.
> Budget ₹9,000 each. Minimum margin 8%."*

The agent queries suppliers, rejects the cheapest option because it misses the
delivery SLA, splits the order across two faster suppliers, quotes a price that
preserves margin, collects the customer's payment, re-checks its mandate, and
places the supplier orders — all before the customer's coffee goes cold.

**Money shot:**

| Metric | Value |
|---|---|
| Customer revenue | ₹223,750 |
| Supplier cost | ₹201,300 |
| Gross profit | ₹22,450 (≈10%) |
| Inventory owned before the order | ₹0 |
| Human procurement actions | 0 |

---

## About webcmd

**webcmd** (`@agentrhq/webcmd` on npm) is the orchestrator that lets this app
treat the live web as a programmable surface. It provides both a **CLI** and a
**browser runtime** that other agents and tools can drive. Demand2Deal uses
webcmd for the three moments that make agentic commerce real:

| Capability | webcmd feature | How Demand2Deal uses it |
|---|---|---|
| **Supplier discovery** | Built-in site **adapters** (`amazon-in`, etc.) + generic **browser automation** | Queries live supplier sites for price, stock, MOQ, and lead time. Amazon.in uses the built-in `amazon-in` adapter (deterministic, no LLM round-trip). Sites without a built-in adapter fall back to the generic browser path: `webcmd browser <session> open <url>` → `webcmd browser <session> extract` → Gemini parses the extracted page text. |
| **Web-wide sourcing** | `webcmd browser open` + `extract` against search engines | When no known distributor has stock, the agent searches DuckDuckGo for additional suppliers across the open web, then refines each discovered URL with a live price extraction. |
| **Checkout automation** | `webcmd browser find` / `click` / `fill` + `amazon-in checkout` adapter | Drives the actual supplier checkout flow: open product page → add to cart → navigate to checkout → fill shipping/billing details → submit → capture order confirmation. Amazon uses its dedicated `checkout` adapter; other sites use the generic browser automation path. |

### Adapter vs. generic modes

Every supplier in `SUPPLIER_SOURCES` (see `engine.py`) has a `mode` field:

- **`adapter`** — Uses a built-in webcmd adapter (e.g. `amazon-in`). Fast,
  deterministic, structured JSON output, no LLM parsing. This is the most
  reliable path.
- **`generic`** — Uses a real headless browser session (`webcmd browser ...`)
  plus Gemini to parse the extracted page text into structured data. Works
  on *any* website today but is slower and more dependent on the target
  site's bot-protection.

### Local vs. Cloud browser mode

- **Local mode:** webcmd runs a headless Chromium/Playwright browser locally.
  Requires Chromium to be available to the process (Playwright installs one
  automatically on first launch).
- **Cloud (hosted) mode:** the browser runs on Kernel's hosted infra. Better for
  deployments (Streamlit Cloud, Render, Fly.io, etc.) where bundling Chromium
  inside the container is unreliable. Set up with `webcmd setup`.

### Why webcmd instead of raw Playwright/Selenium?

webcmd provides a unified interface across adapters and the generic browser
path, built-in anti-bot detection helpers, session management, and an
adapter-authoring flow that turns a real browser into a reusable, structured
CLI command. It collapses "open page → find element → extract text → parse with
LLM → click → fill" into a few invocations, which is exactly what an
agent-driven procurement flow needs.

---

## How It Works

The system is implemented across four modules:

- **`app.py`** — Streamlit UI and state machine. Walks the user through the
  five-stage commercial loop (input → discover → optimize → pay → procure) and
  renders the "money shot" transaction summary.
- **`engine.py`** — The agent backend: RFQ parsing, supplier sourcing (adapters
  + web-wide discovery), the commercial optimizer, the pre-payment mandate
  re-check, and the webcmd-driven checkout automation.
- **`payments.py`** — Real Razorpay Test Mode integration: order creation
  (server-side), Checkout.js modal (browser, public key only), and HMAC-SHA256
  signature verification (server-side). Degrades to a clearly-labeled
  *simulated* mode if no keys are configured.
- **`config.py`** — Conservative environment loader that reads `.env` and
  Streamlit secrets (never overriding existing env vars).
- **`check_site.py`** — Pre-flight wrapper around `webcmd browser <session>
  analyze <url>` to assess a site's anti-bot posture before authoring an
  adapter.

### Data flow

```
User RFQ ──→ parse_rfq_with_gemini() ──→ CustomerDemand
                                             │
                  fetch_all_live_suppliers() │
                  ├── _fetch_via_adapter()   │  (Amazon.in: amazon-in adapter)
                  ├── _fetch_via_generic_browser()  (other sites: browser + Gemini)
                  └── _discover_suppliers_via_web()  (DuckDuckGo web-wide)
                                             │
                  optimize_supply_chain() ──→ AllocationPlan
                                             │
                  Razorpay Test Mode payment (payments.py)
                                             │
                  execute_supplier_procurement()
                  ├── revalidate_mandate_before_purchase()  ← pre-payment gate
                  └── _execute_webcmd_checkout()            ← agent checkout
                                             │
                  Money Shot: revenue − cost = gross profit
```

### Optimized JSON schema

All supplier data is normalized into a single `SupplierQuote` object:

| Field | Type | Notes |
|---|---|---|
| `supplier_id`, `name` | str | |
| `stock` | int | |
| `unit_cost` | float | INR |
| `moq` | int | Minimum order quantity |
| `lead_time_days` | int | |
| `product_url` | str | |
| `compatibility_score` | float | 0.0–1.0 |
| `delivers_to` | list[str] | |
| `source` | str | `"live"`, `"reference"`, or `"web_discovered"` |
| `is_estimate` | dict | Flags fields that are assumptions |
| `checkout_possible` | bool | Whether webcmd can drive checkout |
| `rating`, `review_count` | float / int | From adapter when available |

---

## Demo: One-Day Build & Three-Minute Demo Script

### RUTHLESS SCOPE (Section 6 of the proposal)

| Scope item | Target |
|---|---| 
| Supplier websites | 2 (Amazon.in via adapter + one generic site) |
| Product category | 1 (electronics — part-number-based discovery) |
| Customer payment flow | 1 (Razorpay Test Mode) |
| Agent purchase flow | 1 (webcmd checkout adapter or browser automation) |
| Commercial constraints | 4 (price cap, stock, delivery SLA, minimum margin) |
| Payment safeguards | 3 (spend ceiling, merchant allowlist, final-price tolerance) |

### Three-minute demo script

| Time | Stage | What the audience sees |
|---|---|---|
| 0:00–0:20 | Problem | "Small distributors lose business daily because customers ask for items they don't stock." |
| 0:20–0:35 | Proposition | "What if an SME could sell products it has never stocked?" |
| 0:35–1:30 | Agent acts | Enter the RFQ. Show supplier queries, normalized results, and rejection of the cheapest option because it misses the delivery SLA. |
| 1:30–2:00 | Customer transaction | Complete quote with preserved margin. Customer clicks Pay. Razorpay Test Mode returns success. |
| 2:00–2:40 | Agent spends | Re-checks the mandate, opens supplier checkout via webcmd, places the order, captures confirmation. |
| 2:40–3:00 | Money shot | SALE COMPLETE: customer revenue, supplier cost, gross profit, zero starting inventory, supplier order confirmation. |

### Default demo prompt

```
Need 5 Raspberry Pi 5 8GB units delivered in Bengaluru within 3 days. Maximum customer price ₹10,000 each. Minimum margin 8%.
```

---

## Agent Spending Mandate & Payment Safety

**Reason freely; spend narrowly.** The agent can search, compare, and optimize
broadly — but payment execution is constrained by explicit commercial policy.

| Parameter | Value |
|---|---|
| Maximum order ceiling | ₹250,000 (default; configurable via `MAX_ORDER_SPEND`) |
| Allowed merchants | Robu, Amazon.in, Mouser, element14, Flipkart, DigiKey, IndiaMART |
| Minimum gross margin | 8% (with 2% risk buffer) |
| Maximum price movement | ±2% (re-checked live before purchase) |
| Max delivery | 3 days |
| Substitution policy | require_approval |

### Final pre-payment checks (re-validated live)

Before the agent places any supplier order, `revalidate_mandate_before_purchase()`
re-checks:

1. ✅ **Merchant allowlist** — every allocated supplier is on the approved list
2. ✅ **Spend ceiling** — total supplier cost ≤ ceiling
3. ✅ **Minimum gross margin** — margin minus risk buffer ≥ floor
4. ✅ **Delivery SLA** — planned lead time ≤ required days
5. ✅ **Price drift** — live re-fetch confirms price hasn't moved >2%
6. ✅ **Stock availability** — live re-fetch confirms stock still meets the order
7. ✅ **Substitution policy** — any substitution is explicitly permitted

If any check fails, the purchase is **blocked** and the customer payment is
refunded/held — the agent never spends without a valid mandate.

### ⚠️ A real contradiction in the proposal (worth knowing)

Section 5's mandate table says **Maximum order: ₹50,000**. Section 3.2's own
worked example (25 units × ~₹7,850–8,120/unit) has a **supplier cost of
~₹199,760–201,300** — 4× that ceiling. This build keeps the ceiling at
**₹250,000** (overridable via `MAX_ORDER_SPEND` in `.env` / Streamlit secrets)
so the flagship demo scenario isn't rejected by its own mandate gate. You may
want to reconcile these two numbers in your pitch deck.

---

## Setup

### Prerequisites

- **Python 3.10+**
- **Node.js 20+** (for webcmd)
- **webcmd** CLI: `npm install -g @agentrhq/webcmd`

> 💡 **webcmd skills:** After installing webcmd, run `webcmd skills add` and
> choose your agent harness (Claude, etc.) when prompted. This enables the
> adapter-authoring flow and browser automation.

### API keys (all free, no KYC)

1. **Gemini API key** — https://aistudio.google.com/apikey
   - Used for RFQ parsing, compatibility scoring, and parsing web-extracted
     pages. Falls back to a regex parser if unset (degraded but functional).

2. **Razorpay Test Mode keys** — https://dashboard.razorpay.com/signup →
   Settings → API Keys → Generate Test Key
   - Keys starting with `rzp_test_` are what you want.
   - Free signup, no KYC for Test Mode. **Never use Live keys for a demo.**
   - The app works *without* these (simulated payment mode is clearly labeled),
     but the hackathon is themed on agents that complete real payment flows.

3. **webcmd** — see the adapter-authoring section below. For **local mode** you
   need a real Chromium available to the process (Playwright installs one
   automatically the first time the browser runtime launches). For **hosted
   Cloud mode** (recommended for deployment), run `webcmd setup`, choose
   hosted, and paste an API key from https://api.webcmd.dev/account/signup.

### Configuration

```bash
cp .env.example .env
# Edit .env and fill in:
#   GEMINI_API_KEY=          (required)
#   RAZORPAY_KEY_ID=         (recommended — Test Mode)
#   RAZORPAY_KEY_SECRET=     (recommended — Test Mode)
#   APP_PUBLIC_URL=          (your deploy URL for the Razorpay redirect)
```

Or export the variables directly. For Streamlit Cloud, paste the same values
into the app's **Secrets** panel instead.

### Install Python dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Project

### Local development

```bash
streamlit run app.py
```

Open the link Streamlit prints (usually http://localhost:8501). The sidebar
shows live diagnostics for each dependency — Gemini, webcmd, and Razorpay.

### Via Docker

A `Dockerfile` is included. It assumes webcmd runs in **Cloud (hosted) mode**
so the browser runs on Kernel's infra instead of inside the container.

```bash
docker build -t demand2deal .
docker run -p 8501:8501 --env-file .env demand2deal
```

> To run webcmd in **local mode** inside the container instead, base your image
> on a Playwright Docker image (which bundles Chromium and fonts) rather than
> `python:3.12-slim + manual Node`. See the comment at the top of the
> `Dockerfile`.

### Environment variables reference

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(empty)* | Required for AI parsing/optimization. |
| `RAZORPAY_KEY_ID` | *(empty)* | Razorpay Test Mode public key. |
| `RAZORPAY_KEY_SECRET` | *(empty)* | Razorpay Test Mode secret (server-side only). |
| `APP_PUBLIC_URL` | `http://localhost:8501` | Public URL for Razorpay checkout redirect. |
| `WEBCMD_TIMEOUT_SECONDS` | `45` | Per-command webcmd timeout. |
| `LIVE_PURCHASE_ENABLED` | `false` | 🔒 Master safety switch. When `false` (default), the supplier checkout is prepared to "COD, not finalized" and **never places a real order**. Only set `true` if you deliberately want real-money procurement. |
| `MAX_ORDER_SPEND` | `50000` | Spend-ceiling override (INR). |
| `AUDIT_LOG_PATH` | `audit_log.json` | Path to the JSON audit trail. |
| `WEBCMD_WORKSPACE` | *(empty)* | webcmd Cloud workspace ID (hosted mode). |

---

## Deployment

### Streamlit Community Cloud (fastest to "live link")

Streamlit Cloud containers don't reliably run a local Chromium — **use webcmd's
hosted Cloud mode** (see Setup) so the browser runs on Kernel's infra.

1. Push this repo to GitHub.
2. https://share.streamlit.io → **New app** → point at your repo, `app.py`.
3. In the app's **Secrets** panel, paste the contents of your `.env` (Streamlit
   Cloud reads secrets as env vars automatically).
4. Set `APP_PUBLIC_URL` to the `https://<your-app>.streamlit.app` URL Streamlit
   gives you, so the Razorpay Checkout redirect comes back correctly.

### Self-hosting (Render, Fly.io, a VPS, etc.)

```bash
docker build -t demand2deal .
docker run -p 8501:8501 --env-file .env demand2deal
```

Mount a volume at `/root/.webcmd` if you want the webcmd Cloud setup to persist
across container restarts instead of re-running `webcmd setup` every start.

---

## Authoring a Custom Supplier Adapter

> **This is the one step I can't fully do for you from a chat conversation** —
> webcmd's adapter-authoring flow is inherently interactive: an agent harness
> drives a real browser against the real site.

As of this writing, webcmd ships **101 built-in site adapters**. `Amazon.in`
has a built-in adapter (which is why it's wired up out of the box). **Robu.in,
Mouser, element14, and DigiKey do not** — they run today via the generic browser
fallback, but authoring a real adapter for them makes discovery faster and far
more reliable (and is worth ~20 minutes during the event's Browser Agents 101
primer).

### 1. Install webcmd and its skills (Node 20+ required)

```bash
npm install -g @agentrhq/webcmd
webcmd skills add
# When prompted, choose Claude (or whichever harness you're using)
```

### 2. Sanity-check the site first

Don't spend authoring time on a site that's heavily bot-protected:

```bash
python3 check_site.py https://robu.in
```

This wraps `webcmd browser main analyze https://robu.in`, which classifies the
anti-bot posture, suggests real-data API candidates, points at the nearest
existing adapter to model yours on, and recommends a next step.

### 3. Author the adapter

Open Claude Code in this project folder and paste:

```
Use the webcmd-usage skill, then webcmd-adapter-author, to create a
private Webcmd adapter for Robu.in (https://robu.in), an Indian
electronics distributor.

Command: webcmd robu search "<query>" -f json
Output: stable JSON rows with fields product_url, price (float, INR),
stock (int), lead_time_days (int), title (str). Use null for anything
genuinely unavailable rather than guessing.

This is a public product-search page -- read-only, no login needed.
Verify the command with two different queries (e.g. "Raspberry Pi 5 8GB"
and "Arduino Uno") and show me the JSON output for both before you
finish. If Robu.in's anti-bot layer blocks automated search entirely,
tell me that plainly instead of forcing a workaround.
```

### 4. Wire it up

Once verified, flip the mode in `engine.py`:

```python
{
    "supplier_id": "robu",
    "name": "Robu.in",
    "mode": "adapter",   # was "generic"
    ...
}
```

…and, if the adapter's field names differ from this repo's `SupplierQuote`
schema, adjust the mapping in `_fetch_via_adapter()`'s generic branch to match.

Until you do this, the app **already works** via the generic fallback path
(`_fetch_via_generic_browser`) — it's just slower and less deterministic,
which is exactly the tradeoff webcmd's docs describe.

---

## Honesty Notes & Caveats

These are things to say out loud during the demo, not hide:

- **Amazon.in's built-in adapter doesn't expose a stock count or delivery
  estimate.** This build uses a documented placeholder (25 units, 2-day
  delivery) for those two fields only — price and product URL are real. Flagged
  in the UI with `(est.)` next to those columns.
- **Amazon.in checkout is capped at 10 units per line** by the adapter itself.
  If a plan allocates more than 10 units to Amazon.in, only 10 are actually
  prepared — flagged in the procurement result.
- **`LIVE_PURCHASE_ENABLED` defaults to `false`.** The demo drives Amazon
  checkout all the way to "prepared, COD, not finalized" rather than spending
  real money, per hard rule #2. Flip it only if you've deliberately decided
  that's what you want live, with a cheap item.
- **Reference-pricing fallback is opt-in and clearly badged**, never silently
  substituted for live data. The UI always shows a **LIVE DATA** or
  **REFERENCE DATA** badge so judges see exactly what they're looking at.
- **The proposal's ₹50,000 spend ceiling contradicts its own ₹200k+ worked
  example** (see the contradiction callout above). This build uses ₹250,000 so
  the demo doesn't reject its own flagship scenario.

---

## Project Layout

```
app.py              Streamlit UI / state machine (5-stage commercial loop)
engine.py           RFQ parsing, webcmd supplier discovery, optimizer, mandate gate, checkout automation
payments.py         Razorpay Test Mode: order creation + signature verification + checkout.js
config.py           Conservative .env / Streamlit-secrets loader
check_site.py       Pre-flight webcmd `analyze` wrapper for adapter authoring
requirements.txt    Python dependencies
.env.example        Template for environment variables (copy → .env)
Dockerfile          Self-hosting image (assumes webcmd Cloud hosted mode)
.gitignore
audit_log.json      Runtime JSON audit trail of every commercial event (gitignored)
```

### Key data models (`engine.py`)

| Model | Purpose |
|---|---|
| `CustomerDemand` | Parsed RFQ: product, qty, budget, deadline, location, margin. |
| `SupplierQuote` | Normalized supplier offer: price, stock, MOQ, lead time, URL. |
| `AllocationPlan` | Optimized supplier allocation + revenue/cost/profit math. |
| `MandateCheckResult` | Result of the pre-payment spend-policy gate. |
| `AuditEvent` | Timestamped record of each commercial action (logged to JSON). |

---

## Sources

1. [webcmd Hackathon — Agentic Payments Edition (Luma)](https://luma.com/hmr76csk)
2. [webcmd Documentation](https://webcmd.dev/docs/)
3. [Razorpay — Test and Live Modes](https://razorpay.com/docs/payments/dashboard/test-live-modes/)
4. [Razorpay & NPCI launch agentic payments](https://razorpay.com/newsroom/?p=4701)
