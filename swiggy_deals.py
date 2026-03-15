#!/usr/bin/env python3
"""Swiggy Cheapest Deals Finder — Interactive CLI with login support."""

import http.cookiejar
import json
import os
import re
import ssl
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

# ─── Colors ───────────────────────────────────────────────────────────────────

class C:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    WHITE = "\033[97m"
    RESET = "\033[0m"

def colored(text, color):
    return f"{color}{text}{C.RESET}"

# ─── SSL Context (macOS Python fix) ──────────────────────────────────────────

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ─── Session Config ──────────────────────────────────────────────────────────

SESSION_DIR = os.path.expanduser("~/.swiggy-deals")
COOKIE_FILE = os.path.join(SESSION_DIR, "cookies.txt")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")

# ─── Swiggy Session ─────────────────────────────────────────────────────────

class SwiggySession:
    """Manages authenticated Swiggy session with cookie persistence."""

    def __init__(self):
        os.makedirs(SESSION_DIR, exist_ok=True)
        self.cookie_jar = http.cookiejar.MozillaCookieJar(COOKIE_FILE)
        self.csrf_token = None
        self.logged_in = False

        # Build opener with cookie handling
        cookie_handler = urllib.request.HTTPCookieProcessor(self.cookie_jar)
        https_handler = urllib.request.HTTPSHandler(context=SSL_CTX)
        self.opener = urllib.request.build_opener(cookie_handler, https_handler)

        # Try loading saved session
        self._load_session()

    def _load_session(self):
        """Load cookies from disk if they exist."""
        if os.path.exists(COOKIE_FILE):
            try:
                self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
                if len(self.cookie_jar) > 0:
                    self.logged_in = True
            except Exception:
                self.logged_in = False

    def _save_session(self):
        """Save cookies to disk."""
        try:
            self.cookie_jar.save(ignore_discard=True, ignore_expires=True)
        except Exception:
            pass

    def _request(self, url, data=None, method=None, retries=2):
        """Make an HTTP request through the session."""
        headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.swiggy.com/",
            "Origin": "https://www.swiggy.com",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
            if isinstance(data, dict):
                data = json.dumps(data).encode()
            elif isinstance(data, str):
                data = data.encode()

        for attempt in range(retries + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                resp = self.opener.open(req, timeout=15)
                raw = resp.read().decode()
                if not raw:
                    return None
                return json.loads(raw)
            except urllib.error.HTTPError as e:
                if attempt < retries:
                    time.sleep(1)
                    continue
                return None
            except Exception:
                if attempt < retries:
                    time.sleep(1)
                    continue
                return None

    # ─── Login Flow ───────────────────────────────────────────────────────

    def _auto_extract_cookies(self):
        """Try to automatically extract Swiggy cookies from installed browsers.

        Uses browser_cookie3 to read cookies from Chrome, Firefox, Safari, Edge.
        On macOS, Chrome will trigger a Keychain prompt on first use — click Allow.
        Returns True if cookies were found and loaded.
        """
        try:
            import browser_cookie3
        except ImportError:
            return False

        # Try Chrome and Firefox only
        browsers = [
            ("Chrome", browser_cookie3.chrome),
            ("Firefox", browser_cookie3.firefox),
        ]

        for name, browser_fn in browsers:
            try:
                sys.stdout.write(f"\r  Checking {name}...")
                sys.stdout.flush()
                cj = browser_fn(domain_name=".swiggy.com")
                cookies = list(cj)
                if cookies:
                    self.cookie_jar.clear()
                    for c in cookies:
                        self.cookie_jar.set_cookie(c)
                    print(f"\r  Found {len(cookies)} Swiggy cookies in {name}!     ")
                    return True
            except Exception:
                continue

        print("\r  No Swiggy cookies found in any browser.       ")
        return False

    def _import_cookie_string(self, cookie_input):
        """Parse and import a manually pasted cookie string."""
        self.cookie_jar.clear()

        if "=" in cookie_input:
            pairs = cookie_input.split(";")
            for pair in pairs:
                pair = pair.strip()
                if "=" not in pair:
                    continue
                name, _, value = pair.partition("=")
                name = name.strip()
                value = value.strip()
                cookie = http.cookiejar.Cookie(
                    version=0, name=name, value=value,
                    port=None, port_specified=False,
                    domain=".swiggy.com", domain_specified=True,
                    domain_initial_dot=True,
                    path="/", path_specified=True,
                    secure=True, expires=int(time.time()) + 86400 * 30,
                    discard=False, comment=None, comment_url=None,
                    rest={}, rfc2109=False,
                )
                self.cookie_jar.set_cookie(cookie)
        else:
            cookie = http.cookiejar.Cookie(
                version=0, name="__SW", value=cookie_input,
                port=None, port_specified=False,
                domain=".swiggy.com", domain_specified=True,
                domain_initial_dot=True,
                path="/", path_specified=True,
                secure=True, expires=int(time.time()) + 86400 * 30,
                discard=False, comment=None, comment_url=None,
                rest={}, rfc2109=False,
            )
            self.cookie_jar.set_cookie(cookie)

    def _verify_session(self):
        """Verify cookies work and save if valid."""
        print(colored("  Verifying session...", C.DIM))
        data = self._request(
            "https://www.swiggy.com/dapi/restaurants/list/v5"
            "?lat=12.93&lng=77.62&page_type=DESKTOP_WEB_LISTING"
        )

        if not data or data.get("statusCode") != 0:
            print(colored("  Session invalid or expired.", C.RED))
            return False

        self.logged_in = True
        self._save_session()

        # Check login status
        is_logged = any(c.name == "_is_logged_in" and c.value == "true"
                        for c in self.cookie_jar)

        if is_logged:
            print(colored("  Login successful! Session saved.", C.GREEN + C.BOLD))
        else:
            print(colored("  Cookies saved! API access verified.", C.GREEN + C.BOLD))
            print(colored("  (Make sure you're logged in on swiggy.com for full access)", C.DIM))

        return True

    def login(self):
        """Login by auto-extracting or manually importing browser cookies."""
        print()
        print(colored("  " + "━" * 56, C.CYAN))
        print(colored("  SWIGGY LOGIN", C.BOLD + C.CYAN))
        print(colored("  " + "━" * 56, C.CYAN))
        print()
        print(colored("  Login unlocks:", C.DIM))
        print(colored("    + All restaurants (full pagination)", C.GREEN))
        print(colored("    + Your personal offers & coupons", C.GREEN))
        print(colored("    + Swiggy One benefits", C.GREEN))
        print(colored("    + Accurate delivery fees", C.GREEN))
        print()

        # Step 1: Try automatic extraction
        print(colored("  Attempting auto-login from browser...", C.YELLOW))
        print(colored("  (macOS may ask for Keychain access — click Allow)", C.DIM))
        print()

        if self._auto_extract_cookies():
            if self._verify_session():
                print()
                return True
            print(colored("  Auto-extracted cookies didn't work. Try manual.", C.YELLOW))
            print()

        # Step 2: Fall back to manual paste
        print(colored("  MANUAL LOGIN:", C.BOLD + C.YELLOW))
        print(colored("  1. Open swiggy.com in your browser and login", C.DIM))
        print(colored("  2. Press F12 > Console > type: document.cookie", C.DIM))
        print(colored("  3. Copy the entire output and paste below", C.DIM))
        print()

        cookie_input = input(colored("  Paste cookie string (Enter to skip): ", C.BOLD)).strip()
        if not cookie_input:
            print(colored("  Skipped. Continuing without login.", C.DIM))
            print()
            return False

        self._import_cookie_string(cookie_input)

        if self._verify_session():
            print()
            return True

        print(colored("  Try logging in on swiggy.com first, then retry.", C.DIM))
        print()
        return False

    def logout(self):
        """Clear saved session."""
        self.logged_in = False
        self.cookie_jar.clear()
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)
        print(colored("  Logged out. Session cleared.", C.GREEN))

    # ─── API Methods ──────────────────────────────────────────────────────

    def get(self, url, retries=2):
        """GET request through session."""
        return self._request(url, retries=retries)

    def post(self, url, data, retries=2):
        """POST request through session."""
        return self._request(url, data=data, retries=retries)

    def fetch_restaurants(self, lat, lng, veg_only=False, max_pages=5):
        """Fetch restaurant listings with pagination support."""
        seen = set()
        all_restaurants = []

        # Page 1: initial listing
        url = (
            f"https://www.swiggy.com/dapi/restaurants/list/v5"
            f"?lat={lat}&lng={lng}&is-seo-homepage-enabled=true"
            f"&page_type=DESKTOP_WEB_LISTING"
        )
        if veg_only:
            url += "&facets=catalog_cuisines%3AVeg"

        data = self.get(url)
        if not data or data.get("statusCode") != 0:
            return []

        # Update CSRF from response
        if data.get("csrfToken"):
            self.csrf_token = data["csrfToken"]

        page_offset = data.get("data", {}).get("pageOffset", {})
        new = self._collect_restaurants(data, seen, all_restaurants)

        sys.stdout.write(f"\r  Page 1: {new} restaurants found")
        sys.stdout.flush()

        # Paginate if logged in and more pages available
        if self.logged_in and page_offset.get("nextOffset"):
            for page_num in range(2, max_pages + 1):
                next_offset = page_offset.get("nextOffset", "")
                widget_offset = page_offset.get("widgetOffset", {})

                if not next_offset:
                    break

                payload = {
                    "lat": lat,
                    "lng": lng,
                    "nextOffset": next_offset,
                    "widgetOffset": widget_offset,
                    "filters": {},
                    "seoParams": {
                        "apiName": "FoodHomePage",
                        "pageType": "DESKTOP_WEB_LISTING",
                    },
                    "page_type": "DESKTOP_WEB_LISTING",
                }
                if veg_only:
                    payload["facets"] = {"catalog_cuisines": [{"value": "Veg"}]}

                page_data = self.post(
                    "https://www.swiggy.com/dapi/restaurants/list/update",
                    data=payload
                )

                if not page_data or page_data.get("statusCode") != 0:
                    break

                new = self._collect_restaurants(page_data, seen, all_restaurants)
                page_offset = page_data.get("data", {}).get("pageOffset", {})

                sys.stdout.write(f"\r  Page {page_num}: +{new} restaurants (total: {len(all_restaurants)})")
                sys.stdout.flush()

                if new == 0:
                    break

                time.sleep(0.3)
        elif not self.logged_in:
            # Without login, try multiple sort orders
            for sort_by in ["COST_FOR_TWO", "DELIVERY_TIME", "RATING"]:
                sort_url = (
                    f"https://www.swiggy.com/dapi/restaurants/list/v5"
                    f"?lat={lat}&lng={lng}&page_type=DESKTOP_WEB_LISTING"
                    f"&sortBy={sort_by}"
                )
                if veg_only:
                    sort_url += "&facets=catalog_cuisines%3AVeg"

                sort_data = self.get(sort_url)
                if sort_data and sort_data.get("statusCode") == 0:
                    new = self._collect_restaurants(sort_data, seen, all_restaurants)
                    if new == 0:
                        break
                time.sleep(0.3)

        print()  # Newline after progress
        return all_restaurants

    def _collect_restaurants(self, data, seen, results):
        """Extract restaurants from API response, deduplicating."""
        new_count = 0
        cards = data.get("data", {}).get("cards", [])
        for card in cards:
            inner = card.get("card", {}).get("card", {})
            grid = (inner.get("gridElements", {})
                    .get("infoWithStyle", {})
                    .get("restaurants", []))
            for r in grid:
                info = r.get("info", {})
                rid = info.get("id")
                if rid and rid not in seen:
                    seen.add(rid)
                    results.append(info)
                    new_count += 1
        return new_count

    def fetch_menu(self, restaurant_id, lat, lng):
        """Fetch full menu for a restaurant."""
        url = (
            f"https://www.swiggy.com/mapi/menu/pl"
            f"?page-type=REGULAR_MENU&complete-menu=true"
            f"&lat={lat}&lng={lng}&restaurantId={restaurant_id}"
        )
        data = self.get(url)
        if not data or data.get("statusCode") != 0:
            return [], {}

        items = []
        rest_info = {}
        cards = data.get("data", {}).get("cards", [])

        for card in cards:
            info = card.get("card", {}).get("card", {}).get("info", {})
            if info.get("name") and info.get("id"):
                rest_info = {
                    "name": info.get("name", ""),
                    "cuisines": ", ".join(info.get("cuisines", [])),
                    "area": info.get("areaName", ""),
                    "cost_for_two": info.get("costForTwoMessage", ""),
                    "rating": info.get("avgRatingString", "?"),
                    "total_ratings": info.get("totalRatingsString", ""),
                    "delivery_time": info.get("sla", {}).get("slaString", "?"),
                }
                break

        for card in cards:
            _extract_menu_items(card, items)

        return items, rest_info


