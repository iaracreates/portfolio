"""Builds the three language versions of the site from one template.

    python3 build.py

Reads src/template.html and the text files in i18n/, and writes:
    index.html          English
    pt-br/index.html    Português (Brasil)
    nl/index.html       Nederlands

To change wording, edit the matching i18n/*.json file and run the script again.
Template placeholders: {{key}} = text, {{@key}} = attribute value, {{!key}} = trusted HTML.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))

# Optional: the site's public address, e.g. "https://iaracreates.com".
# When set, each page gets hreflang links so search engines can match visitors to their language.
SITE_URL = ""

LANGS = [
    # code, folder, html lang, og locale, native name
    ("en", "", "en", "en_GB", "English"),
    ("pt-br", "pt-br", "pt-BR", "pt_BR", "Português (Brasil)"),
    ("nl", "nl", "nl", "nl_NL", "Nederlands"),
]
SCRIPT_KEYS = ("projects", "cats", "cert_dates", "skills", "ui")


def esc_text(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def esc_attr(s):
    return esc_text(s).replace('"', "&quot;")


def load(code):
    with open(os.path.join(ROOT, "i18n", code + ".json"), encoding="utf-8") as f:
        return json.load(f)


def render(template, values):
    missing = []

    def repl(m):
        kind, key = m.group(1), m.group(2)
        if key not in values:
            missing.append(key)
            return m.group(0)
        v = values[key]
        if kind == "!":
            return v
        return esc_attr(v) if kind == "@" else esc_text(v)

    out = re.sub(r"\{\{([@!]?)(\w+)\}\}", repl, template)
    if missing:
        raise SystemExit("missing text for: " + ", ".join(sorted(set(missing))))
    return out


def main():
    with open(os.path.join(ROOT, "src", "template.html"), encoding="utf-8") as f:
        template = f.read()
    english = load("en")

    for code, folder, html_lang, og_locale, _ in LANGS:
        text = load(code)
        # every language must cover every key English has
        gaps = [k for k in english if k not in text]
        if gaps:
            raise SystemExit(f"{code}.json is missing: {', '.join(gaps)}")

        base = "../" if folder else ""
        values = {k: v for k, v in text.items() if isinstance(v, str)}
        script_data = {k: text[k] for k in SCRIPT_KEYS}
        values.update({
            "base": base,
            "htmllang": html_lang,
            "og_locale": og_locale,
            "json": json.dumps(script_data, ensure_ascii=False).replace("</", "<\\/"),
            "hreflang": hreflang_tags(),
        })
        for other_code, other_folder, _, _, name in LANGS:
            href = base + (other_folder + "/" if other_folder else "")
            values["href_" + other_code.replace("-", "_")] = href or "./"
            values["current_" + other_code.replace("-", "_")] = ' aria-current="page"' if other_code == code else ""
        values["lang_code"] = {"en": "EN", "pt-br": "PT", "nl": "NL"}[code]

        out_dir = os.path.join(ROOT, folder) if folder else ROOT
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(render(template, values))
        print("built", os.path.relpath(os.path.join(out_dir, "index.html"), ROOT))


def hreflang_tags():
    if not SITE_URL:
        return ""
    site = SITE_URL.rstrip("/")
    tags = []
    for _, folder, html_lang, _, _ in LANGS:
        url = site + "/" + (folder + "/" if folder else "")
        tags.append(f'<link rel="alternate" hreflang="{html_lang}" href="{url}">')
    tags.append(f'<link rel="alternate" hreflang="x-default" href="{site}/">')
    return "\n".join(tags)


if __name__ == "__main__":
    main()
