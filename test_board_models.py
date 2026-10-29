import unittest
from board_models import identify_hal_pin, rename_selected_remote


class ModelsTest(unittest.TestCase):
    def test_models_and_actual_spelling(self):
        mpg = identify_hal_pin("hm2_7i92.0.sd01.0.0.encoder.count")
        self.assertTrue(mpg["encoder"])
        self.assertEqual(mpg["hal_prefix"], "hm2_7i92.0.sd01.0.0")
        self.assertFalse(identify_hal_pin("hm2_7i92.0.SD02.0.1.input-00")["encoder"])

    def test_old_name_is_ambiguous(self):
        self.assertIsNone(identify_hal_pin("hm2_7i92.0.7i69.0.0.input-00"))

    def test_only_selected_remote_migrates(self):
        text = "net a hm2_7i92.0.7i69.0.0.input-00\nnet b hm2_7i92.0.7i69.0.1.input-00\n"
        result = rename_selected_remote(text, "hm2_7i92.0.7i69.0.0", "hm2_7i92.0.sd01.0.0")
        self.assertIn("sd01.0.0.input-00", result)
        self.assertIn("7i69.0.1.input-00", result)


if __name__ == "__main__":
    unittest.main()
