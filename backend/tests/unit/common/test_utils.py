"""Unit tests for common utility functions."""

from src.common.utils import rich_html_to_plain_text


class TestRichHtmlToPlainText:
    """Test cases for rich_html_to_plain_text function."""

    def test_non_string_input(self):
        """Test that non-string inputs are returned unchanged."""
        assert rich_html_to_plain_text(123) == 123
        assert rich_html_to_plain_text(45.67) == 45.67
        assert rich_html_to_plain_text(True) is True
        assert rich_html_to_plain_text(None) is None

    def test_empty_string(self):
        """Test that empty strings are returned unchanged."""
        assert rich_html_to_plain_text('') == ''

    def test_plain_text_without_html(self):
        """Test that plain text without HTML tags is returned unchanged."""
        plain_text = 'This is just plain text without any HTML tags.'
        assert rich_html_to_plain_text(plain_text) == plain_text

    def test_text_with_angle_brackets_but_no_html(self):
        """Test text with < but no actual HTML tags."""
        text = 'The value is < 100 and > 50'
        assert rich_html_to_plain_text(text) == text

    def test_unordered_list(self):
        """Test conversion of unordered lists to bullet points."""
        html = """<ul>
<li>First item</li>
<li>Second item</li>
<li>Third item</li>
</ul>"""
        expected = """• First item
• Second item
• Third item"""
        assert rich_html_to_plain_text(html).strip() == expected

    def test_ordered_list(self):
        """Test conversion of ordered lists to numbered lists."""
        html = """<ol>
<li>First step</li>
<li>Second step</li>
<li>Third step</li>
</ol>"""
        expected = """1. First step
2. Second step
3. Third step"""
        assert rich_html_to_plain_text(html).strip() == expected

    def test_paragraphs_with_line_breaks(self):
        """Test that paragraphs are separated by line breaks."""
        html = """<p>First paragraph</p>
<p>Second paragraph</p>
<p>Third paragraph</p>"""
        expected = """First paragraph

Second paragraph

Third paragraph"""
        assert rich_html_to_plain_text(html).strip() == expected

    def test_br_tags_converted_to_line_breaks(self):
        """Test that <br> tags are converted to line breaks."""
        html = 'Line one<br>Line two<br>Line three'
        expected = """Line one
Line two
Line three"""
        assert rich_html_to_plain_text(html).strip() == expected

    def test_html_entities_decoded(self):
        """Test that HTML entities are properly decoded."""
        html = '<p>Revenue &amp; EBITDA are &lt; $100M &gt; expected</p>'
        expected = 'Revenue & EBITDA are < $100M > expected'
        assert rich_html_to_plain_text(html).strip() == expected

    def test_nested_formatting_removed(self):
        """Test that nested formatting tags are removed but text is preserved."""
        html = '<p>Revenue was <b>$10M</b> in <i>Q1 2024</i>.</p>'
        expected = 'Revenue was $10M in Q1 2024.'
        assert rich_html_to_plain_text(html).strip() == expected

    def test_complex_example_from_requirements(self):
        """Test the complex example from the requirements."""
        html = """<ul>
<li><p>Account is performing. The Deal Team recommends affirming the 5 risk rating for the following reasons:</p></li>
<li><p>1. Financial performance has been strong, highlighted by revenue &amp; EBITDA growth since close</p></li>
<li><p>2. Reasonable Net Senior Leverage of ~3.0x.</p></li>
<li><p>3. Strong coverage ratios, with interest coverage and FCCR of 2.7x and 2.2x, respectively</p></li>
</ul>
<p></p>"""
        result = rich_html_to_plain_text(html).strip()

        # Check that bullet points are present
        assert '• Account is performing.' in result
        assert '• 1. Financial performance' in result
        assert '• 2. Reasonable Net Senior Leverage' in result
        assert '• 3. Strong coverage ratios' in result

        # Check that HTML entities are decoded
        assert '&' in result  # &amp; should become &

        # Check structure is preserved
        lines = result.split('\n')
        assert len([line for line in lines if line.strip().startswith('•')]) == 4

    def test_headers_with_line_breaks(self):
        """Test that headers are followed by line breaks."""
        html = """<h1>Main Title</h1>
<p>Content under title</p>
<h2>Subtitle</h2>
<p>More content</p>"""
        result = rich_html_to_plain_text(html).strip()

        # Check that headers and paragraphs are on separate lines
        lines = result.split('\n')
        assert 'Main Title' in lines[0]
        assert 'Content under title' in lines[2]  # Should be after empty line
        assert 'Subtitle' in lines[4]  # After content and empty line
        assert 'More content' in lines[6]  # After subtitle and empty line

    def test_excessive_whitespace_cleaned(self):
        """Test that excessive whitespace is cleaned up."""
        html = """<p>Text   with    extra     spaces</p>
<p>


Multiple empty lines


</p>
<p>Final text</p>"""
        result = rich_html_to_plain_text(html)

        # Check that multiple spaces are collapsed
        assert 'Text with extra spaces' in result

        # Check that excessive line breaks are reduced
        assert '\n\n\n' not in result

    def test_mixed_lists_and_paragraphs(self):
        """Test mixed content with lists and paragraphs."""
        html = """<p>Introduction paragraph</p>
<ul>
<li>Bullet point 1</li>
<li>Bullet point 2</li>
</ul>
<p>Middle paragraph</p>
<ol>
<li>Numbered item 1</li>
<li>Numbered item 2</li>
</ol>
<p>Conclusion</p>"""
        result = rich_html_to_plain_text(html).strip()

        # Verify structure
        assert 'Introduction paragraph' in result
        assert '• Bullet point 1' in result
        assert '• Bullet point 2' in result
        assert 'Middle paragraph' in result
        assert '1. Numbered item 1' in result
        assert '2. Numbered item 2' in result
        assert 'Conclusion' in result

    def test_hr_tags_converted_to_line_breaks(self):
        """Test that <hr> tags are converted to line breaks."""
        html = 'Section 1<hr>Section 2<hr>Section 3'
        result = rich_html_to_plain_text(html).strip()
        lines = result.split('\n')
        assert 'Section 1' in lines[0]
        assert 'Section 2' in lines[1]
        assert 'Section 3' in lines[2]

    def test_nested_lists_flattened(self):
        """Test that nested lists are flattened (BeautifulSoup behavior)."""
        html = """<ul>
<li>Main item
  <ul>
    <li>Sub item 1</li>
    <li>Sub item 2</li>
  </ul>
</li>
</ul>"""
        result = rich_html_to_plain_text(html).strip()
        # When we set li.string, it replaces all content including nested elements
        # So nested lists get concatenated to the parent li
        assert '• Main item' in result
        # The nested items will be concatenated but without bullet points
        assert 'Sub item 1' in result
        assert 'Sub item 2' in result
