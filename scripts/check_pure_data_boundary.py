"""Finite #0131 schema/envelope model; no filter parser, runtime or media I/O."""
from decimal import Decimal
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/legacy-compatibility/pure-data"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def members(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate member")
        result[key] = value
    return result


def number(token):
    require(len(token) <= 128, "numeric token bytes")
    exponent = re.search(r"[eE]([+-]?\d+)$", token)
    require(not exponent or abs(int(exponent[1])) <= 308, "exponent")
    return Decimal(token)


def read_request(raw):
    require(len(raw.encode("utf-8")) <= 65536, "request bytes")
    require(not raw.startswith("\ufeff"), "BOM")
    return json.loads(raw, object_pairs_hook=members, parse_int=number,
                      parse_float=number,
                      parse_constant=lambda _: require(False, "non-JSON number"))


def kind(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float, Decimal)):
        return "number"
    return {str: "string", dict: "object", list: "array"}.get(type(value))


def shape(value, schema):
    """Only keywords used by the frozen schema; fail closed on new keywords."""
    allowed = {"$schema", "$id", "type", "const", "enum", "pattern", "minLength",
               "maxLength", "maxItems", "items", "required", "properties",
               "additionalProperties"}
    require(set(schema) <= allowed, "unsupported schema keyword")
    if "type" in schema:
        types = schema["type"]
        require(kind(value) in (types if isinstance(types, list) else [types]), "type")
    if "const" in schema:
        require(value == schema["const"], "constant")
    if "enum" in schema:
        require(value in schema["enum"], "enum")
    if isinstance(value, dict):
        require(set(schema.get("required", [])) <= set(value), "required")
        properties = schema.get("properties", {})
        require(schema.get("additionalProperties") is False, "closed object schema")
        require(set(value) <= set(properties), "unknown member")
        for key, item in value.items():
            shape(item, properties[key])
    elif isinstance(value, list):
        require(len(value) <= schema.get("maxItems", len(value)), "item count")
        for item in value:
            shape(item, schema["items"])
    elif isinstance(value, str):
        require(len(value) >= schema.get("minLength", 0), "minimum length")
        require(len(value) <= schema.get("maxLength", len(value)), "maximum length")
        if "pattern" in schema:
            require(re.fullmatch(schema["pattern"], value, flags=re.ASCII), "pattern")


def envelope(request, schema, registry):
    shape(request, schema)
    require(request["registryRevision"] == registry["revision"], "registry revision")
    names = set(registry["builtinNames"])
    expanded = {tuple(pair) for pair in registry["builtinExpandedNames"]}
    for group in ("aliases", "parameters", "definitions"):
        for declaration in request[group]:
            require(declaration["name"] not in names, "name collision")
            names.add(declaration["name"])
            if group == "aliases":
                require(declaration["selector"] in registry["selectors"], "selector")
            elif group == "parameters":
                value = declaration["value"]
                if declaration["type"] == "integer":
                    require(kind(value) == "number" and value == value.to_integral_value(),
                            "integer parameter")
                else:
                    require(kind(value) == declaration["type"], "parameter type")
            else:
                require(re.fullmatch(
                    r"[A-Za-z][A-Za-z0-9+.-]*:(?:[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=-]|%[0-9A-Fa-f]{2})+",
                    declaration["namespace"]),
                        "absolute namespace URI")
                identity = (declaration["namespace"], declaration["localName"])
                require(identity not in expanded, "expanded-name collision")
                expanded.add(identity)

    def byte_bounds(value, field=""):
        if isinstance(value, dict):
            for key, item in value.items():
                byte_bounds(item, key)
        elif isinstance(value, list):
            for item in value:
                byte_bounds(item, field)
        elif isinstance(value, str):
            require(len(value.encode("utf-8")) <= (4096 if field == "expression" else 1024),
                    "UTF-8 field bytes")
    byte_bounds(request)


def main():
    schema = json.loads((DATA / "request.schema.v1.json").read_text(encoding="utf-8"))
    vectors = json.loads((DATA / "vectors.v1.json").read_text(encoding="utf-8"))
    dispositions = ["planned-filter", "planned-bindings", "planned-definition",
                    "refuse-calculation", "independent-date-mapping", "refuse-formatting",
                    "refuse-module", "refuse-lookup", "refuse-hook"]
    require(vectors["extTrace"] == [
        {"id": f"EXT-{i:03}", "disposition": disposition}
        for i, disposition in enumerate(dispositions, 1)], "EXT trace")
    require(set(vectors["futureEvidence"]) == {
        "parser-and-limits", "three-valued-evaluation", "native-request-isolation",
        "actual-authority-refusal"}, "unrun implementation cells")
    cases = vectors["cases"] + vectors["rawCases"]
    require(len({case["id"] for case in cases}) == len(cases), "case identifiers")
    for case in cases:
        raw = case.get("input", json.dumps(case.get("request"), ensure_ascii=True))
        try:
            envelope(read_request(raw), schema, vectors["registry"])
            actual = "accept"
        except (ValueError, UnicodeError):
            actual = "refuse"
        require(actual == case["expected"], f"{case['id']}: expected {case['expected']}, got {actual}")
    print(f"#0131: {len(cases)} authored envelope vectors and all 9 EXT dispositions pass; "
          "filter parser/evaluator and native authority evidence remain unrun")


if __name__ == "__main__":
    main()
