"""
Per-site access control (Phase 4).

Admins are unrestricted. Viewers see only the sites assigned to them
(user.sites). Routes call resolve_site()/scope_filter() so a viewer can never
read another site's data — enforced server-side regardless of the UI.
"""
from flask import g, abort

from services import auth


def allowed_sites():
    """None = unrestricted (admin / public). Otherwise a set of allowed site ids."""
    u = getattr(g, "user", None)
    if not u or u.get("role") == "admin":
        return None
    return set(auth.get_user_sites(u["username"]) or [])


def resolve_site(requested):
    """Effective site for this request. abort(403) if a viewer requests a site
    they aren't assigned. Returns a site id or None (None → caller's default)."""
    allowed = allowed_sites()
    if allowed is None:
        return requested                      # admin: honor request (may be None)
    if requested:
        if requested not in allowed:
            abort(403)
        return requested
    return next(iter(sorted(allowed)), None)  # viewer with no param → first allowed


def scope_filter():
    """Mongo filter fragment limiting a query to allowed sites ({} for admins)."""
    allowed = allowed_sites()
    return {} if allowed is None else {"site_id": {"$in": list(allowed)}}
