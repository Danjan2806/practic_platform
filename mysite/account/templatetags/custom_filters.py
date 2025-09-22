from django import template
register = template.Library()

@register.filter
def to_range(value, max_val):
    return range(int(value), int(max_val)+1)
