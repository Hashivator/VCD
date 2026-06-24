# Timeline reader and renderer
from pathlib import Path
from typing import Optional
from xml.dom import minidom
import xml.etree.ElementTree as ET

from vcd.logger import log
from vcd.core.media import probe_duration


# XML timing extraction
def find_base_tick_from_xml(xml_path: Path) -> Optional[int]:
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
    except ET.ParseError as exc:
        log(f"Cannot parse {xml_path.name}: {exc}", "WARN")
        return None

    best_base: Optional[int] = None
    earliest_time = float("inf")

    for elem in root.findall(".//Message"):
        method_el = elem.find("Method")
        if (
            method_el is None
            or not method_el.text
            or "pacingTick" not in method_el.text
        ):
            continue
        time_str = elem.get("time")
        number = elem.find("Number")
        if time_str is None or number is None or not number.text:
            continue
        try:
            offset = int(time_str.strip())
            tick = int(number.text.strip())
        except ValueError:
            continue
        if offset < 0:
            continue
        if offset < earliest_time:
            earliest_time = offset
            best_base = tick - offset

    return best_base


def collect_media_intervals(
    media_folder: Path,
    ffprobe_path: str,
) -> tuple[list[dict], list[dict], Optional[int]]:
    xml_files = list(media_folder.glob("*.xml"))
    xml_bases: dict[str, int] = {}

    log("Extracting base ticks from XML …")
    for xp in xml_files:
        b = find_base_tick_from_xml(xp)
        if b is not None:
            xml_bases[xp.stem] = b

    if not xml_bases:
        return [], [], None

    global_base = min(xml_bases.values())
    log(f"Global base tick: {global_base}")

    screen_clips: list[dict] = []
    audio_clips: list[dict] = []

    for flv in sorted(media_folder.glob("*.flv")):
        stem = flv.stem
        if stem not in xml_bases:
            log(f"  ⚠  {flv.name} – no valid pacingTick", "WARN")
            continue

        has_video = contains_stream(ffprobe_path, flv, "video")
        has_audio = contains_stream(ffprobe_path, flv, "audio")
        if not has_video and not has_audio:
            log(f"  ⚠  {flv.name} – no usable stream", "WARN")
            continue

        dur_sec = probe_duration(ffprobe_path, flv)
        if dur_sec <= 0:
            log(f"  ⚠  {flv.name} – zero duration", "WARN")
            continue

        start_ms = max(0.0, xml_bases[stem] - global_base)
        duration_ms = dur_sec * 1000.0
        entry = {
            "file": flv,
            "start_ms": start_ms,
            "end_ms": start_ms + duration_ms,
            "duration_ms": duration_ms,
        }

        if has_video and flv.name.startswith("screenshare"):
            screen_clips.append(entry)
        if has_audio:
            audio_clips.append(entry)

        log(f"   {flv.name}: {start_ms / 1000:.1f}s → {entry['end_ms'] / 1000:.1f}s")

    return screen_clips, audio_clips, global_base


# Timeline builder
def _build_continuous_segments(clips: list[dict], total_ms: float) -> list[dict]:
    bps = sorted(
        {0.0, total_ms} | {c["start_ms"] for c in clips} | {c["end_ms"] for c in clips}
    )
    segs: list[dict] = []
    for i in range(len(bps) - 1):
        s, e = bps[i], bps[i + 1]
        if e <= s:
            continue
        covering = [c for c in clips if c["start_ms"] <= s and c["end_ms"] >= e]
        chosen = (
            max(covering, key=lambda x: x["start_ms"])["file"] if covering else None
        )
        if segs and segs[-1]["file"] == chosen:
            segs[-1]["end"] = e
        else:
            segs.append({"start": s, "end": e, "file": chosen})
    return segs


def _build_audio_mix_segments(audio_clips: list[dict], total_ms: float) -> list[dict]:
    bps = sorted(
        {0.0, total_ms}
        | {c["start_ms"] for c in audio_clips}
        | {c["end_ms"] for c in audio_clips}
    )
    segs: list[dict] = []
    for i in range(len(bps) - 1):
        s, e = bps[i], bps[i + 1]
        if e <= s:
            continue
        active = [c for c in audio_clips if c["start_ms"] <= s and c["end_ms"] >= e]
        if segs and segs[-1]["files"] == active:
            segs[-1]["end"] = e
        else:
            segs.append({"start": s, "end": e, "files": active})
    return segs


