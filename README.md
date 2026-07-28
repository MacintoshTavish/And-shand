# And-Shand

Find the cheapest food on Swiggy for any location. Sorts restaurants by what you'll actually pay at checkout — not just the menu price.

## What It Does

- Enter any Indian location (name or lat/lng)
- Set how many people are eating and veg/non-veg preference
- Fetches restaurants delivering to that location from Swiggy
- Calculates estimated checkout price using the real delivery fee when Swiggy provides it (GST + platform + packaging + delivery + small-order fee)
- Sorts cheapest first, skips closed/unserviceable restaurants
- Select any restaurant to browse its full menu with category filters
- Select any item to see a full price breakdown with add-ons and variants

## Install

```bash
# optional — only needed for auto-login from browser
pip3 install browser_cookie3 lz4 pycryptodomex
```

No other dependencies. Runs on Python 3.7+ with just stdlib.

## Run

```bash
# interactive
python3 swiggy_deals.py

# skip the wizard
python3 swiggy_deals.py -l "Koramangala" -p 2 --veg both

# machine-readable, for scripts
python3 swiggy_deals.py --json -l "12.935,77.624" --limit 10
```

The wizard remembers your last location, party size and preference (`~/.swiggy-deals/config.json`) and offers them as defaults next time.

### Flags

| Flag | What it does |
|---|---|
| `-l, --location` | area name or `lat,lng` |
| `-p, --people` | number of people eating |
| `--veg {veg,nonveg,both}` | food preference |
| `-r, --restaurant` | only restaurants whose name contains this |
| `--limit N` | rows to show (default 25) |
| `--json` | print results as JSON and exit |
| `--no-color` | plain output (also automatic when piped) |
| `--insecure` | skip TLS verification |
| `--login` / `--logout` | manage the saved Swiggy session |

## How It Works

```
Step 1: Location       →  "Manipal" or "13.344,74.786"
Step 2: People count   →  how many eating
Step 3: Veg/Non-veg    →  filter preference
Step 4: Restaurant     →  optional name filter
         ↓
   Sorted results table with estimated checkout prices
         ↓
   Select a restaurant number → full menu with categories
         ↓
   Select an item number → price breakdown + variants + add-ons
```

## Features

**Price estimation** — Shows what you'll actually pay, not just the menu price. Uses the restaurant's real delivery fee from Swiggy's payload when available (flat ~₹25 estimate otherwise), plus GST (5%), platform fee (~₹7), packaging (~₹15), and small order fee (₹30 if under ₹150). Free-delivery offers actually zero out the delivery fee in the estimate.

**Discount parsing** — Handles the common Swiggy offer formats: percent with cap, flat off, BOGO, items at fixed price, free delivery. Anything unrecognized is shown as-is and priced conservatively.

**Menu browser** — Full interactive menu with:
- Category filtering (Breads, Curries, Desserts, etc.)
- Per-item estimated checkout price
- Item detail view with complete price breakdown
- Variant prices (Regular/Medium/Large)
- Add-on prices with recalculated totals
- Bestseller and rating badges

**Login support** — Auto-extracts cookies from Chrome or Firefox for:
- More restaurants (full pagination vs ~20-30 without login)
- Personal offers and Swiggy One benefits

**Filters** — Filter by restaurant name or max budget, page through more results with `m`, change location or party size with `n` — all without restarting.

## Login

The script can auto-extract your Swiggy session from Chrome or Firefox. Just be logged into swiggy.com in your browser and run `python3 swiggy_deals.py --login`.

On macOS, Chrome will ask for Keychain access the first time — click Allow.

If auto-login doesn't work, you can manually paste cookies from browser DevTools (F12 → Console → `document.cookie`). The saved session lives in `~/.swiggy-deals/` with owner-only permissions.

## Limitations

The estimated total is an approximation. It can't account for:
- Surge pricing (rain, peak hours)
- Payment-specific offers (HDFC, Paytm, UPI discounts)
- Cart-level coupon codes
- Delivery fee for restaurants that don't include it in the listing payload (falls back to ~₹25)

The tool tells you this in the output. Use it to find cheap options fast, then check the actual Swiggy app for the exact total.

Unofficial — talks to the same endpoints the Swiggy website uses, which can change without notice. For personal use.
