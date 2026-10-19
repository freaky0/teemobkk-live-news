from django import template

register = template.Library()


@register.filter
def accessible_field(bound_field):
    """Connect rendered validation errors to their form controls."""
    attrs = {}
    if bound_field.errors:
        attrs["aria-invalid"] = "true"
        error_id = f"{bound_field.auto_id}_error"
        described_by = bound_field.field.widget.attrs.get("aria-describedby", "").split()
        if error_id not in described_by:
            described_by.append(error_id)
        attrs["aria-describedby"] = " ".join(described_by)
    return bound_field.as_widget(attrs=attrs)
