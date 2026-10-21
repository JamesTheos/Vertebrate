"""
Data hub: keeps every consumed Kafka event (full message + Kafka key + Kafka timestamp) and
exposes the ISA-95 tree, per-topic event history and a merged live feed.

app.consume_messages() calls record_event() for every message; the PLC topic deques double as
data_store[topic] so /data/<topic> keeps working.
"""
import copy
import json
import math
import os
import socket
import threading
import time
from collections import deque
from urllib.parse import urlparse

from confluent_kafka.admin import AdminClient
from flask import Blueprint, jsonify, request
from sqlalchemy import text

from models import DesignSpaceSet, db
from utils import permission_required

MAX_EVENTS_PER_TOPIC = 5000
FEED_THROTTLE_MS = 2000      # numeric topics: at most one feed entry per topic per 2 s
ACTIVE_WINDOW_MS = 60_000    # "events in last 60 s"
API_PERMISSIONS = ('workflow-overview', 'order-management', 'pid', 'data-tree')

ORDERS_TOPIC = 'manufacturing_orders'

# Leaves of the ISA-95 unit, in display order: topic -> (display name, unit, kind)
TOPICS = {
    'ISPEMTemp': ('Material temperature', '°C', 'number'),
    'ISPESpeed': ('Filling speed', 'units/min', 'number'),
    'ISPEPressure': ('Pressure', 'bar', 'number'),
    'ISPEAmbTemp': ('Ambient temperature', '°C', 'number'),
    'ISPEStartPhase1': ('Start phase', '', 'bool'),
    'ISPEScene1': ('Simulation 1', '', 'bool'),
    'ISPEScene2': ('Simulation 2', '', 'bool'),
    ORDERS_TOPIC: ('Orders', '', 'order'),
}
VALUE_TOPICS = [t for t, (_, _, kind) in TOPICS.items() if kind != 'order']

SOURCES = {'FromPLC': 'PLC', 'FromUX': 'UX'}

_config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(_config_path) as _f:
    _config = json.load(_f)

ISA95_PATH = [
    ('Enterprise', _config['enterprise']),
    ('Site', _config['site']),
    ('Area', _config['area']),
    ('Process cell', _config['process_cell']),
    ('Unit', _config['unit']),
]

_lock = threading.Lock()
events = {topic: deque(maxlen=MAX_EVENTS_PER_TOPIC) for topic in TOPICS}

data_hub = Blueprint('data_hub', __name__)


# ── Store ────────────────────────────────────────────────────────────────────

def record_event(topic, kafka_key, kafka_timestamp, message):
    """Keep the whole message. 'timestamp' (Kafka ms) and 'value' keep the old /data/<topic> shape."""
    if topic not in events or not isinstance(message, dict):
        return
    entry = {
        'timestamp': kafka_timestamp,
        'value': message.get('status') if topic == ORDERS_TOPIC else message.get('value'),
        'kafka_key': kafka_key,
        'kafka_timestamp': kafka_timestamp,
        # copy: app.py keeps the same dict as live order state and mutates its status later
        'message': copy.deepcopy(message),
    }
    with _lock:
        events[topic].append(entry)


def snapshot(topic):
    with _lock:
        return list(events.get(topic, ()))


def latest(topic):
    with _lock:
        d = events.get(topic)
        return d[-1] if d else None


def now_ms():
    return int(time.time() * 1000)


# ── Formatting ───────────────────────────────────────────────────────────────

def source_of(entry):
    key = entry.get('kafka_key')
    return SOURCES.get(key, key)


def format_value(topic, value):
    name, unit, kind = TOPICS[topic]
    if value is None:
        return '–'
    if kind == 'bool':
        return 'TRUE' if value is True or str(value).lower() == 'true' else 'FALSE'
    if kind == 'number':
        try:
            return f'{float(value):.2f}' + (f' {unit}' if unit else '')
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def sentence(topic, entry):
    """One human-readable line per event for the live feed."""
    msg = entry['message']
    name, unit, kind = TOPICS[topic]
    order = msg.get('orderNumber')
    if kind == 'order':
        return f"Order {order} {entry['value']}"
    text = f'{name} → {format_value(topic, entry["value"])}' if kind == 'bool' \
        else f'{name} {format_value(topic, entry["value"])}'
    if kind == 'bool' and source_of(entry):
        text += f' ({source_of(entry)})'
    if order:
        text += f' · Order {order}'
    return text


def event_row(topic, entry):
    msg = entry['message']
    return {
        'topic': topic,
        'timestamp': entry['timestamp'],
        'value': entry['value'],
        'display_value': format_value(topic, entry['value']),
        'source': source_of(entry),
        'orderNumber': msg.get('orderNumber'),
        'product': msg.get('product'),
        'lotNumber': msg.get('lotNumber'),
        'health_status': msg.get('health_status'),
    }


def _limit(default, maximum):
    try:
        return max(1, min(int(request.args.get('limit', default)), maximum))
    except ValueError:
        return default


# ── API ──────────────────────────────────────────────────────────────────────

