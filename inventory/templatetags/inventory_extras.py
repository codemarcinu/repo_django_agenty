from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplies the value by the arg."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def subtract(value, arg):
    """Subtracts the arg from the value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def getitem(dictionary, key):
    """Gets an item from a dictionary."""
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None
