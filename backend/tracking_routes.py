"""
Tracking API Routes - Scaled for large deployments.
Uses downsampled data for ranges > 6h.
Gap detection: inserts null points when client is disconnected.
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone, timedelta
from bson import json_util
import json

tracking_bp = Blueprint("tracking", __name__)
_db = None

def init_tracking(mongo_db):
    global _db
    _db = mongo_db

def _parse_range(range_str):
    now = datetime.now(timezone.utc)
    ranges = {
        "last30m": now - timedelta(minutes=30),
        "last1h": now - timedelta(hours=1),
        "last2h": now - timedelta(hours=2),
        "last6h": now - timedelta(hours=6),
        "last12h": now - timedelta(hours=12),
        "last24h": now - timedelta(hours=24),
        "last7d": now - timedelta(days=7),
        "last30d": now - timedelta(days=30),
    }
    if range_str == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return ranges.get(range_str, now - timedelta(hours=2))

def _collection_for_range(range_str):
    """Use downsampled collection for longer ranges."""
    if range_str in ("last7d", "last30d"):
        return "client_snapshots_5m"
    return "client_snapshots"

def _gap_threshold_for_range(range_str):
    """Max seconds between points before inserting a gap.
    ~2.5x the expected poll interval for that collection."""
    if range_str in ("last7d", "last30d"):
        return 750   # 5m averages -> gap if >12.5 min
    return 150        # 60s polls -> gap if >2.5 min

def _serialize(docs):
    result = json.loads(json_util.dumps(docs))
    for doc in result:
        if isinstance(doc.get("_id"), dict) and "$oid" in doc["_id"]:
            doc["_id"] = doc["_id"]["$oid"]
        for field in ("timestamp", "first_seen", "last_seen"):
            if isinstance(doc.get(field), dict) and "$date" in doc[field]:
                doc[field] = doc[field]["$date"]
    return result

def _insert_gaps(docs, gap_threshold_sec):
    """Insert null-value gap markers between points that are too far apart.
    This tells Chart.js to break the line when a client was disconnected."""
    if len(docs) < 2:
        return docs

    result = [docs[0]]
    null_fields = ("rssi_dbm", "snr_db", "quality_score", "quality_label",
                   "data_rate_mbps", "data_retries")

    for i in range(1, len(docs)):
        prev_ts = docs[i - 1].get("timestamp")
        curr_ts = docs[i].get("timestamp")

        if prev_ts and curr_ts:
            try:
                delta = (curr_ts - prev_ts).total_seconds()
            except (TypeError, AttributeError):
                delta = 0

            if delta > gap_threshold_sec:
                # Insert null gap 1s after last real point
                gap1 = {"timestamp": prev_ts + timedelta(seconds=1),
                         "ap_name": docs[i - 1].get("ap_name", ""),
                         "_gap": True}
                for f in null_fields:
                    gap1[f] = None
                result.append(gap1)

                # Insert null gap 1s before reconnect point
                gap2 = {"timestamp": curr_ts - timedelta(seconds=1),
                         "ap_name": docs[i].get("ap_name", ""),
                         "_gap": True}
                for f in null_fields:
                    gap2[f] = None
                result.append(gap2)

        result.append(docs[i])

    return result


@tracking_bp.route("/api/tracking/clients")
def tracked_clients():
    """List unique tracked clients (last 24h only for performance)."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    pipe = [
        {"$match": {"timestamp": {"$gte": since}}},
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$mac", "mac": {"$first": "$mac"},
            "hostname": {"$first": {"$ifNull": ["$hostname", ""]}},
            "username": {"$first": {"$ifNull": ["$username", ""]}},
            "ip": {"$first": {"$ifNull": ["$ip", ""]}},
            "ap_name": {"$first": "$ap_name"}, "ssid": {"$first": "$ssid"},
            "band": {"$first": "$band"},
            "rssi_dbm": {"$first": "$rssi_dbm"},
            "quality_score": {"$first": "$quality_score"},
            "last_seen": {"$first": "$timestamp"},
            "first_seen": {"$last": "$timestamp"},
            "snapshot_count": {"$sum": 1},
        }},
        {"$sort": {"last_seen": -1}},
        {"$limit": 500},
    ]
    try:
        return jsonify(_serialize(list(_db["client_snapshots"].aggregate(pipe, allowDiskUse=True))))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@tracking_bp.route("/api/tracking/client/<mac>/timeline")
