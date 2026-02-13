import json
import os
from jinja2 import Environment, FileSystemLoader, Template
from datetime import datetime

def load_email_templates():
    """Load email templates from email.json"""
    template_path = os.path.join(os.path.dirname(__file__), '..', 'email.json')
    with open(template_path, 'r') as f:
        return json.load(f)

def get_trip_email_content(status: str, context: dict):
    """
    Get email header and body for trip status
    
    Args:
        status: Trip status (pending, approved, etc.)
        context: Dict with variables to replace in template
    
    Returns:
        tuple: (header, body)
    """
    templates = load_email_templates()
    trip_templates = templates.get('trip', {})
    status_template = trip_templates.get(status.lower(), {})
    
    if not status_template:
        # Default template
        header = f"Trip Update: {context.get('trip_code', 'N/A')}"
        body = f"Your trip {context.get('trip_code', 'N/A')} has been updated."
        return header, body
    
    # Get template strings
    header_template = status_template.get('header', '')
    body_template = status_template.get('body', '')
    
    # Add company info to context
    context.update({
        'company_name': 'Eisaku',
        'support_email': 'support@eisaku.com',
        'current_year': datetime.now().year
    })
    
    # Render templates
    header = Template(header_template).render(context)
    body = Template(body_template).render(context)
    
    return header, body
