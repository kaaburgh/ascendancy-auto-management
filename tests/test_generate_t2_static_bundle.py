import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("t2", ROOT / "scripts/generate_t2_static_bundle.py")
t2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t2)

SAMPLE = r'''
                      Linear EXE Header (OS/2 V2.x) - LE
==============================================================================
file offset = 00002A50H
linear EXE format level                           = 00000000H
cpu type                                          =     0002H
os type (1==OS/2, 2==Windows, 3==DOS4, 4==Win386) =     0001H
module version                                    = 00000000H
module flags                                      = 00000200H
# module pages                                    = 00000002H
object # for initial EIP                          = 00000001H
initial EIP                                       = 00000010H
object # for initial ESP                          = 00000002H
initial ESP                                       = 00000020H
page size                                         = 00001000H
last page size (LE)/page shift (LX)               = 00000020H
fixup section size                                = 00000033H
loader section size                               = 00000044H
object iterated data map offset                   = 00000000H
offset of import module name table                = 00000055H
offset of import procedure name table             = 00000055H
offset of enumerated data pages                   = 00002000H
offset of non-resident names table (rel file)     = 00000000H
size of non-resident names table                  = 00000000H
object # for automatic data object                = 00000002H
offset of the debugging information               = 00000000H
size of the debugging information                 = 00000000H
                                 Object Table
==============================================================================
object  1: virtual memory size             = 00001000H
          relocation base address          = 00010000H
          object flag bits                 = 00002045H
          object page table index          = 00000001H
          # of object page table entries   = 00000001H
    page #   1  map page = 000001H file ofs = 00002000H flgs = 00H Valid
object  2: virtual memory size             = 00000020H
          relocation base address          = 00020000H
          object flag bits                 = 00002043H
          object page table index          = 00000002H
          # of object page table entries   = 00000001H
    page #   2  map page = 000002H file ofs = 00003000H flgs = 00H Valid
'''
INFO = {
    "container": {"mz_lfanew":0x2a50,"format_level":0,"cpu":2,"os_type":1,"module_version":0,"module_flags":0x200},
    "pages": {"count":2,"size":0x1000,"last_page_size":0x20,"data_offset":0x2000,"numbers_are_sequential":True},
    "entry": {"object":1,"eip":0x10,"stack_object":2,"esp":0x20},
    "loader": {"fixup_size":0x33,"loader_size":0x44,"iterated_map_offset":0,"import_module_offset":0x55,"import_procedure_offset":0x55,"nonresident_offset":0,"nonresident_size":0,"autodata_object":2,"debug_offset":0,"debug_size":0},
    "objects": [
        {"index":1,"virtual_size":0x1000,"base_address":0x10000,"flags":0x2045,"first_page":1,"page_count":1},
        {"index":2,"virtual_size":0x20,"base_address":0x20000,"flags":0x2043,"first_page":2,"page_count":1},
    ],
}

class TestT2(unittest.TestCase):
    def test_parse_and_compare_wdump(self):
        parsed = t2.parse_wdump(SAMPLE)
        result = t2.compare_wdump(INFO, parsed)
        self.assertEqual("pass", result["result"])
        self.assertEqual(2, result["page_entries_compared"])
        self.assertEqual([], result["disagreements"])

    def test_page_offset_mismatch_fails(self):
        parsed = t2.parse_wdump(SAMPLE.replace("00003000H flgs", "00003100H flgs"))
        result = t2.compare_wdump(INFO, parsed)
        self.assertEqual("fail", result["result"])
        self.assertTrue(any(x["kind"] == "page_file_offset" for x in result["disagreements"]))

    def test_string_summary_does_not_bulk_copy_text(self):
        payload = {"sha256":"abc","strings":[
            {"object":1,"address":1,"length":5,"text":"HELLO"},
            {"object":2,"address":2,"length":13,"text":"RATIONAL DOS/4G"},
        ]}
        summary = t2.string_summary(payload)
        self.assertEqual(2, summary["string_count"])
        self.assertNotIn("strings", summary)
        self.assertNotIn("text", summary["runtime_toolchain_indicators"][0])
        self.assertIn("RATIONAL", summary["runtime_toolchain_indicators"][0]["matched_tokens"])

    def test_verify_targets_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(t2.BundleError):
                t2.verify_targets(pathlib.Path(td))

if __name__ == '__main__': unittest.main()