def client_timeline(mac):
    time_range = request.args.get("range", "last2h")
    since = _parse_range(time_range)
    coll = _collection_for_range(time_range)

    max_points = 500
    docs = list(_db[coll].find(
        {"mac": mac.lower(), "timestamp": {"$gte": since}},
        {"_id": 0, "timestamp": 1, "rssi_dbm": 1, "snr_db": 1,
         "quality_score": 1, "quality_label": 1, "data_rate_mbps": 1,
         "ap_name": 1, "ssid": 1, "band": 1, "channel": 1,
         "data_retries": 1}
    ).sort("timestamp", 1))

    # Downsample if too many points
    if len(docs) > max_points:
        step = len(docs) // max_points
        docs = docs[::step]

    # Insert gap markers where client was disconnected
    gap_threshold = _gap_threshold_for_range(time_range)
    docs = _insert_gaps(docs, gap_threshold)

    return jsonify({"mac": mac, "range": time_range, "since": since.isoformat(),
                     "count": len(docs), "timeline": _serialize(docs)})

@tracking_bp.route("/api/tracking/client/<mac>/roaming")
def client_roaming(mac):
    time_range = request.args.get("range", "last24h")
    since = _parse_range(time_range)
    docs = list(_db["roaming_events"].find(
        {"mac": mac.lower(), "timestamp": {"$gte": since}}, {"_id": 0}
    ).sort("timestamp", 1).limit(200))
    return jsonify({"mac": mac, "range": time_range, "count": len(docs),
                     "events": _serialize(docs)})

@tracking_bp.route("/api/tracking/client/<mac>/summary")
def client_summary(mac):
    time_range = request.args.get("range", "last2h")
    since = _parse_range(time_range)
    coll = _collection_for_range(time_range)
    pipe = [
        {"$match": {"mac": mac.lower(), "timestamp": {"$gte": since}}},
        {"$group": {
            "_id": None, "count": {"$sum": 1},
            "avg_rssi": {"$avg": "$rssi_dbm"}, "min_rssi": {"$min": "$rssi_dbm"}, "max_rssi": {"$max": "$rssi_dbm"},
            "avg_snr": {"$avg": "$snr_db"}, "min_snr": {"$min": "$snr_db"}, "max_snr": {"$max": "$snr_db"},
            "avg_quality": {"$avg": "$quality_score"}, "min_quality": {"$min": "$quality_score"}, "max_quality": {"$max": "$quality_score"},
            "avg_rate": {"$avg": "$data_rate_mbps"}, "max_rate": {"$max": "$data_rate_mbps"},
            "total_retries": {"$max": "$data_retries"},
            "aps_used": {"$addToSet": "$ap_name"}, "ssids_used": {"$addToSet": "$ssid"},
            "bands_used": {"$addToSet": "$band"}, "channels_used": {"$addToSet": "$channel"},
            "first_seen": {"$min": "$timestamp"}, "last_seen": {"$max": "$timestamp"},
        }},
    ]
    try:
        results = list(_db[coll].aggregate(pipe))
        if not results: return jsonify({"mac": mac, "count": 0})
        s = results[0]; del s["_id"]
        s["mac"] = mac; s["range"] = time_range
        s["roam_count"] = _db["roaming_events"].count_documents(
            {"mac": mac.lower(), "timestamp": {"$gte": since}})
        for k in ("avg_rssi","min_rssi","max_rssi","avg_snr","min_snr","max_snr",
                   "avg_quality","min_quality","max_quality","avg_rate","max_rate"):
            if s.get(k) is not None: s[k] = round(s[k], 1)
        return jsonify(_serialize([s])[0])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@tracking_bp.route("/api/tracking/roaming")
def all_roaming():
    time_range = request.args.get("range", "last2h")
    since = _parse_range(time_range)
    docs = list(_db["roaming_events"].find(
        {"timestamp": {"$gte": since}}, {"_id": 0}
    ).sort("timestamp", -1).limit(200))
    return jsonify({"range": time_range, "count": len(docs), "events": _serialize(docs)})

