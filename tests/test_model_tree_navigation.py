#!/usr/bin/env python3
"""Static integration contract for the Danish Model Explorer tree."""
from __future__ import annotations
import json
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app/model-tree-data.js"
DOC = ROOT / "app/models.html"
UI = ROOT / "app/model-tree-ui.js"

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=set()
        self.scripts=[]
        self.buttons=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if "id" in a:self.ids.add(a["id"])
        if tag=="script":self.scripts.append(a.get("src"))
        if tag=="button":self.buttons.append(a)

class ModelTreeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw=JS.read_text(encoding="utf-8")
        assert "window.FPL_MODEL_TREE = " in raw
        cls.data=json.loads(raw.split("window.FPL_MODEL_TREE = ",1)[1].rstrip().removesuffix(";"))
        cls.nodes={x["id"]:x for x in cls.data["nodes"]}
    def test_one_root_no_orphans(self):
        nodes=self.data["nodes"]
        self.assertEqual(len(nodes),len(self.nodes))
        self.assertEqual([n["id"] for n in nodes if n["parent"] is None],["root"])
        self.assertEqual({n["id"] for n in nodes if n["parent"]=="root"},{"mm","pm","ts","chips","data"})
        for n in nodes:
            if n["parent"] is not None:
                self.assertIn(n["parent"],self.nodes)
            seen=set()
            x=n
            while x["parent"] is not None:
                self.assertNotIn(x["id"],seen)
                seen.add(x["id"])
                x=self.nodes[x["parent"]]
            self.assertEqual(x["id"],"root")
    def test_every_node_has_idea_and_formulas(self):
        self.assertGreaterEqual(len(self.nodes),40)
        for n in self.nodes.values():
            self.assertTrue(n["title"].strip(),n["id"])
            self.assertTrue(n["summary"].strip(),n["id"])
            self.assertTrue(n["idea"].strip(),n["id"])
            self.assertTrue(n["formulas"],n["id"])
            for f in n["formulas"]:
                self.assertTrue(f["expression"].strip(),n["id"])
                self.assertTrue(f["meaning"].strip(),n["id"])
            self.assertTrue(n["sources"],n["id"])
    def test_every_source_file_is_real(self):
        missing=[]
        for n in self.nodes.values():
            for path in n["sources"]:
                if not (ROOT/path).is_file():
                    missing.append((n["id"],path))
        self.assertEqual(missing,[])
    def test_math_matches_frozen_contract(self):
        config=json.loads((ROOT/"config/fpl_locked_model.json").read_text(encoding="utf-8"))
        self.assertEqual(config["transfer_strategy"]["weights"],[1.,.6,.36,.216,.1296,.07776])
        self.assertEqual(config["chips"]["free_hit"]["lambda"],10.)
        self.assertEqual(config["chips"]["wildcard"]["lambda"],20.)
        self.assertEqual(config["chips"]["bench_boost"]["lambda"],20.)
        self.assertIn("20",str(self.nodes["chips-bb"]["formulas"]))
        self.assertIn("0,60",str(self.nodes["ts"]["formulas"]))
        self.assertIn("8,57",str(self.nodes["chips-tc-future"]["formulas"]))
    def test_document_navigation_and_js_present(self):
        parser=Parser();parser.feed(DOC.read_text(encoding="utf-8"))
        for id in ["model-detail","model-nav-tree","model-roadmap","model-tree-search","model-search-results","expand-model-tree","collapse-model-tree"]:
            self.assertIn(id,parser.ids)
        self.assertIn("model-tree-data.js",parser.scripts)
        self.assertIn("model-tree-ui.js",parser.scripts)
        source=UI.read_text(encoding="utf-8")
        for hook in ["hashchange","data-open-node","data-toggle-node","data-copy-formula","renderSearch","renderDetail"]:
            self.assertIn(hook,source)

if __name__=="__main__":
    unittest.main()
