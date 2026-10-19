from django import forms
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class InvalidSampleForm(forms.Form):
    summary = forms.CharField(label="요약")
    consent = forms.BooleanField(label="동의합니다")


class FormAccessibilityTests(SimpleTestCase):
    def test_field_errors_are_programmatically_associated(self):
        form = InvalidSampleForm(data={"summary": "", "consent": "on"})
        self.assertFalse(form.is_valid())

        html = render_to_string("community/fields.html", {"form": form})

        self.assertIn('id="id_summary"', html)
        self.assertIn('aria-invalid="true"', html)
        self.assertIn('aria-describedby="id_summary_error"', html)
        self.assertIn('id="id_summary_error"', html)
        self.assertIn('id="id_consent"', html)
        self.assertNotRegex(html, r'<input\b(?=[^>]*\bid="id_consent")(?=[^>]*\baria-invalid="true")[^>]*>')

    def test_valid_fields_do_not_receive_error_state(self):
        form = InvalidSampleForm(data={"summary": "확인", "consent": "on"})
        self.assertTrue(form.is_valid())

        html = render_to_string("community/fields.html", {"form": form})

        self.assertNotIn('aria-invalid="true"', html)
        self.assertNotIn('aria-describedby="id_summary_error"', html)