# Global session instance
session = SwiggySession()


def _extract_menu_items(obj, items, depth=0, current_category=""):
    """Recursively extract menu items from nested card structure."""
    if not isinstance(obj, dict) or depth > 15:
        return

    # Detect category titles from card headers
    title = (obj.get("title") or obj.get("card", {}).get("card", {}).get("title", "")
             or obj.get("card", {}).get("info", {}).get("title", ""))
    if title and isinstance(title, str) and len(title) < 60:
        cat_type = obj.get("@type", "") or obj.get("card", {}).get("card", {}).get("@type", "")
        if "ItemCategory" in cat_type or "NestedItemCategory" in cat_type or not cat_type:
            current_category = title

    info = obj.get("card", {}).get("info", {}) if "card" in obj else obj.get("info", {})
    if info.get("id") and info.get("name") and (info.get("price") or info.get("defaultPrice")):
        price = (info.get("price") or info.get("defaultPrice", 0)) / 100
        is_veg = (info.get("itemAttribute", {}).get("vegClassifier", "") == "VEG"
                  or info.get("isVeg") == 1)

        # Extract ratings
        ratings = info.get("ratings", {}).get("aggregatedRating", {})
        rating_val = ratings.get("rating", "")
        rating_count = ratings.get("ratingCountV2", "")

        # Extract addons
        addon_groups = []
        for ag in info.get("addons", []):
            group_name = ag.get("groupName", "")
            choices = []
            for ch in ag.get("choices", []):
                ch_price = (ch.get("price") or 0) / 100
                choices.append({
                    "name": ch.get("name", ""),
                    "price": ch_price,
                    "is_veg": ch.get("isVeg") == 1,
                })
            if choices:
                addon_groups.append({"name": group_name, "choices": choices})

        # Extract variants
        variants = []
        for vg in info.get("variantsV2", {}).get("variantGroups", []):
            group_name = vg.get("name", "")
            for v in vg.get("variations", []):
                v_price = (v.get("price") or 0) / 100
                variants.append({
                    "name": f"{group_name}: {v.get('name', '')}",
                    "price": v_price,
                    "default": v.get("default", False),
                })

        # Use category from info or from detected title
        category = info.get("category", "") or current_category or "Other"

        items.append({
            "name": info["name"],
            "price": price,
            "is_veg": is_veg,
            "description": info.get("description", "") or "",
            "category": category,
            "rating": rating_val,
            "rating_count": rating_count,
            "addon_groups": addon_groups,
            "variants": variants,
            "item_id": info.get("id"),
            "is_bestseller": info.get("isBestseller", False),
            "ribbon": info.get("ribbon", {}).get("text", ""),
        })
        return

    for key in ("card", "groupedCard", "cardGroupMap", "cards", "itemCards",
                "categories", "REGULAR", "carousel"):
        val = obj.get(key)
        if isinstance(val, dict):
            _extract_menu_items(val, items, depth + 1, current_category)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    _extract_menu_items(item, items, depth + 1, current_category)

