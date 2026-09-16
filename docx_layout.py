"""Conservative text measures for DOCX without requiring local font files.

These estimates allocate space, not validate rendering. Every exported page
still requires visual review in the target office renderer.
"""
from functools import lru_cache
from math import ceil, sqrt
import re
import unicodedata

from output_adapters import style_token


def text_width(value, size):
    return size * sum(0 if unicodedata.combining(c) else
                      1 if unicodedata.east_asian_width(c) in ('W', 'F') else
                      .35 if c.isspace() else .6 for c in value)


def wrap_words(value, size, available):
    """Place visible line breaks at spaces, retaining every word and symbol.

    No hidden joiners are inserted into identifiers or copied text. Tokens
    wider than the column remain intact here and use native Office wrapping.
    """
    result = []
    for line in value.split('\n'):
        if text_width(line, size) <= available * .9:
            result.append(line)
            continue
        current = ''
        for word in line.split():
            candidate = current + ' ' + word if current else word
            if current and text_width(candidate, size) > available * .9:
                result.append(current)
                current = word
            else:
                current = candidate
        result.append(current)
    return '\n'.join(result)


def title_lines(value, size, available):
    """Balance existing words; never inject invisible joiners or change letters."""
    limit = available * .94
    lines = []
    for line in value.split('\n'):
        if text_width(line, size) <= limit:
            lines.append(line)
            continue
        words = line.split()
        @lru_cache(None)
        def fit(start):
            if start == len(words):
                return 0, 0, ()
            best = None
            for end in range(start + 1, len(words) + 1):
                current = ' '.join(words[start:end])
                width = text_width(current, size)
                if width > limit and end > start + 1:
                    break
                count, cost, tail = fit(end)
                candidate = (count + 1, cost + (limit - width) ** 2, (current, *tail))
                if best is None or candidate[:2] < best[:2]:
                    best = candidate
            return best
        lines.extend(fit(0)[2])
    return '\n'.join(lines)


def column_widths(block, theme, available):
    count = len(block['headers'])
    if theme.get('table', {}).get('column_width_mode', 'content') == 'equal':
        return [available / count] * count
    padding = 2 * theme.get('table', {}).get('padding_x_pt', 7)
    minima, preferred = [], []
    for column in range(count):
        entries = [(block['headers'][column], style_token(theme, 'table_header')['size_pt'])]
        entries += [(row[column], style_token(theme, 'table_body')['size_pt']) for row in block['rows']]
        # Identifiers may wrap at punctuation; reserve an intact component.
        minimum = padding + 3 + max([text_width(word, size) for text, size in entries
                                 for word in re.split(r'[\s_./,:]+', text) if word] or [12])
        wanted = padding + max([max(text_width(word, size) for word in text.split())
                                 for text, size in entries if text.split()] or [12])
        # Give descriptive prose useful room as well as long physical names.
        prose = padding + max([sqrt(len(text)) * size for text, size in entries] or [12])
        # Reserve prose space only for actual descriptions. Short type/count
        # columns must not consume the room needed by physical identifiers.
        prose_floor = min(90, available / count) if any(len(text.split()) >= 3 for text, _ in entries[1:]) else 30
        minima.append(max(prose_floor, minimum))
        preferred.append(max(minima[-1], wanted, prose))
    if sum(preferred) <= available:
        return [v + (available - sum(preferred)) / count for v in preferred]
    if sum(minima) < available:
        weights = [max(1, p - m) for p, m in zip(preferred, minima)]
        extra = available - sum(minima)
        return [m + extra * w / sum(weights) for m, w in zip(minima, weights)]
    # Exceptionally wide content must still fit the page; do not grow the table.
    # Preserve useful prose room when several long identifiers compete. A
    # proportional shrink would otherwise starve the short description column.
    floor = min(72, available / count)
    weights = [max(1, value - floor) for value in minima]
    return [floor + (available - floor * count) * w / sum(weights) for w in weights]


def short_text_section(blocks, theme, available):
    if any(b['type'] in ('table', 'image') for b in blocks):
        return False
    heading = style_token(theme, 'heading_1')
    height = heading['size_pt'] * theme['line_spacing'] + heading['space_before_pt'] + heading['space_after_pt']
    for block in blocks:
        role = 'heading_' + str(block['level']) if block['type'] == 'heading' else 'body'
        token = style_token(theme, role)
        lines = sum(max(1, ceil(text_width(line, token['size_pt']) / (available * .94)))
                    for line in block['text'].split('\n'))
        height += lines * token['size_pt'] * theme['line_spacing'] + token['space_before_pt'] + token['space_after_pt']
    return height <= theme.get('layout', {}).get('keep_short_sections_max_height_mm', 85) * 72 / 25.4
