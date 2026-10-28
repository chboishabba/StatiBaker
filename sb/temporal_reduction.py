"""StatiBaker-owned deterministic temporal partition for atom and thread IDs.

Only opaque canonical IDs enter this module. The reducer never performs
semantic merging, source mutation, or hidden deletion.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Mapping, Sequence

@dataclass(frozen=True)
class ActiveRecord:
    first_seen: date
    last_seen: date
    age_days: int

@dataclass(frozen=True)
class ResolvedRecord:
    first_seen: date
    last_seen: date
    resolved_on: date
    age_days: int

@dataclass(frozen=True)
class TemporalState:
    as_of: date
    atoms: Mapping[str, ActiveRecord]
    threads: Mapping[str, ActiveRecord]
    resolved_atoms: Mapping[str, ResolvedRecord]
    resolved_threads: Mapping[str, ResolvedRecord]

@dataclass(frozen=True)
class TemporalDelta:
    as_of: date
    atom_new: tuple[str, ...]
    atom_carryover: tuple[str, ...]
    atom_resolved: tuple[str, ...]
    thread_new: tuple[str, ...]
    thread_carryover: tuple[str, ...]
    thread_resolved: tuple[str, ...]
    state: TemporalState

def _ids(items: Sequence[str]) -> set[str]:
    if isinstance(items, (str, bytes)) or not isinstance(items, (list, tuple, frozenset)):
        raise ValueError("IDs must be a bounded sequence of opaque strings")
    if any(not isinstance(x, str) or not x.strip() for x in items):
        raise ValueError("IDs must be nonempty strings")
    if len(set(items)) != len(items):
        raise ValueError("duplicate canonical IDs are ambiguous")
    return set(items)

def _fold(
    previous: Mapping[str, ActiveRecord],
    resolved: Mapping[str, ResolvedRecord],
    present: set[str],
    today: date,
) -> tuple[dict[str, ActiveRecord], dict[str, ResolvedRecord], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    old = set(previous)
    new = tuple(sorted(present - old))
    carryover = tuple(sorted(present & old))
    gone = tuple(sorted(old - present))
    active: dict[str, ActiveRecord] = {}
    for key in sorted(present):
        first = previous[key].first_seen if key in previous else today
        active[key] = ActiveRecord(first_seen=first, last_seen=today, age_days=(today-first).days)
    history = dict(resolved)
    for key in gone:
        prior = previous[key]
        history[key] = ResolvedRecord(prior.first_seen, prior.last_seen, today, (today-prior.first_seen).days)
    # A returning ID begins a new active episode. Earlier resolution stays
    # visible in the prior append-only daily snapshots.
    return active, history, new, carryover, gone

def reduce_day(
    previous: TemporalState | None, *, as_of: date,
    atoms: Sequence[str], threads: Sequence[str],
    complete_snapshot: bool = True,
) -> TemporalDelta:
    """New=present-old, carryover=present&old, resolved=old-present.

    age_days is calendar days since this active episode's first_seen.
    Require explicit daily snapshots to avoid resolving IDs through gaps.
    """
    if not isinstance(as_of, date):
        raise ValueError("as_of must be a date")
    if complete_snapshot is not True:
        raise ValueError("partial snapshot cannot imply resolution")
    ids_atoms, ids_threads = _ids(atoms), _ids(threads)
    if previous is None:
        previous = TemporalState(as_of, {}, {}, {}, {})
    if as_of <= previous.as_of and (
        previous.atoms or previous.threads or previous.resolved_atoms or previous.resolved_threads
    ):
        raise ValueError("daily fold must advance time")
    if as_of < previous.as_of:
        raise ValueError("time must not go backward")
    if (as_of-previous.as_of).days > 1:
        raise ValueError("missing days require explicit snapshots before resolution")
    a, ah, an, ac, ar = _fold(previous.atoms, previous.resolved_atoms, ids_atoms, as_of)
    t, th, tn, tc, tr = _fold(previous.threads, previous.resolved_threads, ids_threads, as_of)
    state = TemporalState(as_of, a, t, ah, th)
    return TemporalDelta(as_of, an, ac, ar, tn, tc, tr, state)
