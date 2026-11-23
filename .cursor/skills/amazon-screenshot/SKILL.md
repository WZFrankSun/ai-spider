---
name: amazon-screenshot
description: >-
  Trigger the default Amazon product screenshot check through the API.
  Use when the user wants to run the built-in screenshot judgment,
  触发默认商品, or POST /api/screenshots with an empty body.
---

# Amazon screenshot API

Service base URL: `http://127.0.0.1:28000`. Trigger only the built-in product list. Do not pass `tasks`.

## Trigger

```bash
curl -X POST http://127.0.0.1:28000/api/screenshots \
  -H 'content-type: application/json' \
  -d '{}'
```

The response is `202` with a `job_id`. The check runs in the background. A `409` means a job is already running; poll the `job_id` in that response.

## Read the judgment

Poll `GET /api/screenshots/{job_id}` until `status` is `succeeded` or `failed`.

Use `summary.items`. For each item, `present` is the Add to Basket judgment:

- `true`: the button is visible.
- `false`: the button is missing.
- `null`: the check did not finish. Read `error`.
