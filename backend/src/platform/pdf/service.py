import io
import logging
import uuid

from weasyprint import CSS, HTML

from src.platform.files.service import FileService
from src.platform.pdf.utils import render_template
from src.settings import PDF_CSS_DIR

# These are way too noisy
logging.getLogger('fontTools').setLevel(logging.WARNING)
logging.getLogger('weasyprint').setLevel(logging.WARNING)


class PDFService:
    def __init__(self, css_dir: str, file_service: FileService):
        """
        :param css_dir: Directory containing CSS files (optional)
        """
        self.css_dir = css_dir
        self.file_service = file_service

    @classmethod
    def factory(cls) -> 'PDFService':
        return cls(css_dir=PDF_CSS_DIR, file_service=FileService.factory())

    def _convert_to_pdf(self, html_string: str, stylesheets: list[CSS], file_path: str | None = None) -> bytes:
        """
        Pass in file_path to generate pdf locally
        """
        if file_path:
            return HTML(string=html_string).write_pdf(file_path, stylesheets=stylesheets, presentational_hints=True)
        return HTML(string=html_string).write_pdf(stylesheets=stylesheets, presentational_hints=True)

    def _generate_pdf(
        self, template_name: str, context: dict, css_name: str | None = None, file_path: str | None = None
    ) -> io.BytesIO:
        """
        :param template_name: Name of the HTML template
        :param css_name: Name of the CSS file (optional)
        :return: PDF data as bytesIO
        """
        rendered_html = render_template(
            template_name=template_name,
            context=context,
        )

        stylesheets = []
        if css_name and self.css_dir:
            with open(f'{self.css_dir}/{css_name}', 'r', encoding='utf-8') as file:
                css_string = file.read()
                stylesheets.append(CSS(string=css_string))

        pdf = self._convert_to_pdf(html_string=rendered_html, stylesheets=stylesheets, file_path=file_path)
        return io.BytesIO(pdf)

    def generate_pdf(
        self,
        template_name: str,
        file_name: str,
        context: dict,
        css_name: str | None = None,
    ) -> uuid.UUID:
        pdf = self._generate_pdf(template_name=template_name, css_name=css_name, context=context)

        uploaded_file = self.file_service.upload(
            content=pdf,
            file_name=f'{file_name}.pdf',
            is_public=False,
            uploaded_by_id=context.get('uploaded_by_id', None),
        )
        return uploaded_file.id
