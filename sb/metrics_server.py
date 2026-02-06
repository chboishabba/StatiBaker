import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer

from sb.metrics import render_metrics


class MetricsHandler(BaseHTTPRequestHandler):
    state_path = None
    ledger_path = None
    runtime_path = None

    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        payload = render_metrics(
            state_path=self.state_path,
            ledger_path=self.ledger_path,
            runtime_path=self.runtime_path,
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(payload.encode("utf-8"))

    def log_message(self, format, *args):  # noqa: A003
        return


def main():
    parser = argparse.ArgumentParser(description="Serve SB metrics over HTTP.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--state", required=True, help="Path to state.json")
    parser.add_argument("--ledger", required=True, help="Path to activity_ledger.json")
    parser.add_argument("--runtime", required=True, help="Path to sessionizer_runtime_ms.txt")
    args = parser.parse_args()

    MetricsHandler.state_path = args.state
    MetricsHandler.ledger_path = args.ledger
    MetricsHandler.runtime_path = args.runtime

    server = HTTPServer((args.host, args.port), MetricsHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
