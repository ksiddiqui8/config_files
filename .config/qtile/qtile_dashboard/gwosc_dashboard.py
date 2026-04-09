#!/usr/bin/env python3
"""
GWOSC dashboard widget for Qtile screen/group 0.

Displays:
1) total number of GW events recorded in GWOSC's event-version list
2) number of events recorded this week
3) details of the latest recorded event

Requirements:
    - Python 3
    - tkinter (system package on Arch: tk)
    - requests (usually installed via python-requests or your system Python)
"""

from __future__ import annotations

import re
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional
import tkinter as tk
from tkinter import ttk

try:
    import requests
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: requests. Install it with pacman (python-requests) "
        "or inside your project environment."
    ) from exc


GWOSC_API_BASE = "https://gwosc.org/api/v2"
EVENT_LIST_URL = f"{GWOSC_API_BASE}/events/"
REQUEST_TIMEOUT = 20
MAX_PAGES = 200
CURRENT_GPS_UTC_OFFSET_SECONDS = 18  # current-era offset, good for weekly slicing


@dataclass
class EventRecord:
    name: str = ""
    version: Optional[int] = None
    gps: Optional[float] = None
    catalog: str = ""
    run: str = ""
    grace_id: str = ""
    url: str = ""
    raw: Dict[str, Any] = None


def fetch_json(url: str, timeout: int = REQUEST_TIMEOUT) -> Dict[str, Any]:
    resp = requests.get(url, timeout=timeout, headers={"Accept": "application/json"})
    resp.raise_for_status()
    return resp.json()


def iter_event_list_pages() -> Iterable[Dict[str, Any]]:
    url = EVENT_LIST_URL
    pages = 0
    while url and pages < MAX_PAGES:
        payload = fetch_json(url)
        yield payload
        url = payload.get("next")
        pages += 1


def normalize_event(item: Dict[str, Any]) -> EventRecord:
    raw_name = str(item.get("name", "")).strip()
    version = item.get("version")
    gps = item.get("gps")
    catalog = str(item.get("catalog", "")).strip()
    run = str(item.get("run", "")).strip()
    grace_id = str(item.get("grace_id", "")).strip()

    url = str(
        item.get("url")
        or item.get("detail_url")
        or item.get("self")
        or item.get("resource_uri")
        or ""
    ).strip()

    version_int: Optional[int]
    try:
        version_int = int(version) if version is not None else None
    except (TypeError, ValueError):
        version_int = None

    gps_float: Optional[float]
    try:
        gps_float = float(gps) if gps is not None else None
    except (TypeError, ValueError):
        gps_float = None

    return EventRecord(
        name=raw_name,
        version=version_int,
        gps=gps_float,
        catalog=catalog,
        run=run,
        grace_id=grace_id,
        url=url,
        raw=item,
    )


def list_all_events() -> List[EventRecord]:
    events: List[EventRecord] = []
    for page in iter_event_list_pages():
        results = page.get("results") or []
        for item in results:
            if isinstance(item, dict):
                events.append(normalize_event(item))
    return events


def event_slug(event: EventRecord) -> str:
    if event.url:
        return event.url.rstrip("/").split("/")[-1]

    name = event.name
    if name and re.search(r"-v\d+$", name):
        return name

    if event.version is not None and name:
        return f"{name}-v{event.version}"

    return name


def fetch_event_detail(event: EventRecord) -> Dict[str, Any]:
    slug = event_slug(event)
    if not slug:
        raise ValueError("Could not determine event detail slug")

    if slug.startswith("http://") or slug.startswith("https://"):
        url = slug
    else:
        url = f"{GWOSC_API_BASE}/event-versions/{slug}"

    return fetch_json(url)


def week_start_utc(now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).date()
    return datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)


def utc_to_gps_seconds(dt: datetime) -> float:
    epoch = datetime(1980, 1, 6, tzinfo=timezone.utc)
    return (dt - epoch).total_seconds() + CURRENT_GPS_UTC_OFFSET_SECONDS


def format_gps_as_utc(gps: Optional[float]) -> str:
    if gps is None:
        return "Unknown"
    epoch = datetime(1980, 1, 6, tzinfo=timezone.utc)
    utc = epoch + timedelta(seconds=float(gps) - CURRENT_GPS_UTC_OFFSET_SECONDS)
    return utc.strftime("%Y-%m-%d %H:%M:%S UTC")


