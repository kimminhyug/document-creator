"""Local synthetic fixture only; does not read any actual application data."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path not in ("/summary", "/history", "/settings"):
            self.send_error(404)
            return
        name = {"/summary": "성능 요약", "/history": "알람 이력", "/settings": "사용자 설정"}[self.path]
        sections = 5 if self.path == "/summary" else 1
        panels = ''.join(f'<section><h2>영역 {n+1}</h2><p>가상 데이터로 만든 캡처 검증 페이지입니다.</p><table><tr><th>설비</th><th>상태</th></tr><tr><td>OHT-01</td><td>READY</td></tr></table></section>' for n in range(sections))
        html = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><style>
        body{{font-family:"Malgun Gothic",sans-serif;background:#f4f7fb;color:#18324f;margin:0}}
        header{{padding:24px 48px;background:#173b65;color:white}} main{{padding:24px 48px}}
        section{{background:white;border:1px solid #dae4ef;padding:22px;margin:18px 0;min-height:260px}}
        th,td{{text-align:left;padding:12px 60px 12px 8px}} th{{background:#e8f2ff}}
        .private{{display:inline-block;padding:12px;background:#fff;color:#111}} </style>
        <header><h1>{name}</h1><div class="private">개인정보 예시 MASK ME</div></header>
        <main id="ready">{panels}</main></html>'''
        body = html.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
