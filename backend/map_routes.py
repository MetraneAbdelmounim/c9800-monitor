"""
AP Floor-Map routes — store building floor plans and AP marker placements.

The Catalyst 9800 RESTCONF API exposes no physical coordinates for APs, so the
floor-plan images and per-AP X/Y positions are kept here in MongoDB. Live AP
status / client counts are NOT stored — the frontend overlays those from the
existing /api/aps and /api/clients endpoints.

Reads require auth; writes require the admin role.

Collections:
  map_floors      { _id, name, building, order, image (data URL), updated_by, updated_at }
  map_placements  { _id, floor_id, ap_mac, ap_name, x, y }   # x,y are 0-100 percent
"""
from flask import Blueprint, request, jsonify, g
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId

from auth import require_auth, require_role

map_bp = Blueprint("map", __name__, url_prefix="/api/map")
_db = None

# Floor-plan images are stored as base64 data URLs. Cap to keep Mongo docs sane
# (~9 MB binary after base64); real floor plans are far smaller.
MAX_IMAGE_CHARS = 12_000_000


def init_map(mongo_db):
    global _db
    _db = mongo_db
    try:
        _db["map_placements"].create_index("floor_id")
        log_ready = True
    except Exception:
        log_ready = False
    return log_ready


def _oid(v):
    try:
        return ObjectId(v)
    except (InvalidId, TypeError):
        return None


def _floor_public(doc, include_image=False):
    out = {
        "id": str(doc["_id"]),
        "name": doc.get("name", ""),
        "building": doc.get("building", ""),
        "order": doc.get("order", 0),
        "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
    }
    if include_image:
        out["image"] = doc.get("image", "")
    return out


# ── Floors ─────────────────────────────────────────────
@map_bp.route("/floors", methods=["GET"])
@require_auth
def list_floors():
    """Lightweight list for the selector — excludes image blobs."""
    docs = list(_db["map_floors"].find().sort([("building", 1), ("order", 1), ("name", 1)]))
    return jsonify({"floors": [_floor_public(d) for d in docs]})


@map_bp.route("/floors/<fid>", methods=["GET"])
@require_auth
def get_floor(fid):
    oid = _oid(fid)
    if not oid:
        return jsonify({"error": "invalid id"}), 400
    doc = _db["map_floors"].find_one({"_id": oid})
    if not doc:
        return jsonify({"error": "not found"}), 404
    return jsonify(_floor_public(doc, include_image=True))


@map_bp.route("/floors", methods=["POST"])
@require_role("admin")
def create_floor():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    image = data.get("image") or ""
    if len(image) > MAX_IMAGE_CHARS:
        return jsonify({"error": "image too large (max ~9 MB)"}), 413
    doc = {
        "name": name,
        "building": (data.get("building") or "").strip(),
        "order": int(data.get("order") or 0),
        "image": image,
        "updated_by": g.user["username"],
        "updated_at": datetime.now(timezone.utc),
    }
    res = _db["map_floors"].insert_one(doc)
    doc["_id"] = res.inserted_id
    return jsonify(_floor_public(doc, include_image=True)), 201


@map_bp.route("/floors/<fid>", methods=["PUT"])
@require_role("admin")
def update_floor(fid):
    oid = _oid(fid)
    if not oid:
        return jsonify({"error": "invalid id"}), 400
    data = request.get_json(silent=True) or {}
    upd = {"updated_by": g.user["username"], "updated_at": datetime.now(timezone.utc)}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name cannot be empty"}), 400
        upd["name"] = name
    if "building" in data:
        upd["building"] = (data.get("building") or "").strip()
    if "order" in data:
        upd["order"] = int(data.get("order") or 0)
    if "image" in data:
        image = data.get("image") or ""
        if len(image) > MAX_IMAGE_CHARS:
            return jsonify({"error": "image too large (max ~9 MB)"}), 413
        upd["image"] = image
    res = _db["map_floors"].update_one({"_id": oid}, {"$set": upd})
    if res.matched_count == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify(_floor_public(_db["map_floors"].find_one({"_id": oid}), include_image=True))


@map_bp.route("/floors/<fid>", methods=["DELETE"])
@require_role("admin")
def delete_floor(fid):
    oid = _oid(fid)
    if not oid:
        return jsonify({"error": "invalid id"}), 400
    res = _db["map_floors"].delete_one({"_id": oid})
    if res.deleted_count == 0:
        return jsonify({"error": "not found"}), 404
    _db["map_placements"].delete_many({"floor_id": fid})
    return jsonify({"ok": True})


# ── Placements ─────────────────────────────────────────
@map_bp.route("/floors/<fid>/placements", methods=["GET"])
@require_auth
def get_placements(fid):
    docs = list(_db["map_placements"].find({"floor_id": fid}, {"_id": 0}))
    return jsonify({"floor_id": fid, "placements": docs})


@map_bp.route("/floors/<fid>/placements", methods=["PUT"])
@require_role("admin")
def save_placements(fid):
    """Bulk-replace all placements for a floor."""
    oid = _oid(fid)
    if not oid or not _db["map_floors"].find_one({"_id": oid}, {"_id": 1}):
        return jsonify({"error": "floor not found"}), 404
    data = request.get_json(silent=True) or {}
    clean = []
    for p in (data.get("placements") or []):
        mac = (p.get("ap_mac") or "").strip()
        if not mac:
            continue
        try:
            x = float(p.get("x"))
            y = float(p.get("y"))
        except (TypeError, ValueError):
            continue
        clean.append({
            "floor_id": fid,
            "ap_mac": mac,
            "ap_name": (p.get("ap_name") or "").strip(),
            "x": max(0.0, min(100.0, x)),
            "y": max(0.0, min(100.0, y)),
        })
    resp = [dict(c) for c in clean]          # copy before insert_many adds _id
    _db["map_placements"].delete_many({"floor_id": fid})
    if clean:
        _db["map_placements"].insert_many(clean)
    return jsonify({"floor_id": fid, "count": len(resp), "placements": resp})
