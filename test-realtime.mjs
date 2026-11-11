// test-realtime.mjs  (node test-realtime.mjs)
import WebSocket from "ws";

const key = process.env.OPENAI_API_KEY;
const url = "wss://api.openai.com/v1/realtime?model=gpt-realtime-2.1-mini";

function test(label, extraHeaders = {}) {
  const ws = new WebSocket(url, {
    headers: { Authorization: `Bearer ${key}`, ...extraHeaders },
  });
  ws.on("open", () => console.log(label, "OPEN"));
  ws.on("message", (m) => console.log(label, "MSG", String(m).slice(0, 300)));
  ws.on("unexpected-response", (_, res) => console.log(label, "HTTP", res.statusCode));
  ws.on("error", (e) => console.log(label, "ERROR", e.message));
  ws.on("close", (c, r) => console.log(label, "CLOSE", c, String(r)));
  setTimeout(() => ws.close(), 4000);
}

test("GA");
test("BETA", { "OpenAI-Beta": "realtime=v1" });
