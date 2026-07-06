# Free Storefront Launch Checklist

Use this before publishing a small digital product page.

## Buyer Readiness

- The page returns HTTP 200.
- The product title explains what the buyer gets.
- The price is visible near the first call to action.
- There is one clear payment or checkout link.
- There is a support email or buyer help path.
- The page says what happens after payment.
- A free sample, preview, screenshot, or demo is linked.
- Refund or support terms are visible.
- Private payment details are never requested in public.

## Trust Signals

- The page has a real title and meta description.
- Open Graph title, description, and image are set.
- The README or docs match the public page.
- The delivery ZIP has a README.
- The ZIP has been opened and checked before publishing.
- The product clearly says what it is not for.

## Safe Scope

Do not sell or request security, vulnerability, exploit, bypass, jailbreak, credential, spam, fake-review, or personal-data scraping work.

## Quick Test

Run the free checker:

```bash
python3 storefront_checker.py https://your-site.example/ --fail-under 12
```

Free checker:

https://github.com/duct-tape2/ai-money-stack/blob/main/storefront_checker.py

Paid starter kit:

https://duct-tape2.github.io/storefront-starter/