@tracking_bp.route("/api/tracking/ap/<path:ap_name>/load")
def ap_load_history(ap_name):
    time_range = request.args.get("range", "last2h")
    since = _parse_range(time_range)
    docs = list(_db["ap_load_history"].find(
        {"ap_name": ap_name, "timestamp": {"$gte": since}}, {"_id": 0}
    ).sort("timestamp", 1).limit(500))
    return jsonify({"ap_name": ap_name, "range": time_range,
                     "count": len(docs), "history": _serialize(docs)})

@tracking_bp.route("/api/tracking/roaming/graph")
def roaming_graph():
    """Build a graph of AP nodes and roaming edges for D3 visualization."""
    time_range = request.args.get("range", "last2h")
    mac_filter = request.args.get("mac", "").strip().lower()
    since = _parse_range(time_range)

    match = {"timestamp": {"$gte": since}}
    if mac_filter:
        match["mac"] = {"$regex": mac_filter, "$options": "i"}

    try:
        # Aggregate roaming events into edges: from_ap -> to_ap with count
        edge_pipe = [
            {"$match": match},
            {"$group": {
                "_id": {"from": "$from_ap", "to": "$to_ap"},
                "count": {"$sum": 1},
                "macs": {"$addToSet": "$mac"},
                "avg_quality": {"$avg": "$quality_after"},
                "last_rssi": {"$last": "$rssi_after"},
            }},
            {"$sort": {"count": -1}},
            {"$limit": 200},
        ]
        edges = list(_db["roaming_events"].aggregate(edge_pipe, allowDiskUse=True))

        # Collect all AP names from edges
        ap_set = set()
        for e in edges:
            ap_set.add(e["_id"]["from"])
            ap_set.add(e["_id"]["to"])

        if not ap_set:
            return jsonify({"nodes": [], "links": []})

        # Current client count per AP: take each client's LATEST snapshot (its
        # current AP) and count distinct clients — not every snapshot row, which
        # would multiply by the number of polls in the window.
        now = datetime.now(timezone.utc)
        snap_since = now - timedelta(minutes=3)
        ap_stats_pipe = [
            {"$match": {"timestamp": {"$gte": snap_since}}},
            {"$sort": {"timestamp": -1}},
            {"$group": {                       # latest snapshot per client
                "_id": "$mac",
                "ap_name": {"$first": "$ap_name"},
                "quality": {"$first": "$quality_score"},
            }},
            {"$group": {                       # distinct current clients per AP
                "_id": "$ap_name",
                "client_count": {"$sum": 1},
                "avg_quality": {"$avg": "$quality"},
            }},
        ]
        ap_stats = {doc["_id"]: doc for doc in
                    _db["client_snapshots"].aggregate(ap_stats_pipe, allowDiskUse=True)}

        # Count roam events per AP (as source or destination)
        ap_roam_counts = {}
        for e in edges:
            f, t = e["_id"]["from"], e["_id"]["to"]
            ap_roam_counts[f] = ap_roam_counts.get(f, 0) + e["count"]
            ap_roam_counts[t] = ap_roam_counts.get(t, 0) + e["count"]

        # Build nodes
        nodes = []
        for ap in ap_set:
            stats = ap_stats.get(ap, {})
            nodes.append({
                "id": ap, "type": "ap", "label": ap,
                "client_count": stats.get("client_count", 0),
                "quality_avg": round(stats.get("avg_quality", 0) or 0, 1),
                "roam_count": ap_roam_counts.get(ap, 0),
            })

        # Build links
        links = []
        for e in edges:
            links.append({
                "source": e["_id"]["from"],
                "target": e["_id"]["to"],
                "count": e["count"],
                "mac": e["macs"][0] if len(e["macs"]) == 1 else None,
                "avg_quality": round(e["avg_quality"] or 0, 1),
                "last_rssi": e.get("last_rssi", 0),
            })

        return jsonify({"nodes": nodes, "links": links})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@tracking_bp.route("/api/tracking/status")
def collector_status():
    try:
        snap_count = _db["client_snapshots"].estimated_document_count()
        roam_count = _db["roaming_events"].estimated_document_count()
        ds_count = _db["client_snapshots_5m"].estimated_document_count()
        latest = _db["client_snapshots"].find_one(
            sort=[("timestamp", -1)], projection={"timestamp": 1, "_id": 0})
        return jsonify({"snapshots": snap_count, "downsampled": ds_count,
            "roaming_events": roam_count,
            "last_collection": latest["timestamp"].isoformat() if latest else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500