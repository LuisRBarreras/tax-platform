"""Read the fields we care about from a CFDI 4.0 (Mexican e-invoice) XML.

The SAT stamps every invoice with a namespace that changes between versions, so
everything here matches on local tag names instead of the full qualified ones.
Anything missing comes back as an empty string or `None`, never as an exception:
a malformed attachment must not sink the whole mailbox scan.
"""
import re
from typing import Any, Dict, Optional
from xml.etree import ElementTree as ET

# "…correspondientes al periodo de Octubre del 2026"
# "…correspondientes al mes de Marzo de 2025"
PERIOD_RE = re.compile(
    r"(?:mes|periodo)\s+de\s+([A-Za-zÁÉÍÓÚÜáéíóúü]+)\s+de[l]?\s+(\d{4})", re.IGNORECASE
)

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def _plain(text: str) -> str:
    for accented, plain in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        text = text.replace(accented, plain)
    return text.lower().strip()


def period_from_text(text: str) -> str:
    """'…periodo de Octubre del 2026' -> '2026-10'. Empty when the text is silent."""
    match = PERIOD_RE.search(text or "")
    if not match:
        return ""
    month = MONTHS.get(_plain(match.group(1)))
    return f"{match.group(2)}-{month:02d}" if month else ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(element, name: str):
    for child in element:
        if _local(child.tag) == name:
            return child
    return None


def _descendant(element, name: str):
    for node in element.iter():
        if _local(node.tag) == name:
            return node
    return None


def _amount(value: Any) -> Optional[float]:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def parse(xml_bytes: bytes) -> Dict[str, Any]:
    """Invoice number, dates, amounts and issuer from the CFDI."""
    data: Dict[str, Any] = {
        "folio": "",
        "cfdi_fecha": "",
        "uuid": "",
        "total": None,
        "subtotal": None,
        "currency": "MXN",
        "issuer_name": "",
        "issuer_rfc": "",
        "description": "",
        "period": "",
    }
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return data
    if _local(root.tag) != "Comprobante":
        return data

    attributes = root.attrib
    data["folio"] = (attributes.get("Folio") or "").strip()
    data["cfdi_fecha"] = (attributes.get("Fecha") or "").strip()
    data["currency"] = (attributes.get("Moneda") or "MXN").strip() or "MXN"
    data["total"] = _amount(attributes.get("Total"))
    data["subtotal"] = _amount(attributes.get("SubTotal"))

    issuer = _child(root, "Emisor")
    if issuer is not None:
        data["issuer_name"] = (issuer.attrib.get("Nombre") or "").strip()
        data["issuer_rfc"] = (issuer.attrib.get("Rfc") or "").strip()

    concept = _descendant(root, "Concepto")
    if concept is not None:
        data["description"] = (concept.attrib.get("Descripcion") or "").strip()
        data["period"] = period_from_text(data["description"])

    stamp = _descendant(root, "TimbreFiscalDigital")
    if stamp is not None:
        data["uuid"] = (stamp.attrib.get("UUID") or "").strip().upper()

    return data
