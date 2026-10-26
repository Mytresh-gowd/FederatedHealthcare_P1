from django import template
register=template.Library()
@register.filter
def get_item(obj,key):
    try: return obj.get(key,'')
    except Exception: return ''
@register.filter
def percent(value):
    try: return round(float(value)*100,1)
    except (TypeError,ValueError): return 0