# ─── Discount Parser ─────────────────────────────────────────────────────────

def parse_discount(discount_info):
    """Parse Swiggy's aggregatedDiscountInfoV3 into usable discount data."""
    if not discount_info:
        return None

    header = discount_info.get("header", "").upper()
    sub = discount_info.get("subHeader", "").upper()
    desc = f"{discount_info.get('header', '')} {discount_info.get('subHeader', '')}".strip()

    result = {"description": desc, "type": None, "percent": 0, "max_discount": 0,
              "flat_off": 0, "min_order": 0, "items_at": 0}

    min_match = re.search(r'ABOVE\s*₹?\s*(\d+)', sub) or re.search(r'ABOVE\s*₹?\s*(\d+)', header)
    if min_match:
        result["min_order"] = int(min_match.group(1))

    items_at = re.search(r'AT\s*₹?\s*(\d+)', sub) or re.search(r'AT\s*₹?\s*(\d+)', header)
    if items_at and "ITEMS" in (header + " " + sub):
        result["type"] = "items_at"
        result["items_at"] = int(items_at.group(1))
        return result

    pct_match = re.search(r'(\d+)%\s*OFF\s*(?:UPTO|UP\s*TO)\s*₹?\s*(\d+)', header + " " + sub)
    if pct_match:
        result["type"] = "percent_capped"
        result["percent"] = int(pct_match.group(1))
        result["max_discount"] = int(pct_match.group(2))
        return result

    pct_h = re.search(r'(\d+)%\s*OFF', header)
    cap_s = re.search(r'UPTO\s*₹?\s*(\d+)', sub)
    if pct_h and cap_s:
        result["type"] = "percent_capped"
        result["percent"] = int(pct_h.group(1))
        result["max_discount"] = int(cap_s.group(1))
        return result

    if pct_h:
        result["type"] = "percent"
        result["percent"] = int(pct_h.group(1))
        return result

    flat_match = re.search(r'FLAT\s*₹?\s*(\d+)\s*OFF', header)
    if flat_match:
        result["type"] = "flat"
        result["flat_off"] = int(flat_match.group(1))
        return result

    off_match = re.search(r'₹\s*(\d+)\s*OFF', header)
    if off_match:
        result["type"] = "flat"
        result["flat_off"] = int(off_match.group(1))
        return result

    if "BUY 1 GET 1" in header or "BOGO" in header or "B1G1" in header:
        result["type"] = "bogo"
        return result

    if "FREE DELIVERY" in header:
        result["type"] = "free_delivery"
        return result

    result["type"] = "unknown"
    return result

