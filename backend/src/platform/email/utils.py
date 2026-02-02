import datetime

from jinja2 import Environment, PackageLoader, select_autoescape

from src import settings


def render_template(template_name: str, context: dict):
    env = Environment(
        loader=PackageLoader('src.platform.email', 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )
    template = env.get_template(template_name)

    # Add company information to all email templates
    return template.render(
        **context,
        copyright_year=datetime.date.today().year,
        company_name=settings.COMPANY_FULL_NAME,
        support_email=settings.SUPPORT_EMAIL,
        company_website=settings.COMPANY_WEBSITE,
        logo_url=settings.COMPANY_LOGO_URL,
    )
