from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.filter
def jsonify(value):
    """Convert a Python object to JSON string."""
    return mark_safe(json.dumps(value))

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary."""
    return dictionary.get(key)

@register.filter
def add_class(field, css_class):
    """Add a CSS class to a form field."""
    return field.as_widget(attrs={"class": css_class})

@register.simple_tag
def quality_color(score):
    """Return a color based on quality score."""
    if score is None:
        return '#808080'  # Gray for unknown
    
    if score >= 80:
        return '#4CAF50'  # Green for excellent
    elif score >= 60:
        return '#8BC34A'  # Light green for good
    elif score >= 40:
        return '#FFC107'  # Amber for average
    elif score >= 20:
        return '#FF9800'  # Orange for fair
    else:
        return '#F44336'  # Red for poor

@register.simple_tag
def quality_label(score):
    """Return a label based on quality score."""
    if score is None:
        return 'Unknown'
    
    if score >= 80:
        return 'Excellent'
    elif score >= 60:
        return 'Good'
    elif score >= 40:
        return 'Average'
    elif score >= 20:
        return 'Fair'
    else:
        return 'Poor'