def write_timeline_xml(
    screen_clips: list[dict],
    audio_clips: list[dict],
    total_ms: float,
    out_path: Path,
) -> None:
    v_segs = _build_continuous_segments(screen_clips, total_ms)
    a_segs = _build_audio_mix_segments(audio_clips, total_ms)

    all_t = sorted(
        {s["start"] for s in v_segs + a_segs} | {s["end"] for s in v_segs + a_segs}
    )

    def vid_at(t: float):
        for s in v_segs:
            if s["start"] <= t < s["end"]:
                return s["file"]
        return None

    def aud_at(t: float):
        for s in a_segs:
            if s["start"] <= t < s["end"]:
                return s["files"]
        return []

    fmap: dict = {c["file"]: c["start_ms"] for c in screen_clips + audio_clips}

    root = ET.Element("timeline")
    ET.SubElement(root, "total_duration_ms").text = str(int(total_ms))
    segs_el = ET.SubElement(root, "segments")

    for i in range(len(all_t) - 1):
        t0, t1 = all_t[i], all_t[i + 1]
        if t1 <= t0:
            continue
        mid = (t0 + t1) / 2
        vf = vid_at(mid)
        af = aud_at(mid)
        dur = t1 - t0

        seg = ET.SubElement(segs_el, "segment", start=str(int(t0)), end=str(int(t1)))
        if vf is None:
            ET.SubElement(seg, "video", file="black")
        else:
            ET.SubElement(
                seg,
                "video",
                file=vf.name,
                offset=str(round((t0 - fmap[vf]) / 1000, 3)),
                dur=str(round(dur / 1000, 3)),
            )
        if not af:
            ET.SubElement(seg, "audio", file="silence")
        else:
            for ac in af:
                ET.SubElement(
                    seg,
                    "audio",
                    file=ac["file"].name,
                    offset=str(round((t0 - fmap[ac["file"]]) / 1000, 3)),
                    dur=str(round(dur / 1000, 3)),
                )

    pretty = minidom.parseString(ET.tostring(root, encoding="utf-8")).toprettyxml(
        indent="  ", encoding="utf-8"
    )
    out_path.write_bytes(pretty)
    log(f"✅ timeline.xml → {out_path}", "SUCCESS")


def _read_timeline_xml(path: Path) -> tuple[list[dict], dict, int]:
    tree = ET.parse(str(path))
    root = tree.getroot()
    total_ms = int(root.find("total_duration_ms").text)  # type: ignore
    video_plan: list[dict] = []
    audio_meta: dict[str, dict] = {}

    for seg in root.findall(".//segment"):
        ss = int(seg.get("start"))  # type: ignore
        se = int(seg.get("end"))  # type: ignore
        ve = seg.find("video")
        vf = ve.get("file") if ve is not None else "black"
        if vf and vf != "black":
            vo = float(ve.get("offset", 0))  # type: ignore
            vd = float(ve.get("dur", (se - ss) / 1000))  # type: ignore
        else:
            vo, vf, vd = None, "black", (se - ss) / 1000
        video_plan.append(
            {"start_ms": ss, "end_ms": se, "file": vf, "offset": vo, "dur": vd}
        )

        for ae in seg.findall("audio"):
            af = ae.get("file")
            if af == "silence":
                continue
            sd = float(ae.get("dur", (se - ss) / 1000)) * 1000
            om = float(ae.get("offset", 0)) * 1000
            if af not in audio_meta:
                audio_meta[af] = {
                    "first_start_ms": ss,
                    "first_offset_ms": om,
                    "latest_end_ms": ss + sd,
                }
            else:
                info = audio_meta[af]
                if ss < info["first_start_ms"]:
                    info["first_start_ms"] = ss
                    info["first_offset_ms"] = om
                info["latest_end_ms"] = max(info["latest_end_ms"], ss + sd)
    return video_plan, audio_meta, total_ms
