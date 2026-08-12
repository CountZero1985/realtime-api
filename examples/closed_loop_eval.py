"""Score a recorded translator session against an independent reference.

Every field test so far used a different moment of a different video, so
nothing was comparable and no change could be shown to have helped. This takes
the two WAV files the app records in one run — what it heard and what it said —
and produces a repeatable score against a reference built separately.

The reference deliberately does NOT come from the realtime API. Using it would
grade the model against itself, and every mistake it makes consistently would
score as correct. Instead: an accurate transcription of the input, then a
translation by a text model that has the whole passage at once and no latency
budget. That is the best the content allows, which is the right thing to
measure a real-time system against.

What it reports:
  * the reference and the app's output, side by side, for reading;
  * per reference sentence, the best semantic match in the app's output, so
    dropped content shows up as a specific missing sentence rather than a
    vague "it felt jumbled";
  * coverage and length ratios.

Usage:
    uv run python examples/closed_loop_eval.py data/eval/<stamp>-input.wav \\
                                               data/eval/<stamp>-output.wav
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import sys
from pathlib import Path

from openai import AsyncOpenAI

TRANSCRIBE_MODEL = "gpt-4o-transcribe"
# A referenciának ERŐSEBBNEK kell lennie a mértnél, különben a mérce maga a
# hibaforrás. A projektnek nincs `gpt-5` hozzáférése; a `gpt-5-mini` viszont
# nem realtime, az egész szöveget egyben látja, és nincs latency-korlátja —
# ezek a valódi előnyök a `gpt-realtime-mini`-vel szemben, nem a modellméret.
TRANSLATE_MODEL = "gpt-5-mini"
EMBED_MODEL = "text-embedding-3-small"

# Under this cosine similarity a reference sentence has no counterpart worth
# calling a translation. Calibrate against real data before trusting it as a
# pass/fail line — it is a reading aid, not a verdict.
MATCH_THRESHOLD = 0.60

REFERENCE_PROMPT = """Fordítsd le a következő szöveget magyarra.

Ez egy hírbemondó folyamatos beszédének átirata. A fordítás legyen pontos és
teljes: minden tényt, nevet, számot és időpontot adj vissza. Ne rövidíts, ne
foglalj össze, ne kommentálj. Csak a magyar fordítást add vissza."""

SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")

FACT_EXTRACT_PROMPT = """Bontsd atomi tényállításokra az alábbi magyar szöveget.

Egy tény = egy önállóan igaz vagy hamis állítás. Minden számot, nevet,
helyszínt, időpontot és eseményt külön tényként vegyél fel. Ne értelmezz, ne
egészíts ki, ne vonj össze.

Csak JSON tömböt adj vissza, sztringekkel, más semmit.
Példa: ["Az áldozatok száma 15.", "A baleset aranybányában történt."]"""

FACT_CHECK_PROMPT = """Egy fordítógép kimenetét ellenőrzöl.

Megkapsz egy TÉNYT a helyes fordításból, és a gép TELJES kimenetét. Döntsd el,
hogy a tény megjelenik-e a kimenetben.

Szigorú szabályok:
- A számoknak, neveknek, helyszíneknek PONTOSAN egyezniük kell. Ha egy szám
  más szerepben jelenik meg (pl. áldozatszámból dátum lett), az NEM egyezés.
- A megfogalmazás eltérhet; csak a tartalom számít.
- Ha a tény részben van meg (pl. az esemény igen, de a helyszín hibás),
  az "partial".