def latest_event(events: List[EventRecord]) -> Optional[EventRecord]:
    gps_events = [e for e in events if e.gps is not None]
    if not gps_events:
        return None
    return max(gps_events, key=lambda e: float(e.gps))


def count_events_this_week(events: List[EventRecord]) -> int:
    start_gps = utc_to_gps_seconds(week_start_utc())
    return sum(1 for e in events if e.gps is not None and float(e.gps) >= start_gps)


class GWOSCDashboard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("GWOSC Dashboard")
        self.geometry("1100x700")
        self.configure(bg="#0b0f14")
        self.minsize(900, 600)

        self._busy = False

        self._build_styles()
        self._build_ui()
        self._schedule_refresh(initial=True)

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Card.TFrame", background="#121826", relief="flat")
        style.configure(
            "Title.TLabel",
            background="#0b0f14",
            foreground="#e5e7eb",
            font=("Sans", 22, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background="#0b0f14",
            foreground="#9ca3af",
            font=("Sans", 10),
        )
        style.configure(
            "Section.TLabel",
            background="#121826",
            foreground="#93c5fd",
            font=("Sans", 11, "bold"),
        )
        style.configure(
            "Metric.TLabel",
            background="#121826",
            foreground="#f9fafb",
            font=("Sans", 28, "bold"),
        )
        style.configure(
            "Dark.TButton",
            background="#1f2937",
            foreground="#f9fafb",
            padding=8,
            font=("Sans", 10, "bold"),
        )
        style.map(
            "Dark.TButton",
            background=[("active", "#374151")],
            foreground=[("active", "#ffffff")],
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True, padx=18, pady=18)

        header = tk.Frame(outer, bg="#0b0f14")
        header.pack(fill="x", pady=(0, 14))

        title = ttk.Label(header, text="GWOSC Dashboard", style="Title.TLabel")
        title.pack(anchor="w")

        subtitle = ttk.Label(
            header,
            text="Live event count, this-week count, and the latest recorded case.",
            style="Subtitle.TLabel",
        )
        subtitle.pack(anchor="w", pady=(2, 0))

        controls = tk.Frame(header, bg="#0b0f14")
        controls.pack(anchor="e", pady=(8, 0), fill="x")

        self.status_var = tk.StringVar(value="Idle")
        status = ttk.Label(controls, textvariable=self.status_var, style="Subtitle.TLabel")
        status.pack(side="left")

        refresh_btn = ttk.Button(controls, text="Refresh now", style="Dark.TButton", command=self.refresh_async)
        refresh_btn.pack(side="right")

        cards = tk.Frame(outer, bg="#0b0f14")
        cards.pack(fill="both", expand=True)
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)
        cards.rowconfigure(1, weight=1)

        self.total_card = self._make_card(cards, 0, 0, "Total events ever recorded")
        self.week_card = self._make_card(cards, 0, 1, "Events this week")

        latest_card = ttk.Frame(cards, style="Card.TFrame")
        latest_card.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)

        latest_title = ttk.Label(latest_card, text="Latest recorded case", style="Section.TLabel")
        latest_title.pack(anchor="w", padx=16, pady=(14, 8))

        self.latest_text = tk.Text(
            latest_card,
            wrap="word",
            bg="#121826",
            fg="#e5e7eb",
            insertbackground="#e5e7eb",
            relief="flat",
            highlightthickness=0,
            font=("Monospace", 11),
        )
        self.latest_text.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.latest_text.configure(state="disabled")

        footer = tk.Frame(outer, bg="#0b0f14")
        footer.pack(fill="x", pady=(10, 0))

        self.error_var = tk.StringVar(value="")
        err = ttk.Label(footer, textvariable=self.error_var, style="Subtitle.TLabel")
        err.pack(anchor="w")

    def _make_card(self, parent: tk.Widget, row: int, col: int, label: str) -> Dict[str, Any]:
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
        parent.columnconfigure(col, weight=1)

        lbl = ttk.Label(frame, text=label, style="Section.TLabel")
        lbl.pack(anchor="w", padx=16, pady=(14, 8))

        value = ttk.Label(frame, text="—", style="Metric.TLabel")
        value.pack(anchor="w", padx=16, pady=(0, 14))

        return {"frame": frame, "label": lbl, "value": value}

    def _schedule_refresh(self, initial: bool = False) -> None:
        if initial:
            self.refresh_async()
        self.after(20 * 60 * 1000, self.refresh_async)  # every 20 minutes

    def refresh_async(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.status_var.set("Refreshing…")
        self.error_var.set("")
        thread = threading.Thread(target=self._refresh_worker, daemon=True)
        thread.start()

    def _refresh_worker(self) -> None:
        try:
            events = list_all_events()
            total = len(events)
            weekly = count_events_this_week(events)
            latest = latest_event(events)

            latest_detail: Dict[str, Any] = {}
            if latest is not None:
                try:
                    latest_detail = fetch_event_detail(latest)
                except Exception:
                    latest_detail = latest.raw or {}

            latest_text = self._render_latest_text(latest, latest_detail, total, weekly)
            self.after(0, lambda: self._apply_data(total, weekly, latest_text))
        except Exception as exc:
            detail = f"{exc.__class__.__name__}: {exc}"
            trace = traceback.format_exc(limit=3)
            self.after(0, lambda: self._apply_error(detail, trace))
        finally:
            self.after(0, lambda: setattr(self, "_busy", False))

    def _apply_data(self, total: int, weekly: int, latest_text: str) -> None:
        self.total_card["value"].config(text=f"{total:,}")
        self.week_card["value"].config(text=f"{weekly:,}")
        self._set_latest_text(latest_text)
        self.status_var.set(f"Updated {datetime.now().strftime('%H:%M:%S')}")
        self.error_var.set("")

    def _apply_error(self, detail: str, trace: str) -> None:
        self.status_var.set("Update failed")
        self.error_var.set(detail)
        self._set_latest_text(
            "Could not refresh GWOSC data.\n\n"
            f"{detail}\n\n"
            "Traceback (last lines):\n"
            f"{trace}"
        )

    def _set_latest_text(self, text: str) -> None:
        self.latest_text.configure(state="normal")
        self.latest_text.delete("1.0", "end")
        self.latest_text.insert("1.0", text)
        self.latest_text.configure(state="disabled")

    def _render_latest_text(
        self,
        latest: Optional[EventRecord],
        latest_detail: Dict[str, Any],
        total: int,
        weekly: int,
    ) -> str:
        if latest is None:
            return "No GWOSC events were found."

        name = str(latest_detail.get("name") or latest.name or "Unknown").strip()
        version = latest_detail.get("version", latest.version)
        catalog = str(latest_detail.get("catalog") or latest.catalog or "Unknown").strip()
        run = str(latest_detail.get("run") or latest.run or "Unknown").strip()
        grace_id = str(latest_detail.get("grace_id") or latest.grace_id or "Unknown").strip()
        gps = latest_detail.get("gps", latest.gps)
        aliases = latest_detail.get("aliases") or []
        gcn_notice = latest_detail.get("gcn_notice") or ""
        gcn_circular = latest_detail.get("gcn_circular") or ""
        doi = latest_detail.get("doi") or ""

        lines = [
            f"Name: {name}",
            f"Version: {version}",
            f"Catalog: {catalog}",
            f"Run: {run}",
            f"Grace ID: {grace_id}",
            f"GPS: {gps if gps is not None else 'Unknown'}",
            f"UTC: {format_gps_as_utc(gps if gps is not None else None)}",
        ]

        if aliases:
            lines.append(f"Aliases: {', '.join(map(str, aliases))}")
        if gcn_notice:
            lines.append(f"GCN notice: {gcn_notice}")
        if gcn_circular:
            lines.append(f"GCN circular: {gcn_circular}")
        if doi:
            lines.append(f"DOI: {doi}")

        lines.append("")
        lines.append(f"Total events: {total:,}")
        lines.append(f"This week: {weekly:,}")

        return "\n".join(lines)


def main() -> None:
    app = GWOSCDashboard()
    app.mainloop()


if __name__ == "__main__":
    main()
