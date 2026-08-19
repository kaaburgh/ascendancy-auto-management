#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, shutil, subprocess, sys, tempfile
from typing import Iterable
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import le_image  # noqa: E402
SCHEMA = "ascendancy.a2-decoded-memory-reference-probe/v1"
CANONICAL_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
CANDIDATES = (
    {"id": "object2-96c10", "object": 2, "address": 0x96C10, "size": 6206},
    {"id": "object2-988dc", "object": 2, "address": 0x988DC, "size": 3052},
)
LINE_RE = re.compile(r"^\s*(?P<address>[0-9a-fA-F]+):\s+(?P<bytes>(?:[0-9a-fA-F]{2}\s+)+)(?P<text>.+?)\s*$")
HEX_RE = re.compile(r"0x([0-9a-fA-F]+)")
SEGMENT_ABSOLUTE_RE = re.compile(r"\b(?:cs|ds|es|fs|gs|ss):0x([0-9a-fA-F]+)\b", re.I)
BRACKET_RE = re.compile(r"\[([^\]]+)\]")
class DecodedReferenceProbeError(Exception): pass

def validate_output_path(target: pathlib.Path, output: pathlib.Path | None) -> None:
    if output is None: return
    if target.expanduser().resolve(strict=True) == output.expanduser().resolve(strict=False):
        raise DecodedReferenceProbeError("output path aliases immutable target input")

def _candidate_models(candidate: dict, target_base: int):
    start, end = candidate["address"], candidate["address"] + candidate["size"]
    rs, re_ = start-target_base, end-target_base
    if rs < 0: raise DecodedReferenceProbeError("candidate starts before target object base")
    return (("linear-va", start, end), ("target-object-relative", rs, re_))

def _absolute_memory_literals(text: str) -> list[int]:
    values=[]
    for bracket in BRACKET_RE.findall(text):
        match = re.fullmatch(r"\s*0x([0-9a-fA-F]+)\s*", bracket)
        if match:
            values.append(int(match.group(1), 16))
    values += [int(x,16) for x in SEGMENT_ABSOLUTE_RE.findall(text)]
    return sorted(set(values))

def parse_objdump_memory_operands(text: str) -> list[dict]:
    rows=[]
    for raw in text.splitlines():
        m=LINE_RE.match(raw)
        if not m: continue
        ins=m.group("text").strip(); parts=ins.split(None,1); mnemonic=parts[0]; operands=parts[1] if len(parts)>1 else ""
        lits=_absolute_memory_literals(operands)
        if lits: rows.append({"instruction_address":int(m.group("address"),16),"mnemonic":mnemonic,"absolute_memory_literals":lits})
    return rows