@data_hub.route('/api/tree')
@permission_required(*API_PERMISSIONS)
def api_tree():
    now = now_ms()
    leaves = []
    for topic, (name, unit, kind) in TOPICS.items():
        items = snapshot(topic)
        last = items[-1] if items else None
        recent = sum(1 for e in reversed(items) if now - e['timestamp'] <= ACTIVE_WINDOW_MS) if items else 0
        leaves.append({
            'topic': topic,
            'name': name,
            'unit': unit,
            'kind': kind,
            'value': last['value'] if last else None,
            'display_value': format_value(topic, last['value']) if last else None,
            'timestamp': last['timestamp'] if last else None,
            'orderNumber': last['message'].get('orderNumber') if last else None,
            'events_last_60s': recent,
        })

    # nest Enterprise > Site > Area > Process cell > Unit > leaves
    node = None
    for level, name in reversed(ISA95_PATH):
        node = {'level': level, 'name': name, 'children': leaves if node is None else [node]}
    return jsonify({
        'server_time': now,
        'path': [{'level': level, 'name': name} for level, name in ISA95_PATH],
        'tree': node,
    })


@data_hub.route('/api/topic/<topic>/events')
@permission_required(*API_PERMISSIONS)
def api_topic_events(topic):
    if topic not in TOPICS:
        return jsonify({'error': 'Unknown topic'}), 404
    limit = _limit(50, 500)
    rows = [event_row(topic, e) for e in reversed(snapshot(topic)[-limit:])]
    name, unit, kind = TOPICS[topic]
    return jsonify({'server_time': now_ms(), 'topic': topic, 'name': name, 'unit': unit,
                    'kind': kind, 'events': rows})


def changed_events(topic, limit):
    """Last `limit` events of a boolean/order topic, without repeats of the previous value.

    UX sends the same FALSE several times on End and order status can be published twice;
    for orders the previous value is the same order's previous status.
    """
    items = snapshot(topic)
    window = items[-(limit * 4 + 1):]
    has_reference = len(items) > len(window)  # window[0] then only serves as the previous value
    previous = {}
    kept = []
    for i, e in enumerate(window):
        key = e['message'].get('orderNumber') if topic == ORDERS_TOPIC else topic
        value = e['value']
        changed = key not in previous or previous[key] != value
        previous[key] = value
        if changed and not (i == 0 and has_reference):
            kept.append(e)
    return kept[-limit:]


def recent_feed(limit):
    """Merged feed across topics, newest first; numeric topics throttled to one entry per 2 s."""
    candidates = []
    for topic in TOPICS:
        kind = TOPICS[topic][2]
        if kind == 'number':
            # numeric topics need a deeper window because most of their events get throttled away
            candidates += [(e['timestamp'], topic, e) for e in snapshot(topic)[-limit * 40:]]
        else:
            candidates += [(e['timestamp'], topic, e) for e in changed_events(topic, limit)]
    candidates.sort(key=lambda c: c[0], reverse=True)

    feed, last_kept = [], {}
    for ts, topic, entry in candidates:
        if TOPICS[topic][2] == 'number':
            kept = last_kept.get(topic)
            if kept is not None and kept - ts < FEED_THROTTLE_MS:
                continue
            last_kept[topic] = ts
        row = event_row(topic, entry)
        row['name'] = TOPICS[topic][0]
        row['text'] = sentence(topic, entry)
        feed.append(row)
        if len(feed) >= limit:
            break
    return feed


@data_hub.route('/api/events/recent')
@permission_required(*API_PERMISSIONS)
def api_events_recent():
    return jsonify({'server_time': now_ms(), 'events': recent_feed(_limit(30, 200))})


# ── Quality (same check as design-space-representation.html) ─────────────────

