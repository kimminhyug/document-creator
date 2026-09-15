"""Safe clickable web addresses; local publication references remain readable text."""
import re
from html import escape
from urllib.parse import urlsplit

def validate_web_links(addresses):
    if not isinstance(addresses, (list, tuple, set)) or any(not isinstance(a, str) for a in addresses):
        raise ValueError('web_links must contain explicit URL strings')
    for address in addresses:
        parsed = urlsplit(address)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or re.search(r'[\s<>]', address):
            raise ValueError('web link must be HTTP(S), without credentials or whitespace')
        parsed.port  # Reject malformed or out-of-range ports without guessing boundaries.
    return addresses


def url_parts(value, addresses=()):
    addresses = validate_web_links(addresses)
    if not addresses:
        yield value, None
        return
    # Link only author-declared destinations. Guessing from prose would turn
    # Korean particles ("http://와") and Host placeholders into invented URLs.
    pattern = re.compile('|'.join(re.escape(a) for a in sorted(set(addresses), key=len, reverse=True)))
    start = 0
    for match in pattern.finditer(value):
        address = match[0]
        yield value[start:match.start()], None
        yield address, address
        start = match.start() + len(address)
    yield value[start:], None


def safe_url_markup(value, addresses=()):
    return ''.join('<a href="' + escape(url, quote=True) + '">' + escape(label) + '</a>'
                   if url else escape(label) for label, url in url_parts(value, addresses))


def add_docx_links(paragraph, value, addresses=()):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE
    for label, url in url_parts(value, addresses):
        if not url:
            paragraph.add_run(label)
            continue
        link = OxmlElement('w:hyperlink')
        link.set(qn('r:id'), paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True))
        run = OxmlElement('w:r')
        text = OxmlElement('w:t'); text.text = label
        run.append(text); link.append(run); paragraph._p.append(link)
