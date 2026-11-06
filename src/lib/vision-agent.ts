import "server-only";

const VISION_AGENT_URL =
  process.env.VISION_AGENT_URL ?? "http://127.0.0.1:8000";

export type StartVisionAgentOptions = {
  meetingId: string;
  agentId: string;
  agentName: string;
  instructions: string;
};

/**
 * Ask the Python vision-agent service to join a meeting's call.
 *
 * Best-effort: a failing or unreachable service must never fail the webhook,
 * otherwise Stream retries the event and duplicate sessions are created. The
 * meeting simply proceeds without the AI participant.
 *
 * @returns `true` when the service accepted the request, `false` otherwise.
 */
export async function startVisionAgent({
  meetingId,
  agentId,
  agentName,
  instructions,
}: StartVisionAgentOptions): Promise<boolean> {
  try {
    const response = await fetch(`${VISION_AGENT_URL}/agent/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        meeting_id: meetingId,
        agent_id: agentId,
        agent_name: agentName,
        instructions,
      }),
    });

    if (!response.ok) {
      const detail = await response.text();
      console.error("[Meeting Agent] Failed to start vision agent", {
        meetingId,
        status: response.status,
        detail,
      });
      return false;
    }

    console.info("[Meeting Agent] Vision agent dispatched", {
      meetingId,
      agentId,
    });
    return true;
  } catch (error) {
    console.error("[Meeting Agent] Vision agent service unreachable", {
      meetingId,
      error,
    });
    return false;
  }
}

/**
 * Ask the Python vision-agent service to drop its session for a meeting.
 *
 * Best-effort: the call may already be over, the service may be down, or the
 * session may never have started. None of those should fail the caller.
 */
export async function stopVisionAgent(meetingId: string) {
  try {
    const response = await fetch(
      `${VISION_AGENT_URL}/agent/${encodeURIComponent(meetingId)}`,
      { method: "DELETE" }
    );

    if (!response.ok) {
      console.error("[Meeting Agent] Failed to stop vision agent", {
        meetingId,
        status: response.status,
      });
    }
  } catch (error) {
    console.error("[Meeting Agent] Vision agent stop request failed", {
      meetingId,
      error,
    });
  }
}
