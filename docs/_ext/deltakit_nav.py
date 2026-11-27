# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Sphinx extension that builds the sidebar shared by the Deltakit documentation sites.

The Deltakit documentation is split across several sites: the main Deltakit site, and one site per
package, such as this one. Every site shows the same top-level entries in its sidebar, so readers
move between the sites as if they were one. The entry for the site being built expands into its
own table of contents, and every other entry links to the site that owns it.

A site names the entry it owns in ``deltakit_nav_current``, and the ``sidebar_deltakit_nav.html``
template renders the sidebar. The entries are defined here rather than in each site's
configuration, so that this file can move unchanged into a package every Deltakit site installs.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, NamedTuple

from sphinx.errors import ConfigError

if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from sphinx.config import Config

DOCS_URL = "https://deltakit-docs.riverlane.com"
MAIN_SITE_URL = f"{DOCS_URL}/en/{{channel}}"


class NavEntry(NamedTuple):
    """A top-level entry of the shared sidebar.

    Attributes:
        key: The name a site sets ``deltakit_nav_current`` to, to own this entry.
        title: The text the sidebar shows.
        url: The page the entry links to from the other sites. ``{channel}`` stands for the
            documentation version to link to: see `_channel`.
    """

    key: str
    title: str
    url: str


NAV = (
    NavEntry("home", "Home", f"{MAIN_SITE_URL}/index.html"),
    NavEntry("setup", "Setup", f"{MAIN_SITE_URL}/setup.html"),
    NavEntry("getting-started", "Getting Started", f"{MAIN_SITE_URL}/guide/getting_started.html"),
    NavEntry("examples", "Examples", f"{MAIN_SITE_URL}/examples/index.html"),
    # Each package's site is a Read the Docs subproject of the main site, served on its domain.
    NavEntry(
        "deltakit-compile",
        "deltakit-compile",
        f"{DOCS_URL}/projects/deltakit-compile/en/{{channel}}/index.html",
    ),
    # The deltakit-visualise guides are still part of the main site. Point this entry at the
    # package's own site once it has one.
    NavEntry(
        "deltakit-visualise", "deltakit-visualise", f"{MAIN_SITE_URL}/deltakit_visualise/index.html"
    ),
    NavEntry("reference-api", "Reference API", f"{MAIN_SITE_URL}/api.html"),
    NavEntry("contributing", "Contributing to Deltakit", f"{MAIN_SITE_URL}/CONTRIBUTING.html"),
)


def _channel() -> str:
    """Return the version of the other sites to link to.

    Documentation built for a release links to the released documentation of the other sites.
    Everything else, including local builds and pull request previews, links to their latest
    documentation.
    """
    if (
        os.environ.get("READTHEDOCS_VERSION") == "stable"
        or os.environ.get("READTHEDOCS_VERSION_TYPE") == "tag"
    ):
        return "stable"
    return "latest"


def _check_current(_app: Sphinx, config: Config) -> None:
    keys = [entry.key for entry in NAV]
    if config.deltakit_nav_current not in keys:
        msg = f"deltakit_nav_current must be one of {keys}, not {config.deltakit_nav_current!r}"
        raise ConfigError(msg)


def _add_nav(
    app: Sphinx, _pagename: str, _templatename: str, context: dict[str, Any], _doctree: object
) -> None:
    channel = _channel()
    context["deltakit_nav"] = [
        entry._replace(url=entry.url.format(channel=channel)) for entry in NAV
    ]
    context["deltakit_nav_current"] = app.config.deltakit_nav_current


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the extension with Sphinx."""
    app.add_config_value("deltakit_nav_current", None, "html", types=[str])
    app.connect("config-inited", _check_current)
    app.connect("html-page-context", _add_nav)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
