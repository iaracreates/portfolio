# iara creates

Portfolio website of Iara Lucena, Content Designer & UX Writer in the Netherlands.

A static site in three languages, with no build step on the server:

| Language | Address | Text file |
|---|---|---|
| English | `/` | `i18n/en.json` |
| Português (Brasil) | `/pt-br/` | `i18n/pt-br.json` |
| Nederlands | `/nl/` | `i18n/nl.json` |

## How it's put together
- `src/template.html`: the page layout, styles and behaviour, shared by all languages.
- `i18n/*.json`: every word on the site, one file per language.
- `build.py`: combines the two into `index.html`, `pt-br/index.html` and `nl/index.html`.
- `src/details.html`: a "Project details" page design that any project can use. Each page's text lives in the
  `details` section of each `i18n` file, under the project's id (for example `details.buddy`).

## Project details pages
Which projects have a details page, and whether it's live, is set in `DETAILS_PAGES` near the top of `build.py`:

```python
"buddy": {"path": "projects/ai-buddy/", "image": "work-buddy.webp", "published": False},
```

- **Publish:** set `"published": True` and run `python3 build.py`. The page is written in all three languages and a
  small "More info" link appears at the end of that project's drawer.
- **Unpublish:** set it back to `False` and run the build. The pages and the link are removed; the text stays.
- **New project:** copy the `buddy` block in each `i18n` file's `details` section, rename it to the project's id
  (as used in `src/template.html`), rewrite the text, and add an entry to `DETAILS_PAGES`.

The AI Buddy details page is currently **unpublished**.
- `images/`: shared by all languages.

The generated `index.html` files are committed, so hosting only has to serve the files.

## Updating the site
1. Change wording in the `i18n` files, or layout in `src/template.html`.
2. Run `python3 build.py`. It stops with a message if any language is missing a piece of text.
3. Commit to `main`. Cloudflare Pages publishes every commit to `main` automatically.

To replace an image, keep the same file name in `images/`.

### Cloudflare Pages settings
- Framework preset: None
- Build command: `exit 0` (or leave empty)
- Build output directory: `/`

### Search engines
Once the site has its final address, set `SITE_URL` near the top of `build.py` and run it again.
Each page then tells search engines about its other language versions.
