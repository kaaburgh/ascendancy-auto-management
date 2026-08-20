from __future__ import annotations
import importlib.util
import pathlib
import sys
import tempfile
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "probe_a2_decoded_memory_references.py"
spec = importlib.util.spec_from_file_location("probe_a2_decoded_memory_references", SCRIPT)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)

class DecodedMemoryReferenceProbeTests(unittest.TestCase):
    def test_parser_keeps_only_absolute_memory_literals(self):
        text = """
  10000: a1 10 6c 00 00        mov    eax,ds:0x6c10
  10005: 8b 15 20 6c 00 00     mov    edx,DWORD PTR ds:0x6c20
  1000b: b8 10 6c 00 00        mov    eax,0x6c10
  10010: 8b 43 10              mov    eax,DWORD PTR [ebx+0x10]
"""
        rows = probe.parse_objdump_memory_operands(text)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["absolute_memory_literals"], [0x6C10])
        self.assertEqual(rows[1]["absolute_memory_literals"], [0x6C20])

    def test_classifies_linear_and_object_relative_hits(self):
        rows = [{"instruction_address":0x11000,"mnemonic":"mov","absolute_memory_literals":[0x96C20,0x6C30]}]
        candidates = [{"id":"c","object":2,"address":0x96C10,"size":0x40}]
        hits = probe.classify_references(rows,candidates,{2:0x90000})
        self.assertEqual(len(hits),2)
        self.assertEqual({(h["interpretation"],h["target_address"]) for h in hits},{("linear-va",0x96C20),("target-object-relative",0x96C30)})

    def test_boundaries_do_not_match(self):
        rows = [{"instruction_address":0x11000,"mnemonic":"mov","absolute_memory_literals":[0x96C0F,0x96C50,0x6C0F,0x6C50]}]
        candidates = [{"id":"c","object":2,"address":0x96C10,"size":0x40}]
        self.assertEqual(probe.classify_references(rows,candidates,{2:0x90000}),[])

    def test_output_cannot_alias_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=pathlib.Path(tmp)/"target.exe"; target.write_bytes(b"x")
            with self.assertRaises(probe.DecodedReferenceProbeError):
                probe.validate_output_path(target,target)

    def test_objdump_identity_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake=pathlib.Path(tmp)/"objdump"
            fake.write_text("#!/bin/sh\necho 'GNU objdump (GNU Binutils) 2.42'\n",encoding="utf-8")
            fake.chmod(0o755)
            resolved,identity=probe.resolve_objdump_identity(objdump=str(fake))
            self.assertEqual(pathlib.Path(resolved),fake)
            self.assertEqual(identity,"GNU objdump (GNU Binutils) 2.42")

if __name__ == "__main__": unittest.main()
