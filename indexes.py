"""Human-readable folder maps; no secrets, hashes or evidence identifiers."""
from pathlib import Path
from urllib.parse import quote

MARKER = '<!-- generated-folder-index -->'
SKIP = {'.git', '.local', '.metadata', '__pycache__', 'output', 'workspaces'}


def refresh(root):
    root = Path(root).resolve()
    folders = [root]
    for directory in list(root.rglob('*')):
        if directory.is_dir() and not directory.is_symlink() and not any(p in SKIP for p in directory.relative_to(root).parts):
            folders.append(directory)
    for folder in sorted(folders, key=lambda p: len(p.parts), reverse=True):
        index = folder / 'INDEX.md'
        if index.exists() and MARKER not in index.read_text(encoding='utf-8-sig'):
            continue  # Authored document contents remain authoritative.
        lines = [MARKER, '# ' + ('문서 생성기 안내' if folder == root else folder.name + ' 파일 안내'), '',
                 '이 폴더의 자료는 아래 링크에서 찾습니다. 하위 폴더는 해당 INDEX부터 읽습니다.', '']
        if folder != root:
            lines += ['- [상위 폴더](../INDEX.md)', '']
        for child in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold())):
            if child.name in SKIP or child.name.startswith('.') or child.name.casefold() == 'index.md' or child.is_symlink():
                continue
            target = child.name + ('/INDEX.md' if child.is_dir() else '')
            label = child.name
            if child.suffix.lower() == '.md' and child.is_file():
                heading = next((s[2:] for s in child.read_text(encoding='utf-8-sig').splitlines() if s.startswith('# ')), None)
                if heading:
                    label = heading
            label = label.replace('[', '').replace(']', '')
            lines.append(f'- [{label}]({quote(target, safe="/")})')
        index.write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('root', nargs='?', type=Path, default=Path(__file__).parent)
    refresh(parser.parse_args().root)
