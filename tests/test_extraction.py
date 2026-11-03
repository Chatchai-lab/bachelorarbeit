import json

from extraction.parsing import parse_model_output
from extraction.prompts import SCHEMA_HINWEISE, build_messages, json_schema, prompt_hash


def test_reines_json():
    obj, err = parse_model_output('{"netto": 100.5}')
    assert err is None and obj == {"netto": 100.5}


def test_json_in_codeblock():
    obj, err = parse_model_output('```json\n{"iban": null}\n```')
    assert err is None and obj == {"iban": None}


def test_text_vor_und_nach_json():
    obj, err = parse_model_output('Hier ist das Ergebnis:\n{"a": 1}\nIch hoffe, das hilft.')
    assert err is None and obj == {"a": 1}


def test_unbrauchbare_ausgaben():
    assert parse_model_output("")[1] == "leere Antwort"
    assert parse_model_output("Keine Daten gefunden.")[1] == "kein JSON-Objekt gefunden"
    assert parse_model_output('{"a": 1,')[1].startswith("ungültiges JSON")
    assert parse_model_output("[1, 2]")[1].startswith("JSON ist kein Objekt")


def test_prompt_enthaelt_dokument_und_schema():
    msgs = build_messages("vertrag", "Dienstleistungsvertrag\n§ 1 ...")
    assert msgs[0]["role"] == "system"
    assert "Dienstleistungsvertrag\n§ 1 ..." in msgs[1]["content"]
    assert "kuendigungsfrist" in msgs[1]["content"]


def test_schema_hinweise_decken_ground_truth_ab():
    from common.schemas import Rechnung, Vertrag

    for typ, model in [("rechnung", Rechnung), ("vertrag", Vertrag)]:
        felder = set(model.model_fields) - {"dokument_typ"}
        assert felder == set(SCHEMA_HINWEISE[typ])
        schema = json_schema(typ)
        assert "dokument_typ" not in schema["properties"]
        json.dumps(schema)


def test_prompt_hash_stabil():
    assert prompt_hash() == prompt_hash() and len(prompt_hash()) == 12


def test_text_schema_feste_felder_nur_text():
    from extraction.prompts import text_schema

    s = text_schema("rechnung")
    assert s["additionalProperties"] is False
    assert set(s["required"]) == set(SCHEMA_HINWEISE["rechnung"])
    assert s["properties"]["netto"] == {"type": ["string", "null"]}
    pos = s["properties"]["positionen"]["items"]
    assert pos["properties"]["menge"] == {"type": ["string", "null"]}
    json.dumps(s)
