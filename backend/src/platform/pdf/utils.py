from jinja2 import Environment, PackageLoader, select_autoescape


def render_template(template_name: str, context: dict):
    env = Environment(
        loader=PackageLoader('src.platform.pdf', 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )
    template = env.get_template(template_name)

    return template.render(**context)
