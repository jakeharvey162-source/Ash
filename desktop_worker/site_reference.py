from __future__ import annotations

import html
import ipaddress
import re
import socket
from dataclasses import dataclass, asdict
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx


@dataclass
class SiteReference:
    url: str
    final_url: str
    title: str
    description: str
    headings: list[str]
    colors: list[str]
    fonts: list[str]
    radii: list[str]
    spacing: list[str]
    text_sample: str
    css_urls: list[str]

    def as_prompt_context(self, *, include_text: bool = False) -> str:
        payload = asdict(self)
        if not include_text:
            payload["text_sample"] = ""
        import json
        return json.dumps(payload, ensure_ascii=False, indent=2)[:12000]


class _ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self.headings: list[str] = []
        self.css_urls: list[str] = []
        self.inline_css: list[str] = []
        self.visible: list[str] = []
        self._tag = ""
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        self._tag = tag.lower()
        attrs = dict(attrs)
        if self._tag in {"script", "noscript", "svg", "canvas"}:
            self._skip += 1
        if self._tag == "meta" and str(attrs.get("name", "")).lower() == "description":
            self.description = str(attrs.get("content") or "")[:500]
        if self._tag == "link" and "stylesheet" in str(attrs.get("rel", "")).lower() and attrs.get("href"):
            self.css_urls.append(str(attrs["href"]))
        style = attrs.get("style")
        if style:
            self.inline_css.append(str(style))

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "noscript", "svg", "canvas"} and self._skip:
            self._skip -= 1
        self._tag = ""

    def handle_data(self, data):
        if self._skip:
            return
        text = re.sub(r"\s+", " ", html.unescape(str(data or ""))).strip()
        if not text:
            return
        if self._tag == "title" and not self.title:
            self.title = text[:180]
        if self._tag in {"h1", "h2", "h3"} and len(self.headings) < 20:
            self.headings.append(text[:220])
        if len(" ".join(self.visible)) < 16000:
            self.visible.append(text)


_PRIVATE_HOSTS = {
    "localhost", "localhost.localdomain", "metadata.google.internal",
    "169.254.169.254", "100.100.100.200",
}


def _validate_public_url(raw: str) -> str:
    url = str(raw or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Reference URL must be a public http(s) URL.")
    host = parsed.hostname.lower().rstrip(".")
    if host in _PRIVATE_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("Private/local reference URLs are not allowed.")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("Private/local reference URLs are not allowed.")
    except ValueError as exc:
        if "Private/local" in str(exc):
            raise
        # hostname, not an IP literal
        pass

    # Resolve once before the request to block common localhost/private DNS targets.
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        for info in infos:
            resolved = ipaddress.ip_address(info[4][0])
            if resolved.is_private or resolved.is_loopback or resolved.is_link_local or resolved.is_reserved or resolved.is_multicast:
                raise ValueError("Reference URL resolves to a private/local address.")
    except socket.gaierror as exc:
        raise ValueError("Reference host could not be resolved.") from exc
    return url


def _tokens(css: str) -> tuple[list[str], list[str], list[str], list[str]]:
    css = css[:120000]
    colors = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]{3,80}\)|hsla?\([^)]{3,80}\)", css)
    fonts = re.findall(r"font-family\s*:\s*([^;}{]{1,120})", css, flags=re.I)
    radii = re.findall(r"border-radius\s*:\s*([^;}{]{1,60})", css, flags=re.I)
    spacing = re.findall(r"(?:gap|padding|margin)\s*:\s*([^;}{]{1,80})", css, flags=re.I)

    def uniq(values, limit):
        out = []
        seen = set()
        for value in values:
            clean = re.sub(r"\s+", " ", value).strip()
            key = clean.lower()
            if not clean or key in seen:
                continue
            seen.add(key)
            out.append(clean[:120])
            if len(out) >= limit:
                break
        return out

    return uniq(colors, 16), uniq(fonts, 8), uniq(radii, 8), uniq(spacing, 10)


def capture_site_reference(raw_url: str, *, include_text: bool = False) -> SiteReference:
    url = _validate_public_url(raw_url)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AshReference/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }
    current = url
    html_text = ""
    final_url = current

    with httpx.Client(timeout=httpx.Timeout(18.0, connect=6.0), headers=headers, follow_redirects=False) as client:
        for _ in range(4):
            response = client.get(current)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise RuntimeError("Reference site redirected without a destination.")
                current = _validate_public_url(urljoin(current, location))
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                raise ValueError("Reference URL did not return a web page.")
            if len(response.content) > 2_500_000:
                raise ValueError("Reference page is too large to inspect safely.")
            html_text = response.text
            final_url = str(response.url)
            break
        else:
            raise RuntimeError("Reference site redirected too many times.")

        parser = _ReferenceParser()
        parser.feed(html_text)
        css_chunks = list(parser.inline_css)
        css_urls: list[str] = []
        for href in parser.css_urls[:6]:
            css_url = urljoin(final_url, href)
            try:
                css_url = _validate_public_url(css_url)
                css_response = client.get(css_url)
                if css_response.status_code == 200 and len(css_response.content) <= 600_000:
                    css_chunks.append(css_response.text[:600_000])
                    css_urls.append(css_url)
            except Exception:
                continue

    # Include style tags without preserving the source document itself.
    css_chunks.extend(re.findall(r"<style\b[^>]*>([\s\S]*?)</style>", html_text, flags=re.I)[:8])
    colors, fonts, radii, spacing = _tokens("\n".join(css_chunks))
    visible = re.sub(r"\s+", " ", " ".join(parser.visible)).strip()
    return SiteReference(
        url=url,
        final_url=final_url,
        title=parser.title,
        description=parser.description,
        headings=parser.headings[:12],
        colors=colors,
        fonts=fonts,
        radii=radii,
        spacing=spacing,
        text_sample=visible[:8000] if include_text else "",
        css_urls=css_urls[:6],
    )