def _inside_polygon(x, y, polygon):
    """Ray casting, as insidePolygon() on the Design Space page."""
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        (xi, yi), (xj, yj) = polygon[i], polygon[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def design_space(product=None):
    """Design space of `product` (set with the same name) or the first set.

    Returns {'name', 'polygon' (outer points sorted around the centroid, like the chart),
    'band': {'ISPESpeed': [min, max], 'ISPEMTemp': [min, max]}} or None.
    """
    sets = DesignSpaceSet.query.order_by(DesignSpaceSet.name).all()
    design_set = next((s for s in sets if product and s.name == product), sets[0] if sets else None)
    if not design_set:
        return None
    try:
        points = [(float(v['ispespeed']), float(v['ispetemp'])) for v in design_set.data['values']]
    except (KeyError, TypeError, ValueError):
        return None
    if len(points) < 3:
        return None
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    points.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    return {
        'name': design_set.name,
        'polygon': points,
        'band': {'ISPESpeed': [min(p[0] for p in points), max(p[0] for p in points)],
                 'ISPEMTemp': [min(p[1] for p in points), max(p[1] for p in points)]},
    }


def quality(product=None, order_number=None):
    """Latest speed/temperature against the design space of `product` (or the first set).

    With `order_number`, the values must carry that order (PLC2Nexus tags them once the order
    runs); until then the state stays 'unknown' instead of judging the idle values.
    Returns {'state': 'inside'|'outside'|'unknown', 'set': name, 'speed': .., 'temp': ..}.
    """
    ds = design_space(product)
    speed, temp = latest('ISPESpeed'), latest('ISPEMTemp')
    result = {'state': 'unknown', 'set': ds['name'] if ds else None,
              'speed': speed['value'] if speed else None, 'temp': temp['value'] if temp else None}
    if not ds or speed is None or temp is None:
        return result
    if order_number is not None and any(
            str(e['message'].get('orderNumber')) != str(order_number) for e in (speed, temp)):
        return result
    try:
        x, y = float(speed['value']), float(temp['value'])
    except (TypeError, ValueError):
        return result
    result['state'] = 'inside' if _inside_polygon(x, y, ds['polygon']) else 'outside'
    return result


# ── Dashboard helpers ────────────────────────────────────────────────────────

def series(topic, since_ms, max_points=120):
    """[[timestamp, value], ...] of a numeric topic since `since_ms`, thinned to max_points."""
    points, before = [], None
    for e in snapshot(topic):
        try:
            value = float(e['value'])
        except (TypeError, ValueError):
            continue
        if e['timestamp'] >= since_ms:
            points.append([e['timestamp'], value])
        else:
            before = value
    if before is not None:
        # the PLC holds its value: start the window with the last value before it
        points.insert(0, [since_ms, before])
    if len(points) > max_points:
        step = len(points) / max_points
        points = [points[int(i * step)] for i in range(max_points - 1)] + [points[-1]]
    return points


def order_times(order_number):
    """First Kafka timestamp (ms) per status of an order, from the stored order events."""
    times = {}
    for e in snapshot(ORDERS_TOPIC):
        if str(e['message'].get('orderNumber')) == str(order_number):
            times.setdefault(e['value'], e['timestamp'])
    return times


_out_of_spec_cache = {}


def out_of_spec_seconds(order_number, product, start_ms, end_ms, final=False):
    """Approximate seconds the latest speed/temperature point was outside the design space
    while the order ran. PLC values are held between change events, so each state lasts
    until the next event. Results of finished orders are cached."""
    key = (str(order_number), start_ms, end_ms)
    if final and key in _out_of_spec_cache:
        return _out_of_spec_cache[key]
    ds = design_space(product)
    if not ds or start_ms is None or end_ms is None:
        return None
    points = []
    for topic in ('ISPESpeed', 'ISPEMTemp'):
        for e in snapshot(topic):
            if start_ms <= e['timestamp'] <= end_ms and str(e['message'].get('orderNumber')) == str(order_number):
                try:
                    points.append((e['timestamp'], topic, float(e['value'])))
                except (TypeError, ValueError):
                    pass
    points.sort()
    current, total_ms, previous_ts = {}, 0, None
    for ts, topic, value in points:
        if previous_ts is not None and len(current) == 2 and \
                not _inside_polygon(current['ISPESpeed'], current['ISPEMTemp'], ds['polygon']):
            total_ms += ts - previous_ts
        current[topic] = value
        previous_ts = ts
    if previous_ts is not None and len(current) == 2 and \
            not _inside_polygon(current['ISPESpeed'], current['ISPEMTemp'], ds['polygon']):
        total_ms += end_ms - previous_ts
    result = round(total_ms / 1000)
    if final:
        _out_of_spec_cache[key] = result
    return result


# ── System health (/api/health) ──────────────────────────────────────────────

HEALTH_CACHE_S = 5
_health_lock = threading.Lock()
_health_cache = {'at': 0, 'result': None}


def _check_kafka():
    server = os.environ.get('KAFKASERVER', _config.get('Kafkaserver'))
    AdminClient({'bootstrap.servers': server}).list_topics(timeout=1.5)


def _check_plc():
    url = urlparse(os.environ.get('OPCUA_URL', 'opc.tcp://localhost:4840'))
    with socket.create_connection((url.hostname, url.port or 4840), timeout=1.0):
        pass


def _check_database():
    db.session.execute(text('SELECT 1'))


def health():
    """Kafka broker, PLC (OPC UA endpoint reachable) and database, cached for 5 s."""
    with _health_lock:
        if _health_cache['result'] and time.time() - _health_cache['at'] < HEALTH_CACHE_S:
            return _health_cache['result']
        checked_at = now_ms()
        result = {}
        for name, label, check in (('kafka', 'Kafka broker', _check_kafka),
                                   ('plc', 'PLC (OPC UA)', _check_plc),
                                   ('database', 'Database', _check_database)):
            try:
                check()
                result[name] = {'label': label, 'ok': True, 'checked_at': checked_at}
            except Exception as e:
                if name == 'database':
                    db.session.rollback()
                result[name] = {'label': label, 'ok': False, 'checked_at': checked_at, 'error': type(e).__name__}
        _health_cache.update(at=time.time(), result=result)
        return result


@data_hub.route('/api/health')
@permission_required(*API_PERMISSIONS)
def api_health():
    return jsonify({'server_time': now_ms(), 'checks': health()})