Csak JSON objektumot adj vissza:
{"verdict": "yes" | "partial" | "no", "evidence": "a kimenet releváns része vagy null", "note": "egy rövid mondat, ha nem yes"}"""


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


async def _transcribe(client: AsyncOpenAI, path: Path, language: str | None) -> str:
    with path.open("rb") as fh:
        kwargs = {"model": TRANSCRIBE_MODEL, "file": fh}
        if language:
            kwargs["language"] = language
        result = await client.audio.transcriptions.create(**kwargs)
    return result.text.strip()


async def _translate(client: AsyncOpenAI, text: str) -> str:
    resp = await client.responses.create(
        model=TRANSLATE_MODEL,
        input=[
            {"role": "system", "content": REFERENCE_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    return resp.output_text.strip()


async def _extract_facts(client: AsyncOpenAI, text: str) -> list[str]:
    """Atomi tényekre bontja a referenciát.

    A mondatszintű hasonlóság **fogalmazást** mér, nem információt: a mért
    felvételen a „15 halálos áldozat" -> „augusztus 15-én" ferdítés 0.66-ot
    kapott, vagyis átment — pedig egy hírfordítónál ez a legsúlyosabb hiba.
    Tényenként vizsgálva ez bukás, aminek lennie is kell.
    """
    resp = await client.responses.create(
        model=TRANSLATE_MODEL,
        input=[
            {"role": "system", "content": FACT_EXTRACT_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    raw = resp.output_text.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    return [str(f) for f in json.loads(raw)]


async def _check_fact(client: AsyncOpenAI, fact: str, produced: str) -> dict:
    resp = await client.responses.create(
        model=TRANSLATE_MODEL,
        input=[
            {"role": "system", "content": FACT_CHECK_PROMPT},
            {"role": "user", "content": f"TÉNY:\n{fact}\n\nKIMENET:\n{produced}"},
        ],
    )
    raw = resp.output_text.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        out = {"verdict": "no", "evidence": None, "note": f"elemzési hiba: {raw[:80]}"}
    out["fact"] = fact
    return out


async def _embed(client: AsyncOpenAI, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    resp = await client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def _wav_seconds(path: Path) -> float:
    import wave

    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_wav", type=Path, help="amit az app HALLOTT")
    ap.add_argument("output_wav", type=Path, help="amit az app MONDOTT")
    ap.add_argument(
        "--source-language",
        default=None,
        help="a forrás nyelve ISO-639-1 kóddal (pl. bg); alapból automatikus",
    )
    ap.add_argument("--json", type=Path, help="a nyers eredmény ide is kiírva")
    args = ap.parse_args()

    for p in (args.input_wav, args.output_wav):
        if not p.is_file():
            sys.exit(f"nincs meg: {p}")

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    print(f"forras : {args.input_wav.name}  ({_wav_seconds(args.input_wav):.1f}s)")
    print(f"kimenet: {args.output_wav.name}  ({_wav_seconds(args.output_wav):.1f}s)\n")

    print("1/4  a forras atirata...")
    source_text = await _transcribe(client, args.input_wav, args.source_language)

    print("2/4  fuggetlen referenciaforditas...")
    reference = await _translate(client, source_text)

    print("3/4  az app kimenetenek atirata...")
    produced = await _transcribe(client, args.output_wav, "hu")

    print("4/5  tenyek kibontasa a referenciabol...")
    facts = await _extract_facts(client, reference)
    print(f"     {len(facts)} teny")

    print("5/5  tenyenkenti ellenorzes...\n")
    checks = await asyncio.gather(
        *(_check_fact(client, f, produced) for f in facts)
    )
    ref_sentences = _sentences(reference)
    got_sentences = _sentences(produced)
    ref_vecs = await _embed(client, ref_sentences)

    # Szomszédos mondatpárok is jelöltek. A rendszer gyakran ÖSSZEVONJA két
    # forrásmondat tartalmát egyetlen kimeneti mondatba (a 4 s-os vágás miatt
    # amúgy sem esnek egybe a mondathatárok) — csak egyedi mondatokhoz mérve
    # az ilyen esetek hamis hiányként jelennének meg, és a metrika rosszabbnak
    # mutatná a rendszert, mint amilyen.
    candidates = list(got_sentences) + [
        f"{a} {b}" for a, b in zip(got_sentences, got_sentences[1:])
    ]
    cand_vecs = await _embed(client, candidates)

    matches = []
    for sent, vec in zip(ref_sentences, ref_vecs):
        best, best_i = 0.0, -1
        for i, cvec in enumerate(cand_vecs):
            score = _cosine(vec, cvec)
            if score > best:
                best, best_i = score, i
        matches.append(
            {
                "reference": sent,
                "best_score": round(best, 3),
                "matched": candidates[best_i] if best_i >= 0 else None,
            }
        )

    print("=" * 76)
    print("FORRAS (amit a modell hallott)")
    print("=" * 76)
    print(source_text + "\n")
    print("=" * 76)
    print("REFERENCIA (fuggetlen forditas — ez a merce)")
    print("=" * 76)
    print(reference + "\n")
    print("=" * 76)
    print("AZ APP KIMENETE")
    print("=" * 76)
    print(produced + "\n")

    print("=" * 76)
    print("TENYENKENT — ez a lenyeg: atjott-e az INFORMACIO")
    print("=" * 76)
    mark = {"yes": "  ok ", "partial": "RESZB", "no": "HIANY"}
    for c in checks:
        print(f"{mark.get(c['verdict'], '  ?  ')}  {c['fact']}")
        if c["verdict"] != "yes" and c.get("note"):
            print(f"         {c['note']}")
    yes = sum(1 for c in checks if c["verdict"] == "yes")
    part = sum(1 for c in checks if c["verdict"] == "partial")
    no = sum(1 for c in checks if c["verdict"] == "no")
    print()
    print(f"TENY-FEDETTSEG  {yes}/{len(checks)} pontos"
          f"  ·  {part} reszleges  ·  {no} hianyzik"
          f"  ->  {100 * yes // max(len(checks), 1)}%")
    print()

    print("=" * 76)
    print("MONDATONKENT (fogalmazas-kozelseg — NEM informaciomeres)")
    print("=" * 76)
    missing = 0
    for i, m in enumerate(matches, 1):
        ok = m["best_score"] >= MATCH_THRESHOLD
        if not ok:
            missing += 1
        print(f"{'  ok' if ok else 'HIANY'} [{m['best_score']:.2f}] {m['reference']}")
        if ok:
            print(f"        -> {m['matched']}")
    print()

    print("=" * 76)
    scores = [m["best_score"] for m in matches]
    covered = len(matches) - missing
    print(f"Referencia mondatok      {len(matches)}")
    print(f"Fedve (>= {MATCH_THRESHOLD})         {covered}  ({100 * covered // max(len(matches), 1)}%)")
    print(f"Hianyzik                 {missing}")
    if scores:
        print(f"Hasonlosag  atlag {sum(scores) / len(scores):.2f}  min {min(scores):.2f}")
    print(f"Hossz       referencia {len(reference)} kar  |  app {len(produced)} kar")
    print(f"Hang        forras {_wav_seconds(args.input_wav):.1f}s  |  kimenet {_wav_seconds(args.output_wav):.1f}s")

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "source_text": source_text,
                    "reference": reference,
                    "produced": produced,
                    "matches": matches,
                    "missing": missing,
                    "facts": checks,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nnyers eredmeny: {args.json}")


asyncio.run(main())
