# And-Shand

Find the cheapest food on Swiggy for any location. Sorts restaurants by what you'll actually pay at checkout — not just the menu price.

## What It Does

- Enter any Indian location (name or lat/lng)
- Set how many people are eating and veg/non-veg preference
- Gets all restaurants delivering to that location from Swiggy
- Calculates estimated checkout price (menu price + GST + delivery + fees)
- Sorts cheapest first so you see the best deals immediately
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
python3 swiggy_deals.py
```

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

**Price estimation** — Shows what you'll actually pay, not just the menu price. Adds GST (5%), platform fee (~₹7), packaging (~₹15), delivery (~₹25), and small order fee (₹30 if under ₹150).

**Discount parsing** — Handles all Swiggy offer formats: percent with cap, flat off, BOGO, items at fixed price, free delivery.

**Menu browser** — Full interactive menu with:
- Category filtering (Breads, Curries, Desserts, etc.)
- Per-item estimated checkout price
- Item detail view with complete price breakdown
- Variant prices (Regular/Medium/Large)
- Add-on prices with updated totals
- Bestseller and rating badges

**Login support** — Auto-extracts cookies from Chrome/Firefox for:
- More restaurants (full pagination vs ~20 without login)
- Personal offers and Swiggy One benefits
- User-specific coupons

**Filters** — Filter results by restaurant name, max budget, or veg/non-veg at any point.

## Login

The script can auto-extract your Swiggy session from Chrome or Firefox. Just be logged into swiggy.com in your browser and run the script.

On macOS, Chrome will ask for Keychain access the first time — click Allow.

If auto-login doesn't work, you can manually paste cookies from browser DevTools (F12 → Console → `document.cookie`).

## Limitations

The estimated total is an approximation. It can't account for:
- Exact delivery fees (vary by distance)
- Surge pricing (rain, peak hours)
- Payment-specific offers (HDFC, Paytm, UPI discounts)
- Cart-level coupon codes

The tool tells you this in the output. Use it to find cheap options fast, then check the actual Swiggy app for the exact total.
