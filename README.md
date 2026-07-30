# Demand2Deal — The Autonomous Distributor

Agentic B2B commerce demo for the **webcmd Hackathon Agentic Payments
Edition** (Sat Aug 1, 2026, Bengaluru): a customer RFQ comes in, an agent
sources live supplier quotes, optimizes the supply chain against a spending
mandate, collects a real Razorpay Test Mode payment, re-validates the
mandate, and (where a checkout adapter exists) drives the supplier-side
purchase -- all with zero starting inventory.

## What changed from the original prototype, and why

The uploaded app.py/engine.py were a good product sketch, but several
things didn't hold up against the real webcmd CLI, the real Gemini model
lineup, and the proposal's own numbers. Fixed here:

| Issue | Was | Now |
|---|---|---|
| **webcmd commands didn't exist as written** | `webcmd browser main find --css "body"` for full-page text | `webcmd browser <session> extract` -- `find` is for locating a handful of short UI elements (50 entries x 120 chars, by design), not full-page text |
| **webcmd's actual value was unused** | Every request re-scrapes + re-parses with an LLM | Amazon.in now uses the **built-in `amazon-in` adapter** (verified via `webcmd list`) -- deterministic, no LLM round-trip. Robu.in still uses the generic fallback until you author a real adapter (see below) |
| **Suppliers named in the UI didn't match what the code queried** | UI said "Robu.in, Mouser India"; code hit fabricated `electronicscomp.com`/`quartzcomponents.com` | Supplier list is now defined once (`SUPPLIER_SOURCES`) and both the UI text and the actual queries read from it -- can't drift apart again |
| **Gemini models were wrong/dead** | `gemini-2.0-flash`, `gemini-2.0-flash-lite` (shut down Jun 1, 2026), `gemini-3.5-flash-lite`, `models/gemini-3.5-flash` | `gemini-3.6-flash` -> `gemini-3.5-flash-lite` -> `gemini-2.5-flash-lite`, current GA models, bare IDs (no `models/` prefix) |
| **Spend mandate numbers didn't match the proposal** | Code: Rs.250,000 ceiling, allowed merchants `ElectronicsComp`/`Quartz Components` (match nothing) | See the **proposal contradiction** callout below -- kept Rs.250,000 deliberately; merchants now `Robu, Amazon.in, Mouser, element14` |
| **"Final pre-payment checks" (proposal S5.1) didn't exist in code** | app.py printed a hardcoded `Mandate Policy Gate re-checked... OK` string | `revalidate_mandate_before_purchase()` actually re-checks merchant allowlist, spend ceiling, margin floor, delivery SLA, **and live price drift** -- and blocks the purchase if any fail |
| **"Razorpay Test Mode" was `time.sleep(1)`** | No API call at all | Real Razorpay Orders API + Checkout.js + signature verification (`payments.py`), with an explicitly-labeled simulated fallback if you haven't added keys yet |
| **No resilience if live search fails** | Blank error, demo dead-ends | Explicit, clearly-labeled "reference pricing" fallback the operator opts into -- never silently substituted |

### A real contradiction in the proposal itself (worth knowing before you present)

Section 5's mandate table says **Maximum order: Rs.50,000**. Section 3.2's
own worked example (25 units, ~Rs.7,850-8,120/unit) has a **supplier cost
of ~Rs.199,760-201,300** -- 4x that ceiling. I tested both: at Rs.50,000,
the flagship demo scenario gets rejected by its own mandate gate. I kept
the ceiling at Rs.250,000 (what the original code already had) so your
demo doesn't break, but you may want to reconcile the two numbers in your
pitch deck too.

---

## Before the hackathon: author a real Robu.in adapter

**This is the one step I can't do for you from a chat conversation** --
webcmd's adapter-authoring flow is inherently interactive: an agent
harness drives a real browser against the real site. Robu, Mouser, and
element14 don't have built-in webcmd adapters (checked the full registry
of 101 built-in site adapters -- Amazon.in does, which is why it's wired
up as-is). Do this once, ideally tonight or during the event's 30-minute
Browser Agents 101 primer:

**1. Install webcmd and its skills** (Node 20+ required):
```bash
npm install -g @agentrhq/webcmd
webcmd skills add
# When prompted, choose Claude (or whichever harness you're using)
```

