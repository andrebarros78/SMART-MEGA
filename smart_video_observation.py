from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import math
import multiprocessing as mp
import os
import queue
import re
import socket
import statistics
import tempfile
import threading
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

EXTRACTOR_VERSION = "1.3.1"
PREDICTIVE_EVIDENCE = "NOT_ESTABLISHED"
VALID_STATUSES = {
    "CANDIDATE",
    "UNRESOLVED",
    "UNOBSERVABLE",
    "STREAM_FAILED",
    "TIMEOUT",
    "INSUFFICIENT_EVIDENCE",
}


@dataclass(frozen=True)
class ObservationConfig:
    resolver_timeout_s: float = 15.0
    segment_locator_timeout_s: float = 25.0
    sample_timeout_s: float = 12.0
    contest_timeout_s: float = 120.0
    coarse_sample_s: float = 2.5
    coarse_points: int = 12
    refine_window_s: float = 6.0
    max_refined_regions: int = 3
    analysis_fps: float = 5.0
    frame_width: int = 320
    workers: int = 2
    motion_floor: float = 0.012
    event_mad_multiplier: float = 2.5
    min_event_gap_s: float = 0.3
    min_candidate_events: int = 3
    grid_rows: int = 3
    grid_cols: int = 4

    def validated(self) -> "ObservationConfig":
        for name in (
            "resolver_timeout_s",
            "segment_locator_timeout_s",
            "sample_timeout_s",
            "contest_timeout_s",
            "coarse_sample_s",
            "refine_window_s",
            "analysis_fps",
            "motion_floor",
            "event_mad_multiplier",
            "min_event_gap_s",
        ):
            if float(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in (
            "coarse_points",
            "max_refined_regions",
            "frame_width",
            "workers",
            "min_candidate_events",
            "grid_rows",
            "grid_cols",
        ):
            if int(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.workers > 4:
            raise ValueError("workers must be <= 4")
        return self


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _validate_public_https(url: str) -> str:
    parsed = urlparse(str(url))
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source URL must be credential-free HTTPS")
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("local source hosts are not allowed")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise ValueError("source IP must be globally routable")
        return str(url)
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("source hostname could not be resolved") from exc
    addresses = {item[4][0] for item in infos if item and item[4]}
    if not addresses:
        raise ValueError("source hostname resolved to no addresses")
    for addr in addresses:
        if not ipaddress.ip_address(addr).is_global:
            raise ValueError("source hostname resolves to non-public address")
    return str(url)


def _is_youtube_source(source_url: str) -> bool:
    host = (urlparse(str(source_url)).hostname or "").lower().rstrip(".")
    return host == "youtube.com" or host.endswith(".youtube.com") or host == "youtu.be" or host.endswith(".youtu.be")


def _pick_motion_stream(info: dict[str, Any]) -> dict[str, Any]:
    formats: list[tuple[dict[str, Any], int, int]] = []
    for fmt in info.get("formats") or []:
        if not fmt.get("url") or str(fmt.get("vcodec") or "none") == "none":
            continue
        if not str(fmt.get("protocol") or "").lower().startswith("http"):
            continue
        formats.append((fmt, int(fmt.get("height") or 0), int(fmt.get("width") or 0)))
    if not formats:
        raise ValueError("no usable video stream format")
    under = [item for item in formats if 0 < item[1] <= 360]
    if under:
        return max(under, key=lambda x: (x[1], int(x[0].get("fps") or 0), float(x[0].get("tbr") or 0.0)))[0]
    positive = [item for item in formats if item[1] > 0]
    return min(positive or formats, key=lambda x: (x[1] if x[1] > 0 else 10**9, x[2] if x[2] > 0 else 10**9))[0]


def _resolve_stream_impl(source_url: str) -> dict[str, Any]:
    source_url = _validate_public_https(source_url)
    if _is_youtube_source(source_url):
        import yt_dlp
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 10,
            "retries": 1,
            "fragment_retries": 1,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(source_url, download=False)
        fmt = _pick_motion_stream(info)
        return {
            "source_url": source_url,
            "stream_url": fmt.get("url"),
            "video_id": str(info.get("id") or "unknown"),
            "title": info.get("title"),
            "duration_s": float(info.get("duration") or 0.0),
            "format_id": str(fmt.get("format_id") or "unknown"),
            "height": fmt.get("height"),
            "width": fmt.get("width"),
            "protocol": fmt.get("protocol"),
            "resolver": "yt_dlp_stream_only",
        }
    return {
        "source_url": source_url,
        "stream_url": source_url,
        "video_id": "direct_https",
        "title": None,
        "duration_s": 0.0,
        "format_id": "direct",
        "height": None,
        "width": None,
        "protocol": "https",
        "resolver": "direct_https_stream",
    }


def _resolver_worker(source_url: str, out_q: Any) -> None:
    try:
        out_q.put({"ok": True, "value": _resolve_stream_impl(source_url)})
    except Exception as exc:
        out_q.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def resolve_stream(source_url: str, timeout_s: float) -> dict[str, Any]:
    ctx = mp.get_context("spawn")
    out_q = ctx.Queue(maxsize=1)
    proc = ctx.Process(target=_resolver_worker, args=(source_url, out_q), daemon=True)
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(2)
        raise TimeoutError(f"stream resolution exceeded {timeout_s:.1f}s")
    try:
        payload = out_q.get_nowait()
    except queue.Empty as exc:
        raise RuntimeError(f"resolver exited without result (exit={proc.exitcode})") from exc
    if not payload.get("ok"):
        raise RuntimeError(payload.get("error") or "stream resolver failed")
    return payload["value"]


def _resize_gray(frame: Any, width: int) -> Any:
    import cv2
    h, w = frame.shape[:2]
    if w > width:
        scale = width / float(w)
        frame = cv2.resize(frame, (width, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _grid_energy(diff: Any, rows: int, cols: int) -> list[float]:
    h, w = diff.shape[:2]
    values: list[float] = []
    for r in range(rows):
        y0, y1 = (r * h) // rows, ((r + 1) * h) // rows
        for c in range(cols):
            x0, x1 = (c * w) // cols, ((c + 1) * w) // cols
            cell = diff[y0:y1, x0:x1]
            values.append(float(cell.mean()) / 255.0 if cell.size else 0.0)
    return values


def _sample_impl(spec: dict[str, Any]) -> dict[str, Any]:
    import cv2
    source = spec["stream_url"]
    start_s = max(0.0, float(spec["start_s"]))
    duration_s = max(0.1, float(spec["duration_s"]))
    target_fps = max(0.5, float(spec["analysis_fps"]))
    width = int(spec["frame_width"])
    rows, cols = int(spec["grid_rows"]), int(spec["grid_cols"])
    alt_rows = rows + 1 if rows < 4 else max(2, rows - 1)
    alt_cols = cols
    cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("VideoCapture could not open stream")
    try:
        if start_s > 0:
            cap.set(cv2.CAP_PROP_POS_MSEC, start_s * 1000.0)
        native_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if not math.isfinite(native_fps) or native_fps <= 0:
            native_fps = 25.0
        frame_stride = max(1, int(round(native_fps / target_fps)))
        max_frames = max(2, int(math.ceil(duration_s * native_fps)) + frame_stride)
        prev = None
        scores: list[float] = []
        times: list[float] = []
        grid_sum = [0.0] * (rows * cols)
        grid_sum_alt = [0.0] * (alt_rows * alt_cols)
        global_motion_fractions: list[float] = []
        read_frames = 0
        analyzed_frames = 0
        failures = 0
        while read_frames < max_frames:
            ok, frame = cap.read()
            if not ok or frame is None:
                failures += 1
                if failures >= 3:
                    break
                continue
            failures = 0
            idx = read_frames
            read_frames += 1
            if idx % frame_stride:
                continue
            gray = _resize_gray(frame, width)
            if prev is not None:
                diff = cv2.absdiff(gray, prev)
                score = float(diff.mean()) / 255.0
                scores.append(score)
                times.append(start_s + idx / native_fps)
                ge = _grid_energy(diff, rows, cols)
                ge_alt = _grid_energy(diff, alt_rows, alt_cols)
                baseline = statistics.median(ge) if ge else 0.0
                mean = statistics.fmean(ge) if ge else 0.0
                global_motion_fractions.append(min(1.0, baseline / max(mean, 1e-12)))
                residual = [max(0.0, value - baseline) for value in ge]
                baseline_alt = statistics.median(ge_alt) if ge_alt else 0.0
                residual_alt = [max(0.0, value - baseline_alt) for value in ge_alt]
                for i, value in enumerate(residual):
                    grid_sum[i] += value
                for i, value in enumerate(residual_alt):
                    grid_sum_alt[i] += value
            prev = gray
            analyzed_frames += 1
        if analyzed_frames < 2 or not scores:
            raise RuntimeError("insufficient decodable frames in sample")
        denom = max(1, len(scores))
        return {
            "status": "OK",
            "start_s": start_s,
            "duration_s": duration_s,
            "native_fps": native_fps,
            "read_frames": read_frames,
            "analyzed_frames": analyzed_frames,
            "motion_scores": scores,
            "sample_times": times,
            "mean_motion": statistics.fmean(scores),
            "median_motion": statistics.median(scores),
            "max_motion": max(scores),
            "grid_energy": [value / denom for value in grid_sum],
            "grid_energy_alt": [value / denom for value in grid_sum_alt],
            "grid_shape": [rows, cols],
            "grid_shape_alt": [alt_rows, alt_cols],
            "global_motion_fraction": statistics.fmean(global_motion_fractions) if global_motion_fractions else 0.0,
        }
    finally:
        cap.release()


def _sample_worker(spec: dict[str, Any], out_q: Any) -> None:
    try:
        out_q.put({"ok": True, "value": _sample_impl(spec)})
    except Exception as exc:
        out_q.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def observe_short_sample(spec: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    ctx = mp.get_context("spawn")
    out_q = ctx.Queue(maxsize=1)
    proc = ctx.Process(target=_sample_worker, args=(spec, out_q), daemon=True)
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(2)
        return {"status": "TIMEOUT", "start_s": spec.get("start_s"), "error": f"sample exceeded {timeout_s:.1f}s"}
    try:
        payload = out_q.get_nowait()
    except queue.Empty:
        return {"status": "UNOBSERVABLE", "start_s": spec.get("start_s"), "error": f"sample worker exited without result (exit={proc.exitcode})"}
    if not payload.get("ok"):
        return {"status": "UNOBSERVABLE", "start_s": spec.get("start_s"), "error": payload.get("error") or "sample failed"}
    return payload["value"]


def coarse_timestamps(duration_s: float, points: int, sample_s: float, window_start_s: float = 0.0, window_end_s: float | None = None) -> list[float]:
    end = duration_s if window_end_s is None else min(duration_s, max(0.0, float(window_end_s)))
    lo = min(end, max(0.0, float(window_start_s)))
    if end - lo <= sample_s:
        return [lo]
    hi = max(lo, end - sample_s)
    if points <= 1:
        return [lo + (hi - lo) / 2.0]
    return [lo + (hi - lo) * i / (points - 1) for i in range(points)]


def _sample_spec(stream: dict[str, Any], start_s: float, duration_s: float, cfg: ObservationConfig) -> dict[str, Any]:
    return {
        "stream_url": stream["stream_url"],
        "start_s": start_s,
        "duration_s": duration_s,
        "analysis_fps": cfg.analysis_fps,
        "frame_width": cfg.frame_width,
        "grid_rows": cfg.grid_rows,
        "grid_cols": cfg.grid_cols,
    }


def run_samples(specs: Iterable[dict[str, Any]], sampler: Callable[[dict[str, Any], float], dict[str, Any]], timeout_s: float, workers: int) -> list[dict[str, Any]]:
    specs = list(specs)
    if not specs:
        return []
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(4, workers))) as pool:
        futs = {pool.submit(sampler, spec, timeout_s): spec for spec in specs}
        for fut in as_completed(futs):
            spec = futs[fut]
            try:
                results.append(fut.result())
            except Exception as exc:
                results.append({"status": "UNOBSERVABLE", "start_s": spec.get("start_s"), "error": f"{type(exc).__name__}: {exc}"})
    return sorted(results, key=lambda row: float(row.get("start_s") or 0.0))


def select_promising_regions(coarse: list[dict[str, Any]], cfg: ObservationConfig, duration_s: float, window_start_s: float = 0.0, window_end_s: float | None = None, learning_prior: dict[str, Any] | None = None) -> list[float]:
    valid = [row for row in coarse if row.get("status") == "OK" and float(row.get("mean_motion") or 0.0) >= cfg.motion_floor]
    def priority(row: dict[str, Any]) -> float:
        motion = float(row.get("mean_motion") or 0.0)
        global_fraction = min(1.0, max(0.0, float(row.get("global_motion_fraction") or 0.0)))
        grid = [max(0.0, float(value)) for value in (row.get("grid_energy") or [])]
        locality = 0.0
        total = sum(grid)
        if total > 1e-12:
            dominant = max(grid) / total
            max_cell = max(grid)
            spread = sum(1 for value in grid if value >= max_cell * 0.35) / float(len(grid))
            locality = dominant * max(0.0, 1.0 - spread)
        baseline = motion * (0.25 + 0.75 * (1.0 - global_fraction)) * (1.0 + 2.0 * locality)
        if not learning_prior or learning_prior.get("active") is not True:
            return baseline
        lo = max(0.0, float(window_start_s))
        hi = duration_s if window_end_s is None else min(duration_s, float(window_end_s))
        if hi <= lo:
            return baseline
        middle = (float(row.get("start_s") or 0.0) + cfg.coarse_sample_s / 2.0 - lo) / (hi - lo)
        center = float(learning_prior["normalized_event_center"])
        proximity = max(0.0, 1.0 - abs(middle - center) / 0.20)
        # No suppression of observed motion: at most 15% bounded priority bonus.
        return baseline * (1.0 + 0.15 * proximity)
    valid.sort(key=priority, reverse=True)
    selected: list[float] = []
    separation = max(cfg.refine_window_s * 0.75, cfg.coarse_sample_s)
    lower = max(0.0, float(window_start_s))
    upper_end = duration_s if window_end_s is None else min(duration_s, max(lower, float(window_end_s)))
    for item in valid:
        t = float(item.get("start_s") or 0.0)
        center = t + cfg.coarse_sample_s / 2.0
        start = max(lower, center - cfg.refine_window_s / 2.0)
        if duration_s > 0:
            start = min(start, max(lower, upper_end - cfg.refine_window_s))
        if any(abs(start - chosen) < separation for chosen in selected):
            continue
        selected.append(start)
        if len(selected) >= cfg.max_refined_regions:
            break
    return sorted(selected)


def detect_events(sample: dict[str, Any], cfg: ObservationConfig) -> list[float]:
    scores = [float(value) for value in sample.get("motion_scores") or []]
    times = [float(value) for value in sample.get("sample_times") or []]
    if not scores or len(scores) != len(times):
        return []
    med = statistics.median(scores)
    mad = statistics.median([abs(value - med) for value in scores]) or 1e-9
    threshold = max(cfg.motion_floor, med + cfg.event_mad_multiplier * mad)
    events: list[float] = []
    for i, score in enumerate(scores):
        if score < threshold:
            continue
        left = scores[i - 1] if i else -1.0
        right = scores[i + 1] if i + 1 < len(scores) else -1.0
        if score < left or score < right:
            continue
        t = times[i]
        if events and t - events[-1] < cfg.min_event_gap_s:
            continue
        events.append(t)
    return events


def spatial_classification(samples: list[dict[str, Any]], grid_key: str = "grid_energy") -> dict[str, Any]:
    grids = [sample.get(grid_key) for sample in samples if sample.get("status") == "OK" and sample.get(grid_key)]
    global_fractions = [min(1.0, max(0.0, float(sample.get("global_motion_fraction") or 0.0))) for sample in samples if sample.get("status") == "OK" and sample.get("global_motion_fraction") is not None]
    global_fraction = statistics.median(global_fractions) if global_fractions else 0.0
    if not grids:
        return {"classification": "UNRESOLVED", "dominant_cell": None, "dominance": 0.0, "spread": 0.0, "global_motion_fraction": round(global_fraction, 6)}
    size = len(grids[0])
    agg = [0.0] * size
    for grid in grids:
        if len(grid) != size:
            continue
        for i, value in enumerate(grid):
            agg[i] += float(value)
    total = sum(agg)
    if total <= 1e-12:
        label = "GLOBAL_MOTION_OR_CAMERA_CHANGE" if global_fraction >= 0.72 else "UNRESOLVED"
        return {"classification": label, "dominant_cell": None, "dominance": 0.0, "spread": 0.0, "global_motion_fraction": round(global_fraction, 6)}
    dominant = max(range(size), key=lambda i: agg[i])
    dominance = agg[dominant] / total
    max_cell = max(agg)
    spread = sum(1 for value in agg if value >= max_cell * 0.35) / float(size)
    if global_fraction >= 0.72:
        label = "GLOBAL_MOTION_OR_CAMERA_CHANGE"
    elif spread >= 0.67 and dominance <= 0.22:
        label = "GLOBAL_MOTION_OR_CAMERA_CHANGE"
    elif dominance >= 0.28 and spread <= 0.50:
        label = "RECURRENT_SOURCE_REGION_CANDIDATE"
    else:
        label = "UNRESOLVED"
    return {"classification": label, "dominant_cell": dominant, "dominance": round(dominance, 6), "spread": round(spread, 6), "global_motion_fraction": round(global_fraction, 6)}


def cadence_metrics(events: list[float], event_groups: list[list[float]] | None = None) -> dict[str, Any]:
    if event_groups is None:
        groups = [list(events)]
        basis = "CONTIGUOUS_EVENT_SEQUENCE"
        event_count = len(events)
    else:
        groups = [sorted(float(value) for value in group) for group in event_groups]
        basis = "WITHIN_OBSERVED_WINDOWS_ONLY"
        event_count = sum(len(group) for group in groups)
    gaps = [b - a for group in groups for a, b in zip(group, group[1:]) if b > a]
    if not gaps:
        return {"event_count": event_count, "median_gap_s": None, "regularity": None, "gap_count": 0, "basis": basis}
    med = statistics.median(gaps)
    mad = statistics.median([abs(gap - med) for gap in gaps])
    regularity = 1.0 / (1.0 + (mad / med if med > 0 else 1e9))
    return {"event_count": event_count, "median_gap_s": round(med, 6), "regularity": round(regularity, 6), "gap_count": len(gaps), "basis": basis}


def _segment_from_caption_events(events: list[tuple[float, str]]) -> dict[str, Any]:
    parsed: list[tuple[float, set[str], str]] = []
    for sec, text in events:
        clean = str(text).replace("\n", " ").strip()
        parsed.append((float(sec), set(re.findall(r"[a-záàâãéêíóôõúç0-9]+", clean.lower())), clean))
    case_times = [sec for sec, _tokens, text in parsed if re.search(r"\bCJ60[A-Z]\b", text, re.I)]
    action_roots = ("sorte", "globo", "bola", "lacre", "auditor", "inici", "agora", "carreg", "máquina", "maquina")
    candidates: list[dict[str, Any]] = []
    for i, (sec, _tokens, _text) in enumerate(parsed):
        lo, hi = max(0, i - 3), min(len(parsed), i + 4)
        current_tokens = parsed[i][1]
        token_set = {token for j in range(lo, hi) for token in parsed[j][1]}
        current_has_modality = (
            any(token.startswith("mega") for token in current_tokens)
            or any(token in {"sena", "cena"} or token.startswith("sena") for token in current_tokens)
        )
        context_has_pair = (
            any(token.startswith("mega") for token in token_set)
            and any(token in {"sena", "cena"} or token.startswith("sena") for token in token_set)
        )
        if not (current_has_modality and context_has_pair):
            continue
        actions = sorted({root for root in action_roots if any(token.startswith(root) for token in token_set)})
        case_delta = min((abs(sec - case_t) for case_t in case_times), default=9999.0)
        nearest_case = min(case_times, key=lambda value: abs(sec - value)) if case_times else None
        score = len(actions) * 2 + (3 if case_delta <= 75.0 else 0) + (1 if case_delta <= 30.0 else 0)
        candidates.append({"anchor_s": sec, "action_roots": actions, "action_count": len(actions), "case_marker_s": nearest_case, "case_delta_s": case_delta, "score": score})
    clusters: list[list[dict[str, Any]]] = []
    for item in sorted(candidates, key=lambda value: value["anchor_s"]):
        if not clusters or item["anchor_s"] - clusters[-1][-1]["anchor_s"] > 15.0:
            clusters.append([item])
        else:
            clusters[-1].append(item)
    ranked = sorted(
        [sorted(cluster, key=lambda value: (-value["score"], value["case_delta_s"], value["anchor_s"]))[0] for cluster in clusters],
        key=lambda value: (-value["score"], value["case_delta_s"], value["anchor_s"]),
    )
    if not ranked:
        return {"status": "UNAVAILABLE", "reason": "no operational Mega-Sena caption anchor", "candidate_eligible": False}
    best = ranked[0]
    ambiguous = len(ranked) > 1 and best["score"] == ranked[1]["score"] and abs(best["case_delta_s"] - ranked[1]["case_delta_s"]) <= 10.0
    passed = best["action_count"] >= 3 and best["case_delta_s"] <= 45.0 and best["score"] >= 10 and not ambiguous
    if not passed:
        return {"status": "AMBIGUOUS" if ambiguous else "INSUFFICIENT_EVIDENCE", "candidate_eligible": False, "score": best["score"], "action_count": best["action_count"], "case_delta_s": round(best["case_delta_s"], 6)}
    anchor = float(best["anchor_s"])
    case_t = float(best["case_marker_s"] if best["case_marker_s"] is not None else anchor)
    return {
        "status": "PASS",
        "candidate_eligible": True,
        "method": "MEGA_SENA_OPERATIONAL_CAPTION_NEAR_PROCEDURAL_MARKER_V1",
        "anchor_s": round(anchor, 6),
        "case_marker_s": round(case_t, 6),
        "case_delta_s": round(abs(anchor - case_t), 6),
        "action_roots": list(best["action_roots"]),
        "score": int(best["score"]),
        "segment_start_s": round(max(0.0, min(anchor, case_t) - 45.0), 6),
        "segment_end_s": round(max(anchor, case_t) + 120.0, 6),
    }


def _locate_mega_segment_impl(source_url: str, contest_id: str) -> dict[str, Any]:
    if not _is_youtube_source(source_url):
        return {"status": "NOT_APPLICABLE", "candidate_eligible": True}
    import requests
    import yt_dlp
    from smart_http_guard import read_limited_bytes, validate_https_url
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 10, "retries": 1, "fragment_retries": 1}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source_url, download=False)
    caps = info.get("automatic_captions") or {}
    choices = caps.get("pt-orig") or caps.get("pt") or []
    choice = next((item for item in choices if str(item.get("ext") or "").lower() == "json3"), choices[0] if choices else None)
    if not choice or not choice.get("url"):
        return {"status": "UNAVAILABLE", "reason": "automatic caption json3 unavailable", "candidate_eligible": False}
    caption_url = validate_https_url(str(choice["url"]), allowed_host_suffixes=("youtube.com", "googlevideo.com"))
    response = requests.get(caption_url, timeout=20, stream=True)
    response.raise_for_status()
    raw = read_limited_bytes(response, max_bytes=8 * 1024 * 1024)
    doc = json.loads(raw)
    events: list[tuple[float, str]] = []
    for event in doc.get("events", []):
        text = "".join(seg.get("utf8", "") for seg in event.get("segs", [])).replace("\n", " ").strip()
        if text:
            events.append((float(event.get("tStartMs", 0)) / 1000.0, text))
    result = _segment_from_caption_events(events)
    result["caption_bytes"] = len(raw)
    result["caption_sha256"] = hashlib.sha256(raw).hexdigest()
    result["contest_id"] = str(contest_id)
    return result


def _segment_locator_worker(source_url: str, contest_id: str, out_q: Any) -> None:
    try:
        out_q.put({"ok": True, "value": _locate_mega_segment_impl(source_url, contest_id)})
    except Exception as exc:
        out_q.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def locate_mega_segment(source_url: str, contest_id: str, timeout_s: float) -> dict[str, Any]:
    if not _is_youtube_source(source_url):
        return {"status": "NOT_APPLICABLE", "candidate_eligible": True}
    ctx = mp.get_context("spawn")
    out_q = ctx.Queue(maxsize=1)
    proc = ctx.Process(target=_segment_locator_worker, args=(source_url, str(contest_id), out_q), daemon=True)
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(2)
        return {"status": "TIMEOUT", "reason": f"segment locator exceeded {timeout_s:.1f}s", "candidate_eligible": False}
    try:
        payload = out_q.get_nowait()
    except queue.Empty:
        return {"status": "UNAVAILABLE", "reason": f"segment locator exited without result (exit={proc.exitcode})", "candidate_eligible": False}
    if not payload.get("ok"):
        return {"status": "UNAVAILABLE", "reason": payload.get("error") or "segment locator failed", "candidate_eligible": False}
    return payload["value"]


def _checkpoint_path(checkpoint_dir: Path, contest_id: str) -> Path:
    safe = "".join(ch for ch in str(contest_id) if ch.isalnum() or ch in "-_") or "unknown"
    return checkpoint_dir / f"contest_{safe}.json"


def _read_checkpoint(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or data.get("contest_id") is None or data.get("status") not in VALID_STATUSES:
        return None
    return data


_ATOMIC_JSON_WRITE_LOCK = threading.RLock()

def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    with _ATOMIC_JSON_WRITE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=path.name + ".", suffix=".tmp", delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


def _observation_fingerprint(contest_id: str, source_url: str, cfg: ObservationConfig, hypothesis_id: str | None) -> str:
    identity = {
        "contest_id": str(contest_id),
        "source_url": source_url,
        "extractor_version": EXTRACTOR_VERSION,
        "hypothesis_id": hypothesis_id,
        "params": asdict(cfg),
    }
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()



def learned_motion_prior(
    checkpoint_dir: str | Path,
    contest_id: str,
    hypothesis_id: str | None = None,
    *,
    source_url: str | None = None,
    cutoff_utc: str | None = None,
) -> dict[str, Any]:
    """Causal, bounded cross-contest *observation* learning.

    Uses only earlier checkpointed video-motion observations. No lottery results,
    downstream predictions, audio contents, or later/same-contest files are read.
    A checkpoint must match its recorded extractor fingerprint and video source.
    """
    root = Path(checkpoint_dir)
    target = str(contest_id)
    cutoff = None
    if cutoff_utc is not None:
        if not isinstance(cutoff_utc, str):
            raise ValueError("cutoff_utc must be a timezone-aware ISO-8601 timestamp")
        try:
            cutoff = datetime.fromisoformat(cutoff_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid cutoff_utc timestamp") from exc
        if cutoff.tzinfo is None or cutoff.utcoffset() is None:
            raise ValueError("cutoff_utc requires timezone")
        cutoff = cutoff.astimezone(timezone.utc)
    empty = {
        "schema": "SMART_VISUAL_OBSERVATION_PRIOR_V1",
        "status": "INACTIVE",
        "target_contest": target,
        "training_contests": [],
        "training_sha256": {},
        "eligible_observations": 0,
        "active": False,
        "normalized_event_center": None,
        "observed_spread": None,
        "predictive_evidence": PREDICTIVE_EVIDENCE,
        "scope": "SCIENTIFIC_VIDEO_MOTION_ONLY",
    }
    if not target.isascii() or not target.isdecimal() or not root.is_dir():
        return empty
    target_n = int(target)
    same_host = (
        "youtube.com" if _is_youtube_source(source_url or "")
        else (urlparse(source_url).hostname or "").lower()
    ) if source_url else None
    medians: list[float] = []
    digests: dict[str, str] = {}
    seen_videos: set[str] = set()
    forbidden_labels = {"winning_numbers", "drawn_numbers", "result_numbers", "dezenas_sorteadas", "hit_count"}
    # Bounded reads: checkpoints can be large, untrusted and concurrently written.
    # Prefer the most recent eligible past contests. Old/future files must
    # never consume the bounded reading budget.
    # Vendor-inspired staged indexing: enumerate metadata first, then validate
    # the original checkpoint bytes/fingerprint/PIT below (never trust the index).
    from isolated_source_gate.video_learning_fastpath import candidate_checkpoints
    from isolated_source_gate.checkpoint_cache import CheckpointCache
    cache = CheckpointCache(root / ".checkpoint_cache.sqlite")
    for path in candidate_checkpoints(root, target, limit=512):
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
                continue
        except OSError:
            continue
        stem = path.stem.removeprefix("contest_")
        if not stem.isascii() or not stem.isdecimal() or int(stem) >= target_n:
            continue
        try:
            row, verified_sha256 = cache.read(path)
            if (not isinstance(row, dict) or str(row.get("contest_id")) != stem
                    or forbidden_labels.intersection(row)
                    or row.get("extractor_version") != EXTRACTOR_VERSION
                    or row.get("hypothesis_id") != hypothesis_id
                    or row.get("status") != "CANDIDATE"
                    or row.get("predictive_evidence") != PREDICTIVE_EVIDENCE
                    or row.get("spatial_consensus", {}).get("recurrent") is not True):
                continue
            if cutoff is not None:
                observed_at = row.get("created_at_utc")
                if not isinstance(observed_at, str):
                    continue
                try:
                    observed_dt = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
                    if observed_dt.tzinfo is None or observed_dt.utcoffset() is None:
                        continue
                    if observed_dt.astimezone(timezone.utc) > cutoff:
                        continue
                except ValueError:
                    continue
            source = row.get("source")
            params = row.get("main_params")
            if not isinstance(source, str) or not isinstance(params, dict):
                continue
            source_host = "youtube.com" if _is_youtube_source(source) else (urlparse(source).hostname or "").lower()
            if same_host and source_host != same_host:
                continue
            if source in seen_videos:
                continue
            cfg = ObservationConfig(**params).validated()
            if row.get("checkpoint_fingerprint") != _observation_fingerprint(stem, source, cfg, hypothesis_id):
                continue
            if _is_youtube_source(source) and row.get("analysis_scope", {}).get("segment_guard_passed") is not True:
                continue
            scope = row.get("analysis_scope") or {}
            lo, hi = float(scope["start_s"]), float(scope["end_s"])
            if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
                continue
            events = [float(t) for t in row.get("event_timestamps_s") or []]
            if len(events) < cfg.min_candidate_events or not all(math.isfinite(t) and lo <= t <= hi for t in events):
                continue
            medians.append(statistics.median((t - lo) / (hi - lo) for t in events))
            seen_videos.add(source)
            digests[stem] = verified_sha256
        except (ValueError, KeyError, TypeError, OverflowError, OSError, json.JSONDecodeError):
            continue
    cache.close()
    if medians:
        center = statistics.median(medians)
        spread = statistics.pstdev(medians)
        # Do not promote 1-2 noisy videos or inconsistent broadcast edits.
        active = len(medians) >= 3 and spread <= 0.18
        empty.update(
            status="ACTIVE" if active else "SHADOW_INSUFFICIENT_CONSENSUS",
            training_contests=sorted(int(k) for k in digests),
            training_sha256=digests,
            eligible_observations=len(medians),
            active=active,
            normalized_event_center=round(center, 6),
            observed_spread=round(spread, 6),
        )
    return empty



def _archive_visual_learning_state(root: Path, memory: dict[str, Any]) -> None:
    """Preserve a validated memory revision as an immutable, digest-addressed file."""
    digest = memory.get("sha256")
    payload = dict(memory)
    payload.pop("sha256", None)
    expected = hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    if not isinstance(digest, str) or digest != expected:
        raise ValueError("visual learning history checksum invalid")
    history = root / "learning_history"
    if history.is_symlink():
        raise ValueError("visual learning history directory cannot be a symlink")
    history.mkdir(parents=True, exist_ok=True)
    destination = history / f"{digest}.json"
    serialized = json.dumps(memory, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or destination.read_bytes() != serialized:
            raise ValueError("visual learning history collision or corruption")
        return
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=history, prefix=f"{digest}.", suffix=".tmp", delete=False
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        # The atomic hard link fails rather than replacing an existing revision.
        try:
            os.link(temp_path, destination)
        except FileExistsError:
            if destination.is_symlink() or destination.read_bytes() != serialized:
                raise ValueError("visual learning history collision or corruption")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def persist_visual_learning_state(
    checkpoint_dir: str | Path,
    next_contest: str,
    hypothesis_id: str | None = None,
    *,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Incrementally publish the next-contest visual observation memory.

    Checkpoint files are never rewritten or treated as winning-number labels.
    Previous artifacts remain as immutable training references by SHA-256.
    """
    root = Path(checkpoint_dir)
    state_path = root / "SMART_VISUAL_LEARNING_STATE.json"
    next_contest = str(next_contest)
    if not next_contest.isascii() or not next_contest.isdecimal():
        raise ValueError("next_contest must be numeric")
    previous = None
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(previous, dict):
            raise ValueError("visual learning state is invalid")
        previous_copy = dict(previous)
        stored_digest = previous_copy.pop("sha256", None)
        calculated_digest = hashlib.sha256(json.dumps(
            previous_copy, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        if previous.get("schema") != "SMART_VISUAL_LEARNING_STATE_V1" or stored_digest != calculated_digest:
            raise ValueError("visual learning state checksum invalid; refusing to overwrite")
        previous_target = str(previous.get("next_contest", ""))
        if previous_target.isascii() and previous_target.isdecimal():
            next_contest = str(max(int(next_contest), int(previous_target)))
    profile = learned_motion_prior(root, next_contest, hypothesis_id, source_url=source_url)
    memory = {
        "schema": "SMART_VISUAL_LEARNING_STATE_V1",
        "next_contest": str(next_contest),
        "extractor_version": EXTRACTOR_VERSION,
        "source_host": (urlparse(source_url).hostname or "").lower() if source_url else None,
        "hypothesis_id": hypothesis_id,
        "observation_prior": profile,
        "training_contests": profile["training_contests"],
        "training_sha256": profile["training_sha256"],
        "training_observations": profile["eligible_observations"],
        "promotion_authorized": False,
        "same_contest_predictive_weight_authorized": False,
        "predictive_evidence": PREDICTIVE_EVIDENCE,
    }
    # Repeated learning with unchanged input must not manufacture new history.
    if previous is not None and all(
        previous.get(key) == value for key, value in memory.items()
    ) and set(previous).issubset(set(memory) | {"sha256", "previous_state_sha256"}):
        _archive_visual_learning_state(root, previous)
        return previous
    if previous is not None:
        # Archive the last good state before publishing its replacement.
        _archive_visual_learning_state(root, previous)
    memory["previous_state_sha256"] = previous["sha256"] if previous else None
    memory["sha256"] = hashlib.sha256(json.dumps(
        memory, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    # Durable archive is written first, then the latest pointer is replaced.
    _archive_visual_learning_state(root, memory)
    _atomic_json(state_path, memory)
    return memory

def should_reuse_checkpoint(existing: dict[str, Any] | None, extractor_version: str, hypothesis_id: str | None, force: bool, expected_fingerprint: str | None = None) -> bool:
    if force or not existing:
        return False
    if existing.get("extractor_version") != extractor_version or existing.get("hypothesis_id") != hypothesis_id:
        return False
    if expected_fingerprint is not None and existing.get("checkpoint_fingerprint") != expected_fingerprint:
        return False
    return existing.get("status") in {"CANDIDATE", "UNRESOLVED", "INSUFFICIENT_EVIDENCE"}


def _resource_snapshot() -> dict[str, Any]:
    try:
        import psutil
        proc = psutil.Process()
        ct = proc.cpu_times()
        net = psutil.net_io_counters()
        return {"cpu_s": float(ct.user + ct.system), "rss": int(proc.memory_info().rss), "net_bytes": int(net.bytes_sent + net.bytes_recv)}
    except Exception:
        return {"cpu_s": None, "rss": None, "net_bytes": None}


def _resource_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    def delta(key: str) -> Any:
        a, b = before.get(key), after.get(key)
        return None if a is None or b is None else max(0, b - a)
    return {
        "parent_cpu_seconds": delta("cpu_s"),
        "parent_rss_bytes_end": after.get("rss"),
        "network_bytes_system_delta_approx": delta("net_bytes"),
        "network_measurement_scope": "system-wide approximate; not attributed exclusively to extractor",
    }


def analyze_contest(
    contest_id: str,
    source_url: str,
    checkpoint_dir: str | Path = "runtime/video_observation",
    config: ObservationConfig | None = None,
    *,
    force: bool = False,
    hypothesis_id: str | None = None,
    resolver: Callable[[str, float], dict[str, Any]] = resolve_stream,
    sampler: Callable[[dict[str, Any], float], dict[str, Any]] = observe_short_sample,
    segment_locator: Callable[[str, str, float], dict[str, Any]] = locate_mega_segment,
    persist_memory: bool = True,
    frozen_learning_prior: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = (config or ObservationConfig()).validated()
    checkpoint_dir = Path(checkpoint_dir)
    cp_path = _checkpoint_path(checkpoint_dir, contest_id)
    fingerprint = _observation_fingerprint(str(contest_id), source_url, cfg, hypothesis_id)
    existing = _read_checkpoint(cp_path)
    if should_reuse_checkpoint(existing, EXTRACTOR_VERSION, hypothesis_id, force, fingerprint):
        reused = dict(existing)
        reused["checkpoint_reused"] = True
        if persist_memory and str(contest_id).isascii() and str(contest_id).isdecimal():
            # A valid checkpoint may outlive a deleted/interrupted state export.
            # Rebuild the consumer memory without fetching video or mutating
            # this checkpoint (its SHA-256 may already be referenced).
            try:
                memory = persist_visual_learning_state(
                    checkpoint_dir, str(int(contest_id) + 1), hypothesis_id,
                    source_url=source_url,
                )
                reused["learning_state_status"] = "PERSISTED"
                reused["learning_state_observations"] = memory["training_observations"]
            except (OSError, ValueError, TypeError) as exc:
                reused["learning_state_status"] = "UNAVAILABLE"
                reused.setdefault("limitations", []).append(
                    f"visual learning state unavailable: {type(exc).__name__}"
                )
        return reused

    learned_prior = (
        frozen_learning_prior if frozen_learning_prior is not None
        else learned_motion_prior(checkpoint_dir, str(contest_id), hypothesis_id, source_url=source_url)
    )
    started = time.monotonic()
    resources_before = _resource_snapshot()
    base: dict[str, Any] = {
        "schema": "smart.video_observation.v1",
        "contest_id": str(contest_id),
        "source": source_url,
        "extractor_version": EXTRACTOR_VERSION,
        "hypothesis_id": hypothesis_id,
        "checkpoint_fingerprint": fingerprint,
        "method": "STREAM_FIRST_COARSE_TO_FINE_INDEPENDENT_SHORT_SAMPLES",
        "predictive_evidence": PREDICTIVE_EVIDENCE,
        "semantic_label": None,
        "status": "UNRESOLVED",
        "confidence": 0.0,
        "event_timestamps_s": [],
        "created_at_utc": _utc_now(),
        "main_params": asdict(cfg),
        "analyzed_windows": [],
        "errors": [],
        "limitations": [
            "physical observation is separated from lottery result labels",
            "motion events are candidates, not confirmed ball/ejection semantics",
            "network byte delta is system-wide approximate when available",
        ],
        "media_persisted_bytes": 0,
        "checkpoint_reused": False,
        "learning_context": learned_prior,
    }

    def finish(status: str, **extra: Any) -> dict[str, Any]:
        base["status"] = status if status in VALID_STATUSES else "UNRESOLVED"
        base.update(extra)
        base["resource_metrics"] = _resource_delta(resources_before, _resource_snapshot())
        base["elapsed_s"] = round(time.monotonic() - started, 6)
        _atomic_json(cp_path, base)
        if persist_memory and str(contest_id).isascii() and str(contest_id).isdecimal():
            # A failed video cannot teach motion, but it still produces a
            # checkpoint and an explicit unchanged learning state.
            try:
                memory = persist_visual_learning_state(
                    checkpoint_dir, str(int(contest_id) + 1), hypothesis_id, source_url=source_url
                )
                base["learning_state_status"] = "PERSISTED"
                base["learning_state_observations"] = memory["training_observations"]
            except (OSError, ValueError, TypeError) as exc:
                base["learning_state_status"] = "UNAVAILABLE"
                base["limitations"].append(f"visual learning state unavailable: {type(exc).__name__}")
                # On failure no valid memory points at this checkpoint, so
                # persist the failure explicitly for later incident diagnosis.
                _atomic_json(cp_path, base)
        return base

    try:
        stream = resolver(source_url, cfg.resolver_timeout_s)
    except TimeoutError as exc:
        base["errors"].append(str(exc))
        return finish("TIMEOUT")
    except Exception as exc:
        base["errors"].append(f"{type(exc).__name__}: {exc}")
        return finish("STREAM_FAILED")

    base["video_id"] = stream.get("video_id")
    base["stream_provenance"] = {key: stream.get(key) for key in ("resolver", "format_id", "height", "width", "protocol", "duration_s", "title")}
    duration_s = float(stream.get("duration_s") or 0.0)
    if duration_s <= 0:
        duration_s = max(cfg.refine_window_s * 3, cfg.coarse_sample_s * cfg.coarse_points)
        base["limitations"].append("source duration unavailable; analysis horizon bounded conservatively")

    segment_required = _is_youtube_source(source_url)
    try:
        segment = segment_locator(source_url, str(contest_id), cfg.segment_locator_timeout_s) if segment_required else {"status": "NOT_APPLICABLE", "candidate_eligible": True}
    except Exception as exc:
        segment = {"status": "UNAVAILABLE", "candidate_eligible": False, "reason": f"{type(exc).__name__}: {exc}"}
    base["segment_locator"] = segment
    segment_guard_passed = (not segment_required) or (segment.get("status") == "PASS" and segment.get("candidate_eligible") is True)
    analysis_start, analysis_end = 0.0, duration_s
    if segment_guard_passed and segment_required:
        analysis_start = max(0.0, min(duration_s, float(segment.get("segment_start_s") or 0.0)))
        analysis_end = max(analysis_start, min(duration_s, float(segment.get("segment_end_s") or duration_s)))
    elif segment_required:
        base["limitations"].append("Mega-Sena segment locator did not pass; candidate promotion blocked")
    base["analysis_scope"] = {"start_s": round(analysis_start, 6), "end_s": round(analysis_end, 6), "segment_guard_passed": bool(segment_guard_passed)}

    coarse_times = coarse_timestamps(duration_s, cfg.coarse_points, cfg.coarse_sample_s, analysis_start, analysis_end)
    coarse = run_samples([_sample_spec(stream, t, cfg.coarse_sample_s, cfg) for t in coarse_times], sampler, cfg.sample_timeout_s, cfg.workers)
    summary_fields = ("status", "start_s", "duration_s", "mean_motion", "median_motion", "max_motion", "global_motion_fraction", "read_frames", "analyzed_frames", "error")
    base["coarse"] = [{key: row.get(key) for key in summary_fields if key in row} for row in coarse]
    if time.monotonic() - started > cfg.contest_timeout_s:
        return finish("TIMEOUT")
    ok_coarse = [row for row in coarse if row.get("status") == "OK"]
    if not ok_coarse:
        return finish("TIMEOUT" if any(row.get("status") == "TIMEOUT" for row in coarse) else "UNOBSERVABLE")

    regions = select_promising_regions(coarse, cfg, duration_s, analysis_start, analysis_end, learned_prior)
    if not regions:
        total_observed = sum(float(row.get("duration_s") or cfg.coarse_sample_s) for row in ok_coarse)
        return finish("INSUFFICIENT_EVIDENCE", observed_seconds_requested=round(total_observed, 6), video_duration_s=round(duration_s, 6), coverage_ratio=round(min(1.0, total_observed / duration_s), 6))

    refined = run_samples([_sample_spec(stream, t, cfg.refine_window_s, cfg) for t in regions], sampler, cfg.sample_timeout_s, cfg.workers)
    base["analyzed_windows"] = [{key: row.get(key) for key in summary_fields if key in row} for row in refined]
    if time.monotonic() - started > cfg.contest_timeout_s:
        return finish("TIMEOUT")
    ok_refined = [row for row in refined if row.get("status") == "OK"]
    if not ok_refined:
        return finish("TIMEOUT" if any(row.get("status") == "TIMEOUT" for row in refined) else "UNOBSERVABLE")

    all_events: list[float] = []
    event_groups: list[list[float]] = []
    for sample in ok_refined:
        group = sorted(set(round(value, 6) for value in detect_events(sample, cfg)))
        event_groups.append(group)
        all_events.extend(group)
    all_events = sorted(set(all_events))
    spatial = spatial_classification(ok_refined)
    spatial_alt = spatial_classification(ok_refined, "grid_energy_alt")
    cadence = cadence_metrics(all_events, event_groups)
    base["event_timestamps_s"] = all_events
    base["cadence"] = cadence
    base["spatial"] = spatial
    base["spatial_alt"] = spatial_alt
    spatial_consensus = spatial.get("classification") == "RECURRENT_SOURCE_REGION_CANDIDATE" and spatial_alt.get("classification") == "RECURRENT_SOURCE_REGION_CANDIDATE"
    base["spatial_consensus"] = {"required": True, "recurrent": spatial_consensus, "primary": spatial.get("classification"), "secondary": spatial_alt.get("classification")}

    total_observed = len(ok_coarse) * cfg.coarse_sample_s + len(ok_refined) * cfg.refine_window_s
    base["observed_seconds_requested"] = round(total_observed, 6)
    base["video_duration_s"] = round(duration_s, 6)
    base["coverage_ratio"] = round(min(1.0, total_observed / duration_s), 6)
    scope_duration = max(0.0, analysis_end - analysis_start)
    base["analysis_scope_coverage_ratio"] = round(min(1.0, total_observed / scope_duration), 6) if scope_duration > 0 else None

    enough_events = len(all_events) >= cfg.min_candidate_events
    if enough_events and spatial_consensus and segment_guard_passed:
        base["semantic_label"] = "MOTION_EVENT_CANDIDATE"
        regularity = cadence.get("regularity")
        activity = max(float(row.get("mean_motion") or 0.0) for row in ok_refined)
        confidence = min(0.95, 0.35 + min(0.30, len(all_events) * 0.04) + min(0.20, activity * 3.0) + 0.10 * float(regularity or 0.0))
        return finish("CANDIDATE", confidence=round(confidence, 6))

    if all_events:
        base["semantic_label"] = "MOTION_EVENT_CANDIDATE"
    if spatial.get("classification") == "GLOBAL_MOTION_OR_CAMERA_CHANGE":
        base["limitations"].append("motion pattern is spatially consistent with global motion/camera change")
    if all_events and not enough_events:
        base["limitations"].append("too few recurrent events for candidate status")
    if all_events and not spatial_consensus:
        base["limitations"].append("no stable recurrent source region was established")
    if all_events and spatial.get("classification") == "RECURRENT_SOURCE_REGION_CANDIDATE" and not spatial_consensus:
        base["limitations"].append("recurrent region was not stable across spatial grid resolutions")
    if all_events and spatial_consensus and not segment_guard_passed:
        base["limitations"].append("recurrent motion was detected outside a proven Mega-Sena segment guard")
    return finish("INSUFFICIENT_EVIDENCE", confidence=0.0)


def analyze_queue(
    items: Iterable[dict[str, Any]],
    checkpoint_dir: str | Path = "runtime/video_observation",
    config: ObservationConfig | None = None,
    *,
    force: bool = False,
    hypothesis_id: str | None = None,
    resolver: Callable[[str, float], dict[str, Any]] = resolve_stream,
    sampler: Callable[[dict[str, Any], float], dict[str, Any]] = observe_short_sample,
    segment_locator: Callable[[str, str, float], dict[str, Any]] = locate_mega_segment,
) -> list[dict[str, Any]]:
    cfg = (config or ObservationConfig()).validated()
    root = Path(checkpoint_dir)
    results: list[dict[str, Any]] = []
    for item in items:
        contest_id = str(item.get("contest_id") or item.get("contest") or "").strip()
        source_url = str(item.get("source_url") or item.get("url") or "").strip()
        item_hypothesis = item.get("hypothesis_id", hypothesis_id)
        item_force = bool(item.get("force", force))
        if not contest_id or not source_url:
            fallback = {
                "schema": "smart.video_observation.v1",
                "contest_id": contest_id or "unknown",
                "source": source_url or None,
                "extractor_version": EXTRACTOR_VERSION,
                "hypothesis_id": item_hypothesis,
                "method": "STREAM_FIRST_COARSE_TO_FINE_INDEPENDENT_SHORT_SAMPLES",
                "predictive_evidence": PREDICTIVE_EVIDENCE,
                "semantic_label": None,
                "status": "UNRESOLVED",
                "confidence": 0.0,
                "event_timestamps_s": [],
                "created_at_utc": _utc_now(),
                "errors": ["queue item requires contest_id and source_url"],
                "limitations": ["invalid queue item; observation not attempted"],
                "media_persisted_bytes": 0,
                "checkpoint_reused": False,
            }
            if contest_id:
                _atomic_json(_checkpoint_path(root, contest_id), fallback)
            results.append(fallback)
            continue
        try:
            result = analyze_contest(
                contest_id,
                source_url,
                root,
                cfg,
                force=item_force,
                hypothesis_id=item_hypothesis,
                resolver=resolver,
                sampler=sampler,
                segment_locator=segment_locator,
            )
        except Exception as exc:
            result = {
                "schema": "smart.video_observation.v1",
                "contest_id": contest_id,
                "source": source_url,
                "extractor_version": EXTRACTOR_VERSION,
                "hypothesis_id": item_hypothesis,
                "method": "STREAM_FIRST_COARSE_TO_FINE_INDEPENDENT_SHORT_SAMPLES",
                "predictive_evidence": PREDICTIVE_EVIDENCE,
                "semantic_label": None,
                "status": "UNRESOLVED",
                "confidence": 0.0,
                "event_timestamps_s": [],
                "created_at_utc": _utc_now(),
                "errors": [f"{type(exc).__name__}: {exc}"],
                "limitations": ["unexpected contest failure isolated; queue continued"],
                "media_persisted_bytes": 0,
                "checkpoint_reused": False,
            }
            _atomic_json(_checkpoint_path(root, contest_id), result)
        results.append(result)
    return results


def _main() -> int:
    parser = argparse.ArgumentParser(description="SMART stream-first physical video observation extractor")
    parser.add_argument("--contest", required=True)
    parser.add_argument("--url")
    parser.add_argument("--learn-only", action="store_true",
                        help="Learn from existing checkpoints for --contest; do not fetch video")
    parser.add_argument("--checkpoint-dir", default="runtime/video_observation")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--hypothesis-id")
    args = parser.parse_args()
    if args.learn_only:
        if not str(args.contest).isascii() or not str(args.contest).isdecimal():
            parser.error("--learn-only requires numeric --contest (next contest)")
        result = persist_visual_learning_state(
            args.checkpoint_dir, args.contest, args.hypothesis_id, source_url=args.url
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not args.url:
        parser.error("--url is required for observation")
    result = analyze_contest(
        args.contest,
        args.url,
        args.checkpoint_dir,
        ObservationConfig(workers=args.workers),
        force=args.force,
        hypothesis_id=args.hypothesis_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