def run_objdump(code_bytes: bytes, base_address: int, *, objdump: str="objdump") -> str:
    resolved=shutil.which(objdump)
    if resolved is None: raise DecodedReferenceProbeError(f"GNU objdump not found: {objdump}")
    with tempfile.TemporaryDirectory(prefix="a2-decoded-ref-") as tmp:
        path=pathlib.Path(tmp)/"object1.bin"; path.write_bytes(code_bytes)
        cp=subprocess.run([resolved,"-D","-b","binary","-m","i386","-M","intel",f"--adjust-vma=0x{base_address:x}",str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if cp.returncode != 0: raise DecodedReferenceProbeError(f"objdump failed with exit {cp.returncode}: {(cp.stderr or cp.stdout).strip()}")
    if not cp.stdout.strip(): raise DecodedReferenceProbeError("objdump produced no disassembly")
    return cp.stdout

def classify_references(decoded_rows: Iterable[dict], candidates: Iterable[dict], target_bases: dict[int,int]) -> list[dict]:
    models=[]
    for c in candidates:
        if c["object"] not in target_bases: raise DecodedReferenceProbeError("candidate names missing object")
        tb=target_bases[c["object"]]
        for interpretation,start,end in _candidate_models(c,tb): models.append((c,interpretation,start,end,tb))
    hits=[]; seen=set()
    for row in decoded_rows:
        for value in row["absolute_memory_literals"]:
            for c,interpretation,start,end,tb in models:
                if start <= value < end:
                    ta=value if interpretation=="linear-va" else tb+value
                    key=(c["id"],row["instruction_address"],value,interpretation,ta)
                    if key in seen: continue
                    seen.add(key); hits.append({"candidate":c["id"],"interpretation":interpretation,"instruction_address":row["instruction_address"],"mnemonic":row["mnemonic"],"encoded_value":value,"target_address":ta,"target_offset_within_candidate":ta-c["address"]})
    return sorted(hits,key=lambda h:(h["candidate"],h["instruction_address"],h["interpretation"],h["encoded_value"]))

def build_probe(image: le_image.LEImage, *, expected_sha256: str, objdump: str="objdump", candidates: Iterable[dict]=CANDIDATES) -> dict:
    if image.sha256 != expected_sha256: raise DecodedReferenceProbeError(f"target SHA-256 mismatch: expected {expected_sha256}, found {image.sha256}")
    cs=[dict(c) for c in candidates]; objects={o.index:o for o in image.objects}; bases={o.index:o.base_address for o in image.objects}
    for c in cs:
        obj=objects.get(c["object"])
        if obj is None or not (obj.base_address <= c["address"] and c["address"]+c["size"] <= obj.end_address): raise DecodedReferenceProbeError(f"candidate {c['id']!r} is outside declared object")
    code=objects.get(1)
    if code is None: raise DecodedReferenceProbeError("canonical code object 1 is missing")
    rows=parse_objdump_memory_operands(run_objdump(image.object_bytes(1),code.base_address,objdump=objdump))
    if not rows: raise DecodedReferenceProbeError("objdump produced no decoded absolute-memory operands")
    hits=classify_references(rows,cs,bases); by=[]
    for c in cs:
        ch=[h for h in hits if h["candidate"]==c["id"]]; addrs=sorted({h["instruction_address"] for h in ch})
        by.append({**c,"object_offset":c["address"]-bases[c["object"]],"decoded_memory_reference_count":len(ch),"unique_instruction_count":len(addrs),"instruction_addresses":addrs,"decoded_memory_references":ch,"reusable":False,"reuse_evidence":"not established"})
    producer=pathlib.Path(__file__).resolve()
    return {"schema":SCHEMA,"target":{"name":image.name,"sha256":image.sha256,"file_size":image.size},"producer":{"path":"scripts/probe_a2_decoded_memory_references.py","sha256":hashlib.sha256(producer.read_bytes()).hexdigest()},"method":{"source_object":1,"decoder":"GNU objdump -D -b binary -m i386 -M intel","interpretations":["linear-va","target-object-relative"],"evidence_boundary":"decoded absolute-memory operands are investigation leads; linear sweep can decode embedded data and this probe does not exclude computed/indirect access, differently represented relocations, runtime initialization, scratch use, sentinel semantics, or other consumers","relationship_to_prior_probe":"complements the all-byte raw-u32 scan by requiring an objdump-decoded absolute memory operand; it is not independent validation of objdump itself"},"decoded_memory_operand_row_count":len(rows),"decoded_memory_reference_count":len(hits),"candidates":by}

def parse_args(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("target",type=pathlib.Path); p.add_argument("--output",type=pathlib.Path); p.add_argument("--objdump",default="objdump"); return p.parse_args(argv)
def main(argv=None):
    args=parse_args(argv)
    try:
        validate_output_path(args.target,args.output); image=le_image.load(args.target); result=build_probe(image,expected_sha256=CANONICAL_SHA256,objdump=args.objdump)
    except (DecodedReferenceProbeError,le_image.LEError,OSError,ValueError) as exc:
        print(f"error: {exc}",file=sys.stderr); return 2
    text=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(text,encoding="utf-8"); print(f"wrote A2 decoded-memory reference probe to {args.output}")
    else: sys.stdout.write(text)
    return 0
if __name__ == "__main__": raise SystemExit(main())
