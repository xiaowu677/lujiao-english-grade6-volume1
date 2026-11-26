import hashlib
import json
import re
from pathlib import Path


COURSES = {
    "grade6": {
        "label": "六年级上册",
        "pattern": re.compile(
            r"^v2\.1-(?:unit[1-6]|bridging-unit[1-3])(?:-key)?$"
        ),
        "audio_key": "v2.1",
    },
    "grade7": {
        "label": "七年级上册",
        "pattern": re.compile(r"^g7-v1-unit[1-7](?:-core)?$"),
        "audio_key": "g7-v1",
    },
}


def _read_json_constant(source, marker, next_marker):
    start = source.index(marker) + len(marker)
    end = source.index(next_marker, start)
    payload = source[start:end].strip().removeprefix("=").strip()
    if payload.endswith(";"):
        payload = payload[:-1].rstrip()
    return json.loads(payload)


def _audio_id(kind, text):
    digest = hashlib.sha256(f"{kind}\0{text}".encode("utf-8")).hexdigest()
    return f"{kind}-{digest[:16]}"


def _add_item(items, kind, text, source_unit, course):
    normalized = " ".join(str(text).split())
    key = (kind, normalized)
    if key not in items:
        audio_id = _audio_id(kind, normalized)
        items[key] = {
            "id": audio_id,
            "kind": kind,
            "text": normalized,
            "filename": f"{audio_id}.mp3",
            "course": course,
            "sources": [],
        }
    source = items[key]["sources"]
    if source_unit not in source:
        source.append(source_unit)


def build_catalog(repo_root, course="grade6"):
    if course not in COURSES:
        raise ValueError(f"Unknown course: {course}")
    course_config = COURSES[course]
    repo_root = Path(repo_root)
    outputs = repo_root / "outputs"
    page_dirs = sorted(
        (
            path
            for path in outputs.iterdir()
            if path.is_dir() and course_config["pattern"].fullmatch(path.name)
        ),
        key=lambda path: path.name,
    )
    items = {}

    for page_dir in page_dirs:
        source = (page_dir / "index.html").read_text(encoding="utf-8")
        words = _read_json_constant(source, "const WORDS =", "const CONTEXT_SCENES =")
        scenes = _read_json_constant(
            source, "const CONTEXT_SCENES =", "const CONTEXTS ="
        )
        contexts = _read_json_constant(
            source, "const CONTEXTS =", "const CONTEXT_ACCEPTANCE_STAGES ="
        )

        for word in words:
            _add_item(items, "word", word["en"], page_dir.name, course)
            context = contexts[word["en"]]
            training = context["trainingSentence"].replace("{{word}}", word["en"])
            acceptance = context["acceptanceSentence"].replace("{{word}}", word["en"])
            _add_item(items, "training", training, page_dir.name, course)
            _add_item(items, "acceptance", acceptance, page_dir.name, course)

        for scene in scenes:
            _add_item(items, "story", scene["story"], page_dir.name, course)

    kind_order = {"word": 0, "training": 1, "acceptance": 2, "story": 3}
    return sorted(
        items.values(),
        key=lambda item: (kind_order[item["kind"]], item["sources"][0], item["id"]),
    )


if __name__ == "__main__":
    catalog = build_catalog(Path(__file__).resolve().parents[2])
    counts = {}
    for entry in catalog:
        counts[entry["kind"]] = counts.get(entry["kind"], 0) + 1
    print(json.dumps({"total": len(catalog), "counts": counts}, ensure_ascii=False))
