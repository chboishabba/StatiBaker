import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer

from sb.metrics import render_metrics


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        payload = render_metrics(
            state_path=self.server.state_path,
            ledger_path=self.server.ledger_path,
            runtime_path=self.server.runtime_path,
            runtime_ms=self.server.runtime_ms,
        )
        body = payload.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A003
        return


def main():
    parser = argparse.ArgumentParser(description="Serve SB /metrics endpoint.")
    parser.add_argument("--bind", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=9108, help="Port to listen on")
    parser.add_argument("--state", help="Path to state.json")
    parser.add_argument("--ledger", help="Path to activity_ledger.json")
    parser.add_argument("--runtime-file", help="Path to sessionizer runtime ms file")
    parser.add_argument("--runtime-ms", type=int, help="Override sessionizer runtime ms")
    args = parser.parse_args()

    server = HTTPServer((args.bind, args.port), MetricsHandler)
    server.state_path = args.state
    server.ledger_path = args.ledger
    server.runtime_path = args.runtime_file
    server.runtime_ms = args.runtime_ms

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