def apply_discount(original_price, discount):
    """Calculate price after applying discount. Returns (final_price, savings)."""
    if not discount or discount["type"] is None or discount["type"] in ("unknown", "free_delivery"):
        return original_price, 0

    if discount["min_order"] and original_price < discount["min_order"]:
        return original_price, 0

    if discount["type"] == "items_at":
        return original_price, 0

    if discount["type"] == "percent_capped":
        saving = min(original_price * discount["percent"] / 100, discount["max_discount"])
        return original_price - saving, saving

    if discount["type"] == "percent":
        saving = original_price * discount["percent"] / 100
        return original_price - saving, saving

    if discount["type"] == "flat":
        saving = min(discount["flat_off"], original_price)
        return original_price - saving, saving

    if discount["type"] == "bogo":
        saving = original_price * 0.5
        return original_price - saving, saving

    return original_price, 0

# ─── Checkout Estimator ──────────────────────────────────────────────────────

GST_RATE = 0.05
PLATFORM_FEE = 7.0
AVG_PACKAGING = 15.0
AVG_DELIVERY_FEE = 25.0
SMALL_ORDER_THRESHOLD = 150
SMALL_ORDER_FEE = 30.0

def estimate_checkout_price(discounted_price):
    gst = discounted_price * GST_RATE
    extras = PLATFORM_FEE + AVG_PACKAGING + AVG_DELIVERY_FEE
    if discounted_price < SMALL_ORDER_THRESHOLD:
        extras += SMALL_ORDER_FEE
    return discounted_price + gst + extras

# ─── Geocoding ────────────────────────────────────────────────────────────────

def geocode_location(query):
    encoded = urllib.parse.quote(query + ", India")
    url = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "SwiggyDealsFinder/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            results = json.loads(resp.read().decode())
            if results:
                display = results[0].get("display_name", query)
                parts = display.split(",")
                short = ", ".join(p.strip() for p in parts[:3])
                return float(results[0]["lat"]), float(results[0]["lon"]), short
    except Exception:
        pass
    return None, None, None

# ─── Display ──────────────────────────────────────────────────────────────────

def print_header():
    print()
    print(colored("━" * 56, C.CYAN))
    print(colored("  SWIGGY CHEAPEST DEALS FINDER", C.BOLD + C.CYAN))
    print(colored("━" * 56, C.CYAN))
    status = colored("  LOGGED IN", C.GREEN + C.BOLD) if session.logged_in else colored("  NOT LOGGED IN", C.DIM)
    print(f"  {status}")
    print()

