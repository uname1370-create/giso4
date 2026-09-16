#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression checks for the hair-sale estimate continuation page."""
from pathlib import Path
import unittest


GISO_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = GISO_DIR / "templates" / "hair_sale.html"
BACKEND_PATH = GISO_DIR / "hair_sale.py"


class HairSaleResultVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = TEMPLATE_PATH.read_text(encoding="utf-8")
        cls.backend = BACKEND_PATH.read_text(encoding="utf-8")

    def test_estimate_is_visible_in_server_rendered_result(self):
        """A successful POST must not depend on JavaScript to reveal the estimate."""
        result_start = self.template.index('id="priceResultSection"')
        opening_tag_start = self.template.rfind("<section", 0, result_start)
        opening_tag_end = self.template.index(">", result_start)
        opening_tag = self.template[opening_tag_start:opening_tag_end]

        self.assertIn("giso-step-visible", opening_tag)
        self.assertNotIn("giso-step-hidden", opening_tag)

    def test_evaluation_form_posts_step_one_to_result_anchor(self):
        form_start = self.template.index('id="hairEvalForm"')
        form_tag_start = self.template.rfind("<form", 0, form_start)
        form_tag_end = self.template.index(">", form_start)
        form_block_end = self.template.index("</form>", form_tag_end)
        form_tag = self.template[form_tag_start:form_tag_end]
        form_block = self.template[form_tag_end:form_block_end]

        self.assertIn("#priceResultSection", form_tag)
        self.assertIn('name="csrf_token"', form_block)
        self.assertIn('name="step" value="1"', form_block)

    def test_step_one_post_renders_result_state(self):
        step_one_start = self.backend.index('if step == "1":')
        step_two_start = self.backend.index('elif step == "2":', step_one_start)
        step_one_branch = self.backend[step_one_start:step_two_start]

        self.assertIn('render_template("hair_sale.html"', step_one_branch)
        self.assertIn("show_result=True", step_one_branch)
        self.assertIn('temp=session["hair_temp"]', step_one_branch)

    def test_page_script_is_cache_busted(self):
        self.assertIn("hair_sale_steps.js') }}?v=phase4-redesign-3", self.template)


if __name__ == "__main__":
    unittest.main()
