"""Prometheus custom business metrics."""

from prometheus_client import Counter, Gauge, Histogram

# Message metrics
messages_total = Counter(
    "noteme_messages_total",
    "Total messages processed",
    ["type"],  # text, voice, callback
)

# AI metrics
ai_requests_total = Counter(
    "noteme_ai_requests_total",
    "Total AI requests",
    ["agent"],  # validation, router, event, note, query, formatter
)
ai_latency_seconds = Histogram(
    "noteme_ai_latency_seconds",
    "AI request latency",
    ["agent"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Entity metrics
events_total = Gauge("noteme_events_total", "Total events in DB")
notes_total = Gauge("noteme_notes_total", "Total notes in DB")

# Notification metrics
notifications_sent_total = Counter(
    "noteme_notifications_sent_total",
    "Total notifications sent",
)

# User metrics
active_users = Gauge("noteme_active_users", "Active users count")

# Error metrics
errors_total = Counter(
    "noteme_errors_total",
    "Total errors",
    ["type"],  # handler, ai, db, notification
)