def print_results(results, num_people):
    if not results:
        print(colored("\n  No results found matching your criteria.\n", C.YELLOW))
        return

    print()
    print(colored(f"  TOP CHEAPEST MEALS FOR {num_people} PEOPLE", C.BOLD + C.GREEN))
    print(colored("  " + "─" * 90, C.DIM))
    print()

    print(f"  {colored('#', C.DIM):>12}  "
          f"{colored('Restaurant', C.BOLD):<28}  "
          f"{colored('Cuisines', C.DIM):<24}  "
          f"{colored('Offer', C.YELLOW):<28}  "
          f"{colored('For ' + str(num_people), C.DIM):<14}  "
          f"{colored('After Disc.', C.GREEN):<18}  "
          f"{colored('Est. Total*', C.RED):<18}  "
          f"{colored('Save', C.MAGENTA):<14}  "
          f"{colored('Time', C.CYAN)}")
    print(f"  {'':>4}  {'─'*24}  {'─'*20}  {'─'*24}  {'─'*10}  {'─'*12}  {'─'*12}  {'─'*10}  {'─'*6}")

    for i, r in enumerate(results[:25], 1):
        name = r["name"][:24]
        cuisines = r.get("cuisines", "")[:20]
        offer = r.get("offer_text", "—")[:24]
        original = f"₹{r['original_price']:.0f}"
        final = f"₹{r['final_price']:.0f}"
        est = f"~₹{r['est_checkout']:.0f}"
        save = f"₹{r['savings']:.0f}" if r['savings'] > 0 else "—"
        dt = r.get("delivery_time", "?")

        offer_c = colored(offer, C.YELLOW) if offer != "—" else colored("—", C.DIM)
        final_c = colored(final, C.GREEN + C.BOLD)
        est_c = colored(est, C.RED)
        save_c = colored(save, C.MAGENTA) if save != "—" else colored("—", C.DIM)

        print(f"  {colored(str(i), C.DIM):>12}  "
              f"{name:<28}  "
              f"{colored(cuisines, C.DIM):<33}  "
              f"{offer_c:<37}  "
              f"{colored(original, C.DIM):<23}  "
              f"{final_c:<27}  "
              f"{est_c:<27}  "
              f"{save_c:<23}  "
              f"{colored(str(dt) + 'm', C.CYAN)}")

    print()
    print(colored(f"  Showing {min(len(results), 25)} of {len(results)} results", C.DIM))
    print()

    print(colored("  " + "─" * 90, C.DIM))
    print(colored("  * Est. Total = After Discount + GST (5%) + Platform Fee (~₹7) + Packaging (~₹15)", C.DIM))
    print(colored("                 + Delivery Fee (~₹25) + Small Order Fee (₹30 if under ₹150)", C.DIM))
    print()
    print(colored("  IMPORTANT — What this tool CAN'T show:", C.YELLOW + C.BOLD))
    print(colored("    - Exact delivery/packaging fees (vary by restaurant & distance)", C.DIM))
    print(colored("    - Surge pricing (rain, peak hours, high demand)", C.DIM))
    if not session.logged_in:
        print(colored("    - Swiggy One benefits (LOGIN to see these)", C.DIM))
        print(colored("    - User-specific coupons (LOGIN to see these)", C.DIM))
    print(colored("    - Payment offers (HDFC 10% off, Paytm cashback, UPI discounts)", C.DIM))
    print(colored("    - Cart-level coupon codes (PARTY, WELCOME50, etc.)", C.DIM))
    print()

def estimate_item_checkout(price):
    """Estimate checkout price for a single item (GST + fees)."""
    gst = price * GST_RATE
    extras = PLATFORM_FEE + AVG_PACKAGING + AVG_DELIVERY_FEE
    if price < SMALL_ORDER_THRESHOLD:
        extras += SMALL_ORDER_FEE
    return price + gst + extras

def print_item_detail(item):
    """Show full details for a selected menu item with final price breakdown."""
    print()
    print(colored("  " + "━" * 70, C.YELLOW))

    # Item name + badges
    badges = []
    if item.get("is_bestseller"):
        badges.append(colored(" BESTSELLER ", C.BOLD + C.YELLOW))
    if item.get("ribbon"):
        badges.append(colored(f" {item['ribbon']} ", C.BOLD + C.MAGENTA))
    badge_str = " ".join(badges)

    vt = colored("[VEG]", C.GREEN + C.BOLD) if item["is_veg"] else colored("[NON-VEG]", C.RED + C.BOLD)
    print(f"  {vt}  {colored(item['name'], C.BOLD + C.WHITE)}  {badge_str}")
    print(colored(f"  Category: {item.get('category', '—')}", C.DIM))

    # Rating
    if item.get("rating"):
        stars = item["rating"]
        count = item.get("rating_count", "")
        count_str = f" ({count})" if count else ""
        print(colored(f"  Rating: {stars}{count_str}", C.CYAN))

    print()

    # Description
    desc = item.get("description", "")
    if desc:
        # Word wrap at 65 chars
        words = desc.split()
        lines = []
        current = ""
        for w in words:
            if len(current) + len(w) + 1 > 65:
                lines.append(current)
                current = w
            else:
                current = f"{current} {w}" if current else w
        if current:
            lines.append(current)
        for line in lines:
            print(colored(f"  {line}", C.DIM))
        print()

    # Price breakdown
    base_price = item["price"]
    gst = base_price * GST_RATE
    total = estimate_item_checkout(base_price)

    print(colored("  PRICE BREAKDOWN", C.BOLD))
    print(colored("  " + "─" * 40, C.DIM))
    print(f"    Item price:          {colored(f'₹{base_price:.0f}', C.WHITE + C.BOLD)}")
    print(f"    GST (5%):            {colored(f'₹{gst:.0f}', C.DIM)}")
    print(f"    Platform fee:        {colored(f'~₹{PLATFORM_FEE:.0f}', C.DIM)}")
    print(f"    Packaging:           {colored(f'~₹{AVG_PACKAGING:.0f}', C.DIM)}")
    print(f"    Delivery:            {colored(f'~₹{AVG_DELIVERY_FEE:.0f}', C.DIM)}")
    if base_price < SMALL_ORDER_THRESHOLD:
        print(f"    Small order fee:     {colored(f'₹{SMALL_ORDER_FEE:.0f}', C.RED)}")
    print(colored("  " + "─" * 40, C.DIM))
    print(f"    {colored('Est. Total:', C.BOLD)}           {colored(f'~₹{total:.0f}', C.RED + C.BOLD)}")
    print()

    # Variants
    if item.get("variants"):
        print(colored("  VARIANTS", C.BOLD))
        print(colored("  " + "─" * 40, C.DIM))
        for v in item["variants"]:
            default_tag = colored(" (default)", C.GREEN) if v.get("default") else ""
            v_total = estimate_item_checkout(v["price"]) if v["price"] > 0 else total
            price_str = f"₹{v['price']:.0f}" if v["price"] > 0 else "Base price"
            print(f"    {v['name']:<35} {colored(price_str, C.BOLD)}  →  est. {colored(f'~₹{v_total:.0f}', C.RED)}{default_tag}")
        print()

    # Addons
    if item.get("addon_groups"):
        print(colored("  ADD-ONS", C.BOLD))
        print(colored("  " + "─" * 40, C.DIM))
        for ag in item["addon_groups"]:
            print(colored(f"  {ag['name']}:", C.YELLOW))
            for ch in sorted(ag["choices"], key=lambda x: x["price"]):
                vt2 = colored("[V]", C.GREEN) if ch["is_veg"] else colored("[N]", C.RED)
                if ch["price"] > 0:
                    addon_total = total + ch["price"] * 1.05  # addon also gets GST
                    print(f"    {vt2} {ch['name']:<32} +₹{ch['price']:.0f}  (total → ~₹{addon_total:.0f})")
                else:
                    print(f"    {vt2} {ch['name']:<32} FREE")
        print()

    print(colored("  " + "━" * 70, C.YELLOW))


