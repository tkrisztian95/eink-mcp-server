# GitHub Profile — E-ink Display Prompt

Use this prompt to render any GitHub profile card on the e-ink display.
Replace `<username>` with the target GitHub username before running.

---

## Prompt

Draw the GitHub profile for **`<username>`** on the e-ink display.

### Step 1 — Download the GitHub logo

Download the official GitHub Mark (black, PNG) and save it locally:

```
https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png
```

Save to: `/tmp/github-mark.png`

Use `curl -L -o /tmp/github-mark.png <url>` via Bash.

### Step 2 — Gather profile data

Fetch these two GitHub API endpoints (no auth needed for public data).
Run both requests in parallel.

```
GET https://api.github.com/users/<username>
GET https://api.github.com/users/<username>/events?per_page=100
```

Extract from the profile response:
- `name`         → display name
- `login`        → username
- `bio`          → bio line
- `company`      → company
- `location`     → location
- `public_repos` → repo count
- `followers`    → follower count
- `following`    → following count
- `public_gists` → gist count

From the events response, aggregate event counts by day using the `created_at` field (date part only, `YYYY-MM-DD`). Produce the **last 7 calendar days** (today inclusive, fill missing days with 0). Format as:

```json
[
  { "label": "Mon", "value": 3 },
  { "label": "Tue", "value": 7 },
  ...
]
```

Use the 3-letter weekday abbreviation (Mon/Tue/Wed/Thu/Fri/Sat/Sun) as the label, sorted oldest → newest.

### Step 3 — Render with `render_layout`

Call `mcp__eink-display__render_layout` with `padding=22` and these sections in order:

| # | type | key fields |
|---|------|-----------|
| 1 | `header` | `title`: `" GitHub  /  <login>"`, `subtitle`: full name |
| 2 | `divider` | `bold: true`, `margin_before: 2`, `margin_after: 6` |
| 3 | `text_row` | `left`: `"✦ <bio>"`, `size: "label"`, `bold: true` |
| 4 | `spacer` | `height: 4` |
| 5 | `text_row` | `left`: `"⬡  <company>"`, `right`: `"◎  <location>"`, `size: "value"` |
| 6 | `divider` | `light: true`, `margin_before: 8`, `margin_after: 8` |
| 7 | `text_row` | `left`: `"REPOS"`, `right`: `"FOLLOWERS"`, `size: "tiny"`, `bold: true` |
| 8 | `text_row` | `left`: repo count, `right`: follower count, `size: "large"`, `bold: true` |
| 9 | `spacer` | `height: 2` |
| 10 | `text_row` | `left`: `"FOLLOWING"`, `right`: `"GISTS"`, `size: "tiny"`, `bold: true` |
| 11 | `text_row` | `left`: following count, `right`: gist count, `size: "large"`, `bold: true` |
| 12 | `divider` | `bold: true`, `margin_before: 8`, `margin_after: 6` |
| 13 | `bar_chart` | `title`: `"Activity — last 7 days"`, `data`: the 7-day array from Step 2 |

`bar_chart` must always be the **last** section.

### Notes

- Run Step 1 and Step 2 in parallel (they are independent).
- Use the live API data for all values — do not hardcode any stats.
- If `bio`, `company`, or `location` is null, omit that row.
- If the logo download fails, omit the `image_block` and keep the header text as-is.
