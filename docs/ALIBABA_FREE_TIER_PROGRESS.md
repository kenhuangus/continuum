# Alibaba Cloud International Free Tier — Progress

**Date:** 2026-07-18  
**Automation:** Playwright headed Chromium (fresh profile — no existing session)  
**Goal:** Claim free trial for **ECS** and/or **Function Compute** (Continuum deploy), stop cleanly at payment.

---

## Verdict

**Blocked at login.** Automated browser is **not logged in**. Every console / trial / RAM / billing URL redirects to Sign In. No credentials were entered (none available in the automation profile).

**Payment gate (documented, not yet interactive):** Free Trial onboarding **Step 2 — Add a Payment Method** (Visa / Mastercard / JCB / Amex / PayPal / RuPay / UPI). No live card-number form was reachable without login; we **stopped** rather than inventing card data.

Your **default browser** was also opened to `https://www.alibabacloud.com/free` so you can log in there in parallel.

---

## Steps completed (automation)

| # | Step | Result |
|---|------|--------|
| 1 | Opened `https://www.alibabacloud.com/free` | OK — “AI + Cloud Free Trial”; header shows **Login** (not logged in) |
| 2 | Accepted cookie banner | OK |
| 3 | Mapped CTAs | Found ECS **Try it now** → trial center; **Start for Free** / **Start Now** → login/register |
| 4 | Opened ECS trial center `https://ecs-buy.alibabacloud.com/trialCenter#/internationalPersonalTrial` | **Redirect → Login** (oauth callback preserves trial center) |
| 5 | Opened Function Compute product page | OK; Free Trial CTA returns to free landing (still logged out) |
| 6 | Probed billing / payment-method consoles | **Redirect → Login** |
| 7 | Opened RAM AccessKey `https://ram.console.alibabacloud.com/manage/ak` | **Redirect → Login** |
| 8 | Captured free-page Step 2 payment method as CC-gate guide | OK — stopped (no fake cards) |

**Not completed (needs you):** Sign in → add real payment method → claim ECS (prefer Singapore `ap-southeast-1`) → optional FC → create RAM AccessKey.

---

## Where blocked

| Gate | URL | What you see |
|------|-----|----------------|
| **Login (hard stop for automation)** | `https://account.alibabacloud.com/login/login.htm?oauth_callback=https%3A%2F%2Fecs-buy.alibabacloud.com%2FtrialCenter#/internationalPersonalTrial` | Sign In form |
| **Payment (next gate after login)** | Documented on free landing as Step 2; live form after auth (e.g. usercenter payment method) | Add payment method |
| **RAM AK** | Same login wall with callback to `/manage/ak` | Sign In |

---

## Screenshots

| File | What it shows |
|------|----------------|
| `docs/screenshots/alibaba_free_tier_landing.png` | Free Trial landing (logged out) |
| `docs/screenshots/alibaba_free_pass2_landing.png` | Landing after cookie accept |
| `docs/screenshots/alibaba_free_tier_cc_gate.png` | **Step 2: Add a Payment Method** (Visa/MC/JCB/Amex/PayPal/RuPay/UPI) — CC gate guide |
| `docs/screenshots/alibaba_free_tier_payment_step_marketing.png` | Same 3-steps section |
| `docs/screenshots/alibaba_ecs_trial_center.png` | ECS trial URL → **Sign In** redirect |
| `docs/screenshots/alibaba_login_detail.png` | Sign In form detail |
| `docs/screenshots/alibaba_ram_accesskey_status.png` | RAM AK URL → **Sign In** redirect |
| `docs/screenshots/alibaba_fc_after_cta.png` | After FC Free Trial click |
| `docs/screenshots/alibaba_billing_probe_*.png` | Billing probes → login |

Raw JSON log: `docs/alibaba_free_tier_progress.json`

---

## Exact login fields (what to enter)

On the Sign In page (screenshot: `alibaba_login_detail.png` / `alibaba_ecs_trial_center.png`):

1. **Account** — your Alibaba Cloud International email (placeholder: *Enter your email*)  
2. **Password** — your password (placeholder: *Enter your password*)  
3. Click orange **Sign In**

**Or:** **Log in with Google** / **Log in with Github** if that is how you registered.  
**Or:** top-right **Sign Up** / “Sign up now for an account” if you do not have an account yet (phone/email verification will be required).

Do **not** invent accounts or passwords. Automation left all fields empty.

---

## Precise next clicks (human)

### A. Log in (do this first — in the browser window already opened)

1. Click **Login** (top right) on `https://www.alibabacloud.com/free`, **or** go straight to the ECS-preserving login URL above.  
2. Enter **Account** + **Password** → **Sign In** (or Google/GitHub).  
3. Complete captcha / MFA / phone verify if shown.  
4. Tell the agent when done if you want automation to continue click-through.

### B. Payment method (STOP was intentional here for automation)

After login, complete **Step 2: Add a Payment Method**:

- Enter **your real** card or PayPal/UPI as offered.  
- Accepted brands shown on the free page: **Visa, Mastercard, JCB, American Express, PayPal, RuPay, UPI**.  
- **Never** use fake card numbers.

### C. Claim ECS free trial (simplest Continuum path)

1. Open: https://ecs-buy.alibabacloud.com/trialCenter#/internationalPersonalTrial  
2. Select region **Singapore (`ap-southeast-1`)** if prompted.  
3. Agree to terms → confirm / claim the free trial package.  
4. Optional: also claim **Function Compute** from https://www.alibabacloud.com/free or the FC console.

### D. RAM AccessKey (after login; usually no extra CC)

1. https://ram.console.alibabacloud.com/manage/ak  
2. **Create AccessKey** → complete MFA if asked.  
3. Store AccessKey ID + Secret **outside git** (e.g. `aliyun configure` / env vars). See `docs/ALIBABA_DEPLOY_GUIDE.md`.

---

## Click path discovered (for Continuum)

```
https://www.alibabacloud.com/free
  → Login (required)
  → Add Payment Method (required for free trial eligibility)
  → Claim free tier
  → ECS: https://ecs-buy.alibabacloud.com/trialCenter#/internationalPersonalTrial
       (prefer Singapore ap-southeast-1)
  → RAM AK: https://ram.console.alibabacloud.com/manage/ak
```

Alternate CTAs on free page: **Start for Free**, **Start Now**, ECS card **Try it now** (same trial center; all hit login when logged out).

---

## Constraints honored

- No fake credit cards  
- No fake identity data  
- No secrets stored in git  
- Stopped at payment documentation / login wall before any card entry  