def print_menu(items, rest_info, veg_pref, num_people):
    """Interactive menu viewer with category filtering and item selection."""

    # Apply veg filter once
    if veg_pref == "veg":
        all_items = [i for i in items if i["is_veg"]]
    elif veg_pref == "nonveg":
        all_items = [i for i in items if not i["is_veg"]]
    else:
        all_items = items[:]

    # Deduplicate
    seen = set()
    unique = []
    for item in all_items:
        key = (item["name"], item["price"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    if not unique:
        print(colored("  No items match your preference.", C.YELLOW))
        return

    # Build category map
    categories = {}
    for item in unique:
        cat = item.get("category", "") or "Other"
        categories.setdefault(cat, []).append(item)

    cat_names = sorted(categories.keys())
    active_category = None  # None = show all

    while True:
        # Determine which items to show
        if active_category:
            display_items = categories.get(active_category, [])
        else:
            display_items = unique

        sorted_items = sorted(display_items, key=lambda x: x["price"])

        # ── Header ──
        print()
        print(colored("  " + "━" * 70, C.CYAN))
        print(colored(f"  {rest_info.get('name', 'Restaurant')}", C.BOLD + C.CYAN))
        print(colored(f"  {rest_info.get('cuisines', '')}", C.DIM))
        rating = rest_info.get('rating', '?')
        total_r = rest_info.get('total_ratings', '')
        cost = rest_info.get('cost_for_two', '')
        dt = rest_info.get('delivery_time', '?')
        print(colored(f"  {rating} ({total_r})  |  {cost}  |  {dt}", C.DIM))
        print(colored("  " + "━" * 70, C.CYAN))

        if active_category:
            print(colored(f"  Showing: {active_category} ({len(sorted_items)} items)", C.YELLOW + C.BOLD))
        else:
            print(colored(f"  All items — {len(sorted_items)} total (sorted cheapest first)", C.BOLD))
        print()

        # ── Item list with est. total ──
        print(f"    {'#':>3}  {'Item':<38}  {'Price':>8}  {'Est.Total':>10}  {'':>4}  {'Rating':>8}  {'Info'}")
        print(f"    {'─'*3}  {'─'*38}  {'─'*8}  {'─'*10}  {'─'*4}  {'─'*8}  {'─'*20}")

        for i, item in enumerate(sorted_items[:50], 1):
            name = item["name"][:38]
            price = item["price"]
            est = estimate_item_checkout(price)
            veg_tag = colored("[V]", C.GREEN) if item["is_veg"] else colored("[N]", C.RED)

            # Badges
            info_parts = []
            if item.get("is_bestseller"):
                info_parts.append(colored("★ Bestseller", C.YELLOW))
            if item.get("ribbon"):
                info_parts.append(colored(item["ribbon"], C.MAGENTA))
            if item.get("variants"):
                info_parts.append(colored("has variants", C.DIM))
            if item.get("addon_groups"):
                info_parts.append(colored("+ add-ons", C.DIM))
            info_str = "  ".join(info_parts)

            rating_str = ""
            if item.get("rating"):
                rating_str = f"{item['rating']}"
                if item.get("rating_count"):
                    rating_str += f"({item['rating_count']})"

            print(f"    {colored(str(i), C.CYAN):>12}  {name:<38}  "
                  f"{colored(f'₹{price:.0f}', C.BOLD):>17}  "
                  f"{colored(f'~₹{est:.0f}', C.RED):>19}  "
                  f"{veg_tag}  "
                  f"{colored(rating_str, C.DIM):>8}  "
                  f"{info_str}")

        if len(sorted_items) > 50:
            print(colored(f"\n    ... and {len(sorted_items) - 50} more items", C.DIM))

        # ── Cheapest combo suggestion ──
        print()
        print(colored("  " + "─" * 70, C.DIM))
        combo = sorted_items[:num_people]
        combo_total = sum(item["price"] for item in combo)
        combo_est = estimate_checkout_price(combo_total)
        print(colored(f"  Cheapest combo for {num_people} (1 item each):", C.BOLD + C.GREEN))
        for item in combo:
            vt = colored("[V]", C.GREEN) if item["is_veg"] else colored("[N]", C.RED)
            p = item['price']
            print(f"    {vt} {item['name'][:45]:<45} ₹{p:.0f}")
        print(f"    {'─'*55}")
        print(f"    Subtotal: {colored(f'₹{combo_total:.0f}', C.GREEN + C.BOLD)}  |  "
              f"Est. checkout: {colored(f'~₹{combo_est:.0f}', C.RED)}")

        # ── Categories bar ──
        print()
        print(colored("  CATEGORIES:", C.BOLD))
        cat_display = []
        for ci, cn in enumerate(cat_names, 1):
            count = len(categories[cn])
            if active_category == cn:
                cat_display.append(colored(f"[{ci}. {cn} ({count})]", C.CYAN + C.BOLD))
            else:
                cat_display.append(f"{colored(str(ci), C.CYAN)}. {cn} ({count})")

        # Print categories in rows of 3
        for row_start in range(0, len(cat_display), 3):
            row = cat_display[row_start:row_start + 3]
            print(f"    {'    '.join(row)}")

        # ── Actions ──
        print()
        print(colored("  Actions:", C.BOLD))
        print(f"    {colored('1-' + str(min(len(sorted_items), 50)), C.CYAN)}  — Select item to see full details + final price")
        print(f"    {colored('c1-c' + str(len(cat_names)), C.CYAN)} — Filter by category (e.g. c1, c3)")
        print(f"    {colored('a', C.CYAN)}    — Show all categories")
        print(f"    {colored('Enter', C.CYAN)}  — Back to restaurant list")
        print()

        choice = input(colored("  Choice: ", C.BOLD)).strip().lower()

        if not choice:
            return

        # Category filter: c1, c2, etc.
        if choice.startswith("c") and len(choice) > 1:
            try:
                cat_idx = int(choice[1:])
                if 1 <= cat_idx <= len(cat_names):
                    active_category = cat_names[cat_idx - 1]
                else:
                    print(colored(f"  Pick c1 to c{len(cat_names)}.", C.RED))
            except ValueError:
                print(colored("  Invalid. Use c1, c2, etc.", C.RED))
            continue

        if choice == "a":
            active_category = None
            continue

        # Item selection
        try:
            idx = int(choice)
            if 1 <= idx <= min(len(sorted_items), 50):
                print_item_detail(sorted_items[idx - 1])
                input(colored("  Press Enter to go back...", C.DIM))
            else:
                print(colored(f"  Pick 1 to {min(len(sorted_items), 50)}.", C.RED))
        except ValueError:
            print(colored("  Invalid. Use a number, c1-c#, a, or Enter.", C.RED))

def filter_loop(results, num_people, lat, lng, veg_pref):
    budget_limit = None
    restaurant_filter = None

    while True:
        display = results[:]
        if restaurant_filter:
            display = [r for r in display if restaurant_filter.lower() in r["name"].lower()]
        if budget_limit:
            display = [r for r in display if r["est_checkout"] <= budget_limit]

        display.sort(key=lambda x: x["est_checkout"])
        print_results(display, num_people)

        active = []
        if restaurant_filter:
            active.append(f"restaurant: '{restaurant_filter}'")
        if budget_limit:
            active.append(f"budget: ≤₹{budget_limit:.0f}")
        if active:
            print(colored(f"  Active filters: {', '.join(active)}", C.DIM))
            print()

        print(colored("  What next?", C.BOLD))
        print(f"    {colored('1-' + str(len(display)), C.CYAN)} — Enter a number to see full menu")
        print(f"    {colored('f', C.CYAN)}   — Filter by restaurant name")
        print(f"    {colored('b', C.CYAN)}   — Set max budget (filters by Est. Total)")
        print(f"    {colored('s', C.CYAN)}   — Show all / clear filters")
        print(f"    {colored('v', C.CYAN)}   — Change veg/non-veg (re-fetch)")
        if not session.logged_in:
            print(f"    {colored('l', C.CYAN)}   — Login to Swiggy (more restaurants + offers)")
        else:
            print(f"    {colored('l', C.CYAN)}   — Logout")
        print(f"    {colored('q', C.CYAN)}   — Quit")
        print()

        choice = input(colored("  Choice: ", C.BOLD)).strip().lower()

        try:
            idx = int(choice)
            if 1 <= idx <= len(display):
                selected = display[idx - 1]
                rest_id = selected.get("rest_id")
                if not rest_id:
                    print(colored("  Restaurant ID not available.", C.RED))
                    continue
                print(colored(f"\n  Fetching menu for {selected['name']}...", C.YELLOW))
                items, rest_info = session.fetch_menu(rest_id, lat, lng)
                if items:
                    print_menu(items, rest_info, veg_pref, num_people)
                else:
                    print(colored("  Could not fetch menu.", C.RED))
                continue
            else:
                print(colored(f"  Pick a number between 1 and {len(display)}.", C.RED))
                continue
        except ValueError:
            pass

        if choice == "f":
            val = input(colored("  Restaurant name contains: ", C.BOLD)).strip()
            restaurant_filter = val if val else None
        elif choice == "b":
            try:
                budget_limit = float(input(colored("  Max budget (₹): ", C.BOLD)).strip())
            except ValueError:
                print(colored("  Invalid number.", C.RED))
        elif choice == "s":
            budget_limit = None
            restaurant_filter = None
            print(colored("  Filters cleared, showing all.", C.GREEN))
        elif choice == "v":
            return "refetch"
        elif choice == "l":
            if session.logged_in:
                session.logout()
            else:
                session.login()
            return "refetch"  # Re-fetch to get authenticated results
        elif choice == "q":
            print(colored("\n  Happy eating!\n", C.GREEN))
            return "quit"
        else:
            print(colored("  Invalid choice. Enter a number to view menu, or f/b/s/v/l/q.", C.RED))

# ─── Main ─────────────────────────────────────────────────────────────────────

def process_restaurants(restaurants, num_people, veg_pref):
    results = []

    for rest in restaurants:
        rest_name = rest.get("name", "Unknown")
        rest_id = rest.get("id")
        cuisines_list = rest.get("cuisines", [])
        cuisines = ", ".join(cuisines_list[:3])

        if veg_pref == "nonveg":
            veg_tags = {"Pure Veg", "Vegan"}
            if veg_tags & set(cuisines_list):
                continue

        cost_str = rest.get("costForTwo", "")
        cost_match = re.search(r'(\d+)', cost_str)
        cost_for_two = int(cost_match.group(1)) if cost_match else 500

        original = cost_for_two * num_people / 2

        discount_info = rest.get("aggregatedDiscountInfoV3") or rest.get("aggregatedDiscountInfoV2")
        discount = parse_discount(discount_info)
        offer_text = discount["description"] if discount else "—"

        if discount and discount["type"] == "items_at":
            items_price = discount["items_at"] * num_people
            final = items_price
            savings = original - items_price if original > items_price else 0
        else:
            final, savings = apply_discount(original, discount)

        est_checkout = estimate_checkout_price(final)

        results.append({
            "rest_id": rest_id,
            "name": rest_name,
            "original_price": original,
            "final_price": final,
            "est_checkout": est_checkout,
            "savings": savings,
            "offer_text": offer_text,
            "delivery_time": rest.get("sla", {}).get("deliveryTime", "?"),
            "cuisines": cuisines,
            "rating": rest.get("avgRating", "?"),
        })

    results.sort(key=lambda x: x["est_checkout"])
    return results

def main():
    print_header()

    # ── Login prompt ──
    if not session.logged_in:
        print(colored("  Tip: Login for more restaurants & personalized offers", C.DIM))
        login_choice = input(colored("  Login now? (y/N): ", C.BOLD)).strip().lower()
        if login_choice == "y":
            session.login()
        print()
    else:
        print(colored("  Using saved Swiggy session.", C.GREEN))
        print()

    # ── Step 1: Location ──
    print(colored("  Step 1: Location", C.BOLD))
    loc_input = input("  Enter lat,lng or area name: ").strip()

    if not loc_input:
        print(colored("  No location provided. Exiting.", C.RED))
        sys.exit(1)

    lat, lng, place_name = None, None, None
    if "," in loc_input:
        parts = loc_input.split(",")
        try:
            lat, lng = float(parts[0].strip()), float(parts[1].strip())
            place_name = loc_input
        except ValueError:
            pass

    if lat is None:
        print(colored("  Geocoding...", C.DIM))
        lat, lng, place_name = geocode_location(loc_input)

    if lat is None:
        print(colored("  Could not find that location. Try lat,lng format.", C.RED))
        sys.exit(1)

    print(colored(f"  > {place_name} ({lat:.4f}, {lng:.4f})", C.GREEN))
    print()

    # ── Step 2: Number of people ──
    print(colored("  Step 2: How many people?", C.BOLD))
    try:
        num_people = int(input("  Number of people eating: ").strip() or "2")
        if num_people < 1:
            num_people = 2
    except ValueError:
        num_people = 2
    print(colored(f"  > {num_people} people", C.GREEN))
    print()

    # ── Step 3: Veg/Non-veg ──
    print(colored("  Step 3: Food preference", C.BOLD))
    print(f"    {colored('1', C.CYAN)} Veg only")
    print(f"    {colored('2', C.CYAN)} Non-veg only")
    print(f"    {colored('3', C.CYAN)} Both (default)")
    veg_pref = "both"
    pref_input = input("  Choice [3]: ").strip()
    if pref_input == "1":
        veg_pref = "veg"
    elif pref_input == "2":
        veg_pref = "nonveg"
    print(colored(f"  > {veg_pref}", C.GREEN))
    print()

    # ── Step 4: Restaurant preference ──
    print(colored("  Step 4: Restaurant preference", C.BOLD))
    rest_pref = input("  Restaurant name (Enter to skip): ").strip()
    if rest_pref:
        print(colored(f"  > Searching for '{rest_pref}'", C.GREEN))
    else:
        print(colored("  > No preference", C.GREEN))
    print()

    # ── Fetch & Process loop ──
    while True:
        print(colored("  Fetching restaurants from Swiggy...", C.YELLOW))
        use_veg_filter = veg_pref == "veg"
        restaurants = session.fetch_restaurants(lat, lng, veg_only=use_veg_filter)

        if not restaurants:
            print(colored("  No restaurants found. Swiggy may be blocking requests.", C.RED))
            print(colored("  Try again in a minute, or use lat,lng format.", C.DIM))
            sys.exit(1)

        print(colored(f"  Found {len(restaurants)} restaurants delivering to your location", C.GREEN))
        if not session.logged_in:
            print(colored("  (Login for more — press 'l' in the menu)", C.DIM))

        if rest_pref:
            matches = [r for r in restaurants if rest_pref.lower() in r.get("name", "").lower()]
            if matches:
                print(colored(f"  {len(matches)} match '{rest_pref}'", C.GREEN))
                restaurants = matches
            else:
                print(colored(f"  No matches for '{rest_pref}', showing all", C.YELLOW))

        results = process_restaurants(restaurants, num_people, veg_pref)

        if not results:
            print(colored("  No results after filtering.", C.RED))
            sys.exit(1)

        action = filter_loop(results, num_people, lat, lng, veg_pref)
        if action == "refetch":
            print()
            print(colored("  Food preference:", C.BOLD))
            print(f"    {colored('1', C.CYAN)} Veg only")
            print(f"    {colored('2', C.CYAN)} Non-veg only")
            print(f"    {colored('3', C.CYAN)} Both")
            pref_input = input("  Choice [3]: ").strip()
            if pref_input == "1":
                veg_pref = "veg"
            elif pref_input == "2":
                veg_pref = "nonveg"
            else:
                veg_pref = "both"
            continue
        else:
            break

if __name__ == "__main__":
    main()
