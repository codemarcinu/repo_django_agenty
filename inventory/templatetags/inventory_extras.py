"""
Template tags and filters for inventory app.
Part of Prompt 10: Panel przeglądu (dashboard) - rozszerzenie.
"""

from django import template

register = template.Library()


@register.filter
def getitem(dictionary, key):
    """Get item from dictionary by key."""
    if dictionary and key:
        return dictionary.get(key)
    return None


@register.filter
def multiply(value, arg):
    """Multiply value by argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def percentage(value, total):
    """Calculate percentage of value from total."""
    try:
        if float(total) > 0:
            return (float(value) / float(total)) * 100
        return 0
    except (ValueError, TypeError):
        return 0


@register.filter
def heatmap_intensity(value):
    """Return CSS class for heatmap cell intensity."""
    try:
        val = float(value or 0)
        if val == 0:
            return 'intensity-0'
        elif val <= 2:
            return 'intensity-low'
        elif val <= 5:
            return 'intensity-medium'
        else:
            return 'intensity-high'
    except (ValueError, TypeError):
        return 'intensity-0'