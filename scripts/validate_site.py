#!/usr/bin/env python3
"""Validate the Saravana Bhava public support and legal website."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PAGES = (
    "index.html",
    "privacy.html",
    "data-deletion.html",
    "contact.html",
    "sources.html",
    "disclaimer.html",
)
PACKAGE_NAME = "com.saravanabhava.murugan"
APP_VERSION = "1.1.0"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang = ""
        self.title_depth = 0
        self.title_parts: list[str] = []
        self.h1_count = 0
        self.main_count = 0
        self.has_charset = False
        self.has_viewport = False
        self.links: list[str] = []

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        if tag == "html":
            self.lang = attributes.get("lang", "").strip()
        elif tag == "title":
            self.title_depth += 1
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "main":
            self.main_count += 1
        elif tag == "meta":
            if "charset" in attributes:
                self.has_charset = bool(attributes["charset"].strip())
            if attributes.get("name", "").lower() == "viewport":
                self.has_viewport = bool(attributes.get("content", "").strip())
        elif tag == "a":
            href = attributes.get("href", "").strip()
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title" and self.title_depth:
            self.title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title_parts.append(data)


def validate_internal_link(page: Path, href: str) -> str | None:
    parsed = urlsplit(href)
    if parsed.scheme in {"http", "https", "tel"} or href.startswith("#"):
        return None
    if parsed.scheme == "mailto":
        address = unquote(parsed.path)
        return None if EMAIL_PATTERN.fullmatch(address) else f"invalid mailto address: {href}"
    if parsed.scheme or parsed.netloc:
        return f"unsupported or malformed link: {href}"

    target_text = unquote(parsed.path)
    if not target_text:
        return None
    target = (page.parent / target_text).resolve()
    try:
        target.relative_to(ROOT)
    except ValueError:
        return f"link escapes repository root: {href}"
    if target.is_dir():
        target = target / "index.html"
    if not target.exists():
        return f"missing internal target: {href}"
    return None


def main() -> int:
    failures: list[str] = []

    for relative_path in REQUIRED_PAGES:
        page = ROOT / relative_path
        if not page.is_file():
            failures.append(f"{relative_path}: required page is missing")
            continue

        text = page.read_text(encoding="utf-8")
        parser = PageParser()
        try:
            parser.feed(text)
            parser.close()
        except Exception as exc:  # HTMLParser errors are rare but should fail validation.
            failures.append(f"{relative_path}: HTML parsing failed: {exc}")
            continue

        if "<!doctype html" not in text.lower():
            failures.append(f"{relative_path}: missing HTML doctype")
        if not parser.lang:
            failures.append(f"{relative_path}: html language is missing")
        if not parser.has_charset:
            failures.append(f"{relative_path}: character encoding declaration is missing")
        if not parser.has_viewport:
            failures.append(f"{relative_path}: viewport metadata is missing")
        if not parser.title:
            failures.append(f"{relative_path}: document title is empty")
        if parser.main_count != 1:
            failures.append(f"{relative_path}: expected exactly one main landmark, found {parser.main_count}")
        if parser.h1_count != 1:
            failures.append(f"{relative_path}: expected exactly one h1, found {parser.h1_count}")

        for href in parser.links:
            problem = validate_internal_link(page, href)
            if problem:
                failures.append(f"{relative_path}: {problem}")

    for relative_path in ("index.html", "privacy.html", "data-deletion.html", "contact.html"):
        page = ROOT / relative_path
        if not page.is_file():
            continue
        text = page.read_text(encoding="utf-8")
        if PACKAGE_NAME not in text:
            failures.append(f"{relative_path}: package contract {PACKAGE_NAME!r} is missing")
        if APP_VERSION not in text:
            failures.append(f"{relative_path}: app version contract {APP_VERSION!r} is missing")

    if failures:
        print("Saravana Bhava site validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Saravana Bhava site validation passed for {len(REQUIRED_PAGES)} public pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
