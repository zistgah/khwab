"""Small TEI apparatus reader for comparing witness readings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

TEI_NAMESPACE = "{http://www.tei-c.org/ns/1.0}"
XML_NAMESPACE = "{http://www.w3.org/XML/1998/namespace}"


@dataclass(frozen=True)
class Reading:
    witness: str
    text: str
    kind: str


@dataclass(frozen=True)
class Variant:
    variant_id: str
    readings: tuple[Reading, ...]


def _element_text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def read_tei(path: str | Path) -> tuple[Variant, ...]:
    """Read TEI apparatus entries without interpreting signatures or authority."""
    source_path = Path(path)
    try:
        root = ET.parse(source_path).getroot()
    except ET.ParseError as error:
        raise ValueError(f"{source_path}: invalid TEI XML: {error}") from error
    variants: list[Variant] = []

    for index, app in enumerate(root.iter(f"{TEI_NAMESPACE}app"), start=1):
        readings: list[Reading] = []
        for tag, kind in (("lem", "lemma"), ("rdg", "variant")):
            for element in app.findall(f"{TEI_NAMESPACE}{tag}"):
                text = _element_text(element)
                if not text:
                    raise ValueError(f"{source_path}: empty {tag} in apparatus entry")
                witness_value = element.get("wit", "").strip()
                witnesses = witness_value.split() if witness_value else ["unassigned"]
                readings.extend(Reading(witness, text, kind) for witness in witnesses)
        if not readings:
            raise ValueError(f"{source_path}: apparatus entry has no lemma or readings")
        variant_id = app.get(f"{XML_NAMESPACE}id") or app.get("n") or f"app-{index}"
        variants.append(Variant(variant_id, tuple(readings)))
    return tuple(variants)


def collate(paths: list[str | Path]) -> dict[str, object]:
    """Return a stable variant table across one or more TEI witness files."""
    if not paths:
        raise ValueError("at least one TEI file is required")

    sources: list[dict[str, object]] = []
    variants_by_id: dict[str, list[dict[str, str]]] = {}
    for path in paths:
        source_path = Path(path)
        variants = read_tei(source_path)
        sources.append({"path": str(source_path), "apparatus_entries": len(variants)})
        for variant in variants:
            target = variants_by_id.setdefault(variant.variant_id, [])
            target.extend(
                {
                    "source": str(source_path),
                    "witness": reading.witness,
                    "kind": reading.kind,
                    "text": reading.text,
                }
                for reading in variant.readings
            )

    return {
        "sources": sources,
        "variants": [
            {"variant_id": variant_id, "readings": variants_by_id[variant_id]}
            for variant_id in sorted(variants_by_id)
        ],
    }


def export_tei_apparatus(collation: dict[str, object]) -> str:
    """Serialize a collation result as a TEI apparatus document.

    The output preserves each supplied witness reading; it does not select a
    preferred lemma or assert scholarly authority.
    """
    variants = collation.get("variants")
    if not isinstance(variants, list):
        raise ValueError("collation must contain a variants list")

    root = ET.Element(f"{TEI_NAMESPACE}TEI")
    text = ET.SubElement(root, f"{TEI_NAMESPACE}text")
    body = ET.SubElement(text, f"{TEI_NAMESPACE}body")
    for index, variant in enumerate(variants, start=1):
        if not isinstance(variant, dict):
            raise ValueError(f"variants[{index - 1}] must be an object")
        variant_id = variant.get("variant_id")
        if not isinstance(variant_id, str) or not variant_id.strip():
            raise ValueError(f"variants[{index - 1}].variant_id must be non-empty")
        readings = variant.get("readings")
        if not isinstance(readings, list) or not readings:
            raise ValueError(f"variants[{index - 1}].readings must be non-empty")
        app = ET.SubElement(body, f"{TEI_NAMESPACE}app")
        app.set(f"{XML_NAMESPACE}id", variant_id)
        for reading_index, reading in enumerate(readings):
            if not isinstance(reading, dict):
                raise ValueError(
                    f"variants[{index - 1}].readings[{reading_index}] must be an object"
                )
            text_value = reading.get("text")
            witness = reading.get("witness")
            kind = reading.get("kind")
            if not isinstance(text_value, str) or not text_value.strip():
                raise ValueError("each reading text must be non-empty")
            if not isinstance(witness, str) or not witness.strip():
                raise ValueError("each reading witness must be non-empty")
            if kind not in {"lemma", "variant"}:
                raise ValueError("reading kind must be lemma or variant")
            tag = "lem" if kind == "lemma" else "rdg"
            element = ET.SubElement(app, f"{TEI_NAMESPACE}{tag}")
            element.set("wit", witness)
            element.text = text_value

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
