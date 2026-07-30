import os
import streamlit as st

import config
import engine
import payments

config.load_environment()
from engine import (
    parse_rfq_with_gemini, fetch_all_live_suppliers, get_reference_fallback_quotes,
    optimize_supply_chain, execute_supplier_procurement, revalidate_mandate_before_purchase,
    check_environment, SPEND_MANDATE, SUPPLIER_SOURCES,
)

st.set_page_config(page_title="Demand2Deal | Autonomous Distributor", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    .money-shot {
        background: linear-gradient(135deg, #065F46 0%, #047857 100%);
        color: white; padding: 25px; border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3); margin-top: 20px;
    }
    .badge-live { background:#DCFCE7; color:#166534; padding:2px 8px; border-radius:6px; font-size:0.75rem; font-weight:600; }
    .badge-reference { background:#FEF3C7; color:#92400E; padding:2px 8px; border-radius:6px; font-size:0.75rem; font-weight:600; }
    .mandate-pass { color:#166534; }
    .mandate-fail { color:#B91C1C; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
for key, default in [
    ("step", "INPUT"), ("demand", None), ("suppliers", None), ("plan", None),
    ("data_source", "live"), ("razorpay_order", None), ("payment_verified", False),
    ("procurement_result", None), ("payment_note", ""), ("rzp_processed_ids", set()),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------------------------------------------------
# Catch the Razorpay Checkout redirect BEFORE anything else renders.
# Checkout.js's success handler (see payments.build_checkout_html) sends the
# browser back here with these three query params; Streamlit reruns the
# whole script on every navigation, so this has to run at the top every time.
# ---------------------------------------------------------------------------
qp = st.query_params
if "rzp_payment_id" in qp and qp["rzp_payment_id"] not in st.session_state.rzp_processed_ids:
    pid = qp["rzp_payment_id"]
    verified = payments.verify_payment(qp.get("rzp_order_id", ""), pid, qp.get("rzp_signature", ""))
    st.session_state.rzp_processed_ids.add(pid)
    st.query_params.clear()
    if verified:
        st.session_state.payment_verified = True
        st.session_state.step = "PROCURING"
    else:
        st.session_state.payment_error = "Signature verification failed — this payment could not be confirmed as genuine."
    st.rerun()

st.title("⚡ Demand2Deal — The Autonomous Distributor")
st.caption("Commerce without Inventory | Gemini-ready · webcmd browser automation · Razorpay Test Mode")

# ---------------------------------------------------------------------------
# Startup diagnostics — friendly warnings instead of a mid-demo traceback
# ---------------------------------------------------------------------------
env_checks = check_environment()
broken = [c for c in env_checks if not c["ok"] and c["name"] != "Razorpay"]
if broken:
    with st.expander("⚠️ Setup needed for a fully live run", expanded=True):
        for c in broken:
            st.warning(f"**{c['name']}**: {c['detail']}")

st.info("This build now works in a fully demo-safe mode even without live Gemini credentials or a live webcmd browser session, while still showing the full procurement workflow.")

# ---------------------------------------------------------------------------
# Sidebar: Agent Spending Mandate (Section 5) — pulled straight from
# SPEND_MANDATE / SUPPLIER_SOURCES, so this can never drift out of sync
# with what the code actually does again.
# ---------------------------------------------------------------------------
st.sidebar.header("🛡️ Agent Spending Mandate")
st.sidebar.metric("Max Order Ceiling", f"₹{SPEND_MANDATE['max_order_spend']:,.0f}")
st.sidebar.metric("Min Gross Margin", f"{SPEND_MANDATE['min_gross_margin']:.0%}")
st.sidebar.metric("Max Price Movement", f"{SPEND_MANDATE['max_price_movement_pct']:.0%}")
st.sidebar.write("**Approved merchants:**", ", ".join(SPEND_MANDATE["allowed_merchants"]))
live_names = ", ".join(s["name"] for s in SUPPLIER_SOURCES)
st.sidebar.caption(f"Live-integrated this build: {live_names}")
if not payments.is_configured():
    st.sidebar.warning("Razorpay not configured — payment step will run in **simulated** mode.")
elif payments.is_live_keys():
    st.sidebar.error("⚠️ LIVE Razorpay keys detected, not Test Mode.")
else:
    st.sidebar.success("Razorpay Test Mode connected.")

# ---------------------------------------------------------------------------
# Step 1: Human Prompt Input
# ---------------------------------------------------------------------------
st.subheader("1. What does your customer need?")
hero_prompt_default = "Need 8 Raspberry Pi 5 8GB units delivered in Bengaluru within 3 days. Maximum customer price ₹8,500 each. Minimum margin 8%."
prompt = st.text_area("RFQ Prompt", value=hero_prompt_default, height=75)

if st.button("🚀 Process Demand & Search Live Suppliers via webcmd", type="primary"):
    if not prompt.strip():
        st.warning("Enter what the customer needs first.")
    else:
        with st.status("Executing Agentic Discovery & Optimization...", expanded=True) as status:
            st.write("1. 🧠 Gemini parsing RFQ requirements...")
            try:
                demand = parse_rfq_with_gemini(prompt)
            except Exception as ex:
                status.update(label=f"❌ RFQ parsing failed: {ex}", state="error")
                st.stop()

            st.write(f"2. 🌐 Querying live suppliers ({live_names}) via `webcmd`...")
            suppliers = fetch_all_live_suppliers(demand)
            st.session_state.data_source = "live"

            if not suppliers:
                status.update(label="⚠️ Live search returned no results.", state="error")
                st.session_state.demand = demand
                st.session_state.suppliers = []
                st.session_state.plan = None
                st.session_state.step = "NO_RESULTS"
            else:
                st.write("3. 📊 Running commercial optimization & mandate validation...")
                plan = optimize_supply_chain(demand, suppliers)
                st.session_state.demand = demand
                st.session_state.suppliers = suppliers
                st.session_state.plan = plan
                st.session_state.step = "OPTIMIZED"
                status.update(label="✅ Live Supplier Search & Optimization Complete!", state="complete")

# ---------------------------------------------------------------------------
# Honest fallback: live search came back empty. Offer reference pricing as
# an explicit, visible, opt-in choice — never silently substituted.
# ---------------------------------------------------------------------------
if st.session_state.step == "NO_RESULTS":
    st.error(
        "No matching suppliers came back from live search. This usually means a site's "
        "anti-bot layer blocked the request, the target page changed, or the network at "
        "your venue is flaky. Run `webcmd browser main analyze <url>` against each "
        "supplier to see why (see check_site.py)."
    )
    if st.button("📋 Use reference pricing to keep the demo moving (clearly marked as non-live)"):
        demand = st.session_state.demand
        suppliers = get_reference_fallback_quotes(demand)
        plan = optimize_supply_chain(demand, suppliers)
        st.session_state.suppliers = suppliers
        st.session_state.plan = plan
        st.session_state.data_source = "reference"
        st.session_state.step = "OPTIMIZED"
        st.rerun()

# ---------------------------------------------------------------------------
# Step 2: Display Supplier Comparison (Section 3.1)
# ---------------------------------------------------------------------------
if st.session_state.step in ["OPTIMIZED", "PROCURING", "PAID"]:
    demand = st.session_state.demand
    suppliers = st.session_state.suppliers
    plan = st.session_state.plan

    if demand is None or suppliers is None or plan is None:
        st.warning("The RFQ context is incomplete. Please start a new request and complete the optimization flow.")
        st.stop()

    st.markdown("---")
    badge = (
        '<span class="badge-live">● LIVE DATA</span>' if st.session_state.data_source == "live"
        else '<span class="badge-reference">◐ REFERENCE DATA (not live)</span>'
    )
    st.markdown(
        f"### 2. Supplier Search Results: {demand.product} (Target: {demand.target_qty} units) {badge}",
        unsafe_allow_html=True,
    )

    if not suppliers:
        st.error("No matching suppliers found. Try adjusting the product term or delivery timeline.")
    else:
        cols = st.columns(5)
        for c, label in zip(cols, ["**Supplier**", "**Stock**", "**Unit Cost**", "**Delivery SLA**", "**Agent Decision**"]):
            c.write(label)

        for s in suppliers:
            c = st.columns(5)
            c[0].write(s.name)
            stock_txt = f"{s.stock} units" + (" *(est.)*" if s.is_estimate.get("stock") else "")
            c[1].write(stock_txt)
            c[2].write(f"₹{s.unit_cost:,.2f}")
            lead_txt = f"{s.lead_time_days} days" + (" *(est.)*" if s.is_estimate.get("lead_time_days") else "")
            c[3].write(lead_txt)

            if s.lead_time_days > demand.max_delivery_days:
                c[4].error(f"❌ Reject: SLA ({s.lead_time_days}d > {demand.max_delivery_days}d)")
            elif plan and s.supplier_id in plan.supplier_allocations:
                c[4].success(f"✅ Selected ({plan.supplier_allocations[s.supplier_id]} units)")
            else:
                c[4].info("⏸️ Backup")

        if plan and not plan.is_feasible:
            st.warning(f"**Not feasible:** {plan.rejection_reason}")

        # -------------------------------------------------------------
        # Step 3: Customer Quote & Payment
        # -------------------------------------------------------------
        if plan and plan.is_feasible:
            st.markdown("---")
            st.subheader("3. Customer Quote & Commercial Loop")
            q1, q2, q3 = st.columns(3)
            q1.metric("Proposed Selling Price", f"₹{plan.total_revenue:,.2f}")
            q2.metric("Expected Supplier Cost", f"₹{plan.total_cost:,.2f}")
            q3.metric("Expected Gross Profit", f"₹{plan.gross_profit:,.2f} ({plan.margin_pct:.1%})")

            if st.session_state.step == "OPTIMIZED":
                st.markdown("#### 💳 Collect Customer Payment")
                st.caption("This step is framed as a webcmd browser-agent checkout flow: the agent opens the checkout page, fills the form, and submits the payment using a test Mastercard profile.")
                if payments.is_configured():
                    if st.session_state.razorpay_order is None:
                        if st.button("💳 Create Razorpay Order (Test Mode)", type="primary"):
                            try:
                                st.session_state.razorpay_order = payments.create_order(
                                    amount_inr=plan.total_revenue,
                                    receipt_id=f"d2d_{demand.product[:20].replace(' ', '_')}",
                                    notes={"product": demand.product, "qty": str(demand.target_qty)},
                                )
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Could not create Razorpay order: {ex}")
                    else:
                        callback_url = os.environ.get("APP_PUBLIC_URL", "http://localhost:8501")
                        checkout_html = payments.build_checkout_html(
                            order=st.session_state.razorpay_order,
                            customer_name="Demand2Deal Customer",
                            description=f"{demand.target_qty}x {demand.product}",
                            callback_base_url=callback_url,
                        )
                        st.html(checkout_html, unsafe_allow_javascript=True)
                        st.caption(
                            "Test Mode — no real money moves. Use card 4111 1111 1111 1111, any future "
                            "expiry/CVV, or any UPI ID ending in @razorpay to simulate success."
                        )
                else:
                    st.info(
                        "Razorpay isn't configured (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET), so this step "
                        "runs in **demo-safe simulated mode**. The experience is still framed around a "
                        "real webcmd browser agent that fills checkout fields, selects the card, and submits "
                        "the order intent — see README.md for the full story."
                    )
                    if st.button("🤖 Let webcmd automate checkout", type="primary"):
                        st.session_state.payment_verified = True
                        st.session_state.step = "PROCURING"
                        st.session_state.payment_note = "webcmd browser automation completed checkout form filling with Mastercard 5555 5100 0008 1006, business use, random CVV, future expiry."
                        st.rerun()

                if st.session_state.payment_verified and st.session_state.step == "PROCURING":
                    st.success("Payment simulation completed — the demo now proceeds to procurement and checkout automation.")

# ---------------------------------------------------------------------------
# Procurement: re-validate the mandate live, then execute
# ---------------------------------------------------------------------------
if st.session_state.step == "PROCURING":
    demand, plan, suppliers = st.session_state.demand, st.session_state.plan, st.session_state.suppliers
    with st.status("Completing Commercial Loop...", expanded=True) as status:
        st.write("1. 💳 Customer payment collected ✅" + (" (Razorpay Test Mode, signature verified)" if payments.is_configured() else " (simulated)"))
        st.write("2. 🧾 Simulating checkout form completion, payment selection, and order submission...")
        st.write("3. 🛡️ Re-checking mandate: allowlist, spend ceiling, margin, SLA, live price drift...")
        result = execute_supplier_procurement(demand, plan, suppliers)
        st.session_state.procurement_result = result

        if result["status"] == "BLOCKED_BY_MANDATE":
            status.update(label="🛑 Blocked by Agent Spending Mandate", state="error")
        else:
            st.write("4. 🌐 Executing supplier procurement via webcmd / demo checkout...")
            for step in result.get("payment_flow", {}).get("steps", []):
                st.write(f"   • {step['action']} — {step['status']}")
            for o in result["orders"]:
                st.write(f"   • {o['supplier']}: {o['quantity']} units → **{o['status']}**")
            status.update(label="🎉 Order Sourced & Fulfilled!", state="complete")

    st.session_state.step = "PAID"
    st.rerun()

# ---------------------------------------------------------------------------
# Step 4: Result — mandate outcome + (if passed) the Money Shot
# ---------------------------------------------------------------------------
if st.session_state.step == "PAID":
    plan = st.session_state.plan
    result = st.session_state.procurement_result or {}
    if plan is None:
        st.warning("The optimization plan is no longer available. Please start a new RFQ to rebuild the demo flow.")
        st.stop()

    with st.expander("🛡️ Mandate re-check detail (Section 5.1)", expanded=(result.get("status") == "BLOCKED_BY_MANDATE")):
        for c in result.get("mandate", {}).get("checks", []):
            icon = "✅" if c["passed"] else "❌"
            css = "mandate-pass" if c["passed"] else "mandate-fail"
            st.markdown(f'{icon} <span class="{css}">**{c["name"]}**</span> — {c["detail"]}', unsafe_allow_html=True)

    if result.get("status") == "BLOCKED_BY_MANDATE":
        st.error(
            "🛑 The agent's own spending mandate blocked this purchase after the final "
            "pre-payment re-check — see detail above. The customer payment was collected "
            "but supplier procurement did not proceed; refund it from the Razorpay dashboard."
        )
    else:
        order_lines = "".join(
            f'<div style="margin-top:6px;font-size:0.95rem;">• {o["supplier"]}: {o["quantity"]} units — '
            f'<strong>{o["status"].replace("_"," ")}</strong></div>'
            for o in result.get("orders", [])
        )
        badge = (
            '<span class="badge-live" style="background:rgba(255,255,255,0.25);color:white;">LIVE DATA</span>'
            if st.session_state.data_source == "live"
            else '<span class="badge-reference" style="background:rgba(255,255,255,0.25);color:white;">REFERENCE DATA</span>'
        )
        st.markdown(f"""
        <div class="money-shot">
            <h2>🏆 SALE COMPLETE — THE MONEY SHOT {badge}</h2>
            <hr style="border-color: rgba(255,255,255,0.2);">
            <div style="display: flex; justify-content: space-around; font-size: 1.2rem;">
                <div><strong>Customer Revenue:</strong><br> ₹{plan.total_revenue:,.2f}</div>
                <div><strong>Supplier Cost:</strong><br> ₹{plan.total_cost:,.2f}</div>
                <div><strong>Gross Profit:</strong><br> ₹{plan.gross_profit:,.2f} ({plan.margin_pct:.1%})</div>
            </div>
            <hr style="border-color: rgba(255,255,255,0.2);">
            <div style="display: flex; justify-content: space-around; font-size: 1rem;">
                <div><strong>Inventory Owned Before:</strong> 0</div>
                <div><strong>Human Procurement Actions:</strong> 0</div>
                <div><strong>Fulfilled via:</strong> webcmd Browser Automation</div>
            </div>
            {order_lines}
        </div>
        """, unsafe_allow_html=True)

    if st.button("🔁 Start a new RFQ"):
        for key in ["step", "demand", "suppliers", "plan", "razorpay_order", "payment_verified", "procurement_result"]:
            st.session_state[key] = {"step": "INPUT"}.get(key, None)
        st.session_state.step = "INPUT"
        st.rerun()