**2. Sanity-check the site first** -- don't spend authoring time on a site
that's heavily bot-protected:
```bash
python3 check_site.py https://robu.in
```
This runs `webcmd browser main analyze https://robu.in`, which classifies
anti-bot posture, suggests real-data API candidates, and points at the
nearest existing adapter to model yours on.

**3. Open Claude Code (or your chosen harness) in this project folder and
paste this** -- it follows webcmd's own documented "Create a Reusable CLI"
pattern, with field names matching this repo's `SupplierQuote` schema
exactly so no glue code is needed afterward:

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

**4. Once it's verified**, flip the mode in `engine.py`:
```python
{
    "supplier_id": "robu",
    "name": "Robu.in",
    "mode": "adapter",   # was "generic"
    ...
}
```
and, if the agent's field names differ from the schema above, adjust the
mapping in `_fetch_via_adapter()`'s generic branch to match.

Until you do this, the app **already works** via the generic fallback path
(`_fetch_via_generic_browser`) -- it's just slower and less deterministic,
which is exactly the tradeoff webcmd's docs describe. Live reliability is
30 of the judges' 100 points, so this step is worth the 20 minutes.

---

## Setup

**1. Gemini API key** (free): https://aistudio.google.com/apikey

**2. Razorpay Test Mode keys** (free, no KYC needed for Test Mode):
https://dashboard.razorpay.com/signup -> Settings -> API Keys -> Generate
Test Key. Keys starting `rzp_test_` are what you want.

**3. webcmd**: see the adapter-authoring section above. For **local mode**
you need a real Chromium available to the process (Playwright installs one
automatically the first time webcmd's browser runtime launches); for
**hosted Cloud mode** (recommended if you're deploying this anywhere other
than your own laptop -- see Deployment below), run `webcmd setup`, choose
hosted, and paste an API key from https://api.webcmd.dev/account/signup.

**4. Copy `.env.example` to `.env`** and fill in the values, or export
them directly:
```bash
cp .env.example .env
# edit .env
```

**5. Install Python dependencies and run:**
```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Deployment

Streamlit Community Cloud is the fastest path to "deployed, shareable
link," but its containers don't reliably run a local Chromium -- **use
webcmd's hosted Cloud mode** (see Setup step 3) so the actual browser runs
on Kernel's infra instead of inside the Streamlit container. Then:

1. Push this repo to GitHub.
2. https://share.streamlit.io -> New app -> point at your repo, `app.py`.
3. In the app's **Secrets** panel, paste the contents of your `.env`
   (Streamlit Cloud reads secrets as env vars automatically).
4. Set `APP_PUBLIC_URL` to the `https://<your-app>.streamlit.app` URL
   Streamlit gives you, so the Razorpay Checkout redirect comes back to
   the right place.

**Self-hosting instead** (Render, Fly.io, a VPS, etc.): a `Dockerfile` is
included. It assumes webcmd Cloud (hosted) mode for the same reason as
above -- see the comment at the top of the Dockerfile if you'd rather run
webcmd in local mode with Chromium bundled into the container.

```bash
docker build -t demand2deal .
docker run -p 8501:8501 --env-file .env demand2deal
```

---

## Honesty notes (things to say out loud during the demo, not hide)

- **Amazon.in's `search`/`product` commands don't expose a stock count or
  delivery estimate.** This build uses a documented placeholder (25 units,
  2-day delivery) for those two fields only -- price and product URL are
  real. Flagged in the UI via "(est.)" next to those columns.
- **Amazon.in checkout is capped at 10 units per line** by the adapter
  itself. If a plan allocates more than 10 units to Amazon.in, only 10 are
  actually prepared -- flagged in the procurement result.
- **`LIVE_PURCHASE_ENABLED` defaults to `false`.** The demo drives Amazon
  checkout all the way to "prepared, COD, not finalized" rather than
  spending real money, per hard rule #2. Flip it only if you've decided
  that's what you want live, with a cheap item.
- **Reference-pricing fallback is opt-in and clearly badged**, never
  silently substituted for live data -- the UI always shows a LIVE DATA or
  REFERENCE DATA badge so judges see exactly what they're looking at.

## Project layout

```
app.py              Streamlit UI / state machine
engine.py           RFQ parsing, supplier sourcing, optimizer, mandate gate
payments.py         Razorpay Test Mode: order creation + signature verification
check_site.py       Pre-flight `webcmd analyze` wrapper for adapter authoring
requirements.txt
.env.example
Dockerfile
```
