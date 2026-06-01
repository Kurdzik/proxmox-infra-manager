"use client";

import { useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { Box, Text, Group, ActionIcon, Tooltip } from "@mantine/core";
import { IconArrowLeft } from "@tabler/icons-react";
import Link from "next/link";
import { getAuthCookie } from "@/lib/cookies";

export default function VMTerminalPage() {
  const params = useParams();
  const vmId = params.vm_id as string;
  const termRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!termRef.current || !vmId) return;

    let term: import("@xterm/xterm").Terminal | null = null;
    let ws: WebSocket | null = null;

    // Dynamically import xterm to avoid SSR issues
    Promise.all([
      import("@xterm/xterm"),
      import("@xterm/addon-fit"),
    ]).then(([{ Terminal }, { FitAddon }]) => {
      term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: '"Cascadia Code", "JetBrains Mono", "Fira Code", monospace',
        theme: {
          background: "#0d1117",
          foreground: "#e6edf3",
          cursor: "#58a6ff",
          selectionBackground: "#264f78",
        },
        scrollback: 5000,
      });

      const fitAddon = new FitAddon();
      term.loadAddon(fitAddon);
      term.open(termRef.current!);
      fitAddon.fit();

      const token = getAuthCookie();
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "";
      const wsUrl = backendUrl.replace(/^http/, "ws");
      const wsEndpoint = `${wsUrl}/api/v1/vms/${vmId}/terminal?token=${encodeURIComponent(token)}`;

      ws = new WebSocket(wsEndpoint);

      ws.onopen = () => {
        term?.write("\x1b[32mConnected.\x1b[0m\r\n");
        // Send initial terminal size
        const dims = fitAddon.proposeDimensions();
        if (dims) {
          ws?.send(JSON.stringify({ type: "resize", cols: dims.cols, rows: dims.rows }));
        }
      };

      ws.onmessage = (event) => {
        term?.write(event.data);
      };

      ws.onclose = (event) => {
        term?.write(`\r\n\x1b[31mConnection closed (${event.code}).\x1b[0m\r\n`);
      };

      ws.onerror = () => {
        term?.write("\r\n\x1b[31mWebSocket error — check backend logs.\x1b[0m\r\n");
      };

      term.onData((data) => {
        if (ws?.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "data", data }));
        }
      });

      term.onResize(({ cols, rows }) => {
        if (ws?.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "resize", cols, rows }));
        }
      });

      const handleResize = () => fitAddon.fit();
      window.addEventListener("resize", handleResize);

      // Cleanup
      return () => {
        window.removeEventListener("resize", handleResize);
      };
    });

    return () => {
      ws?.close();
      term?.dispose();
    };
  }, [vmId]);

  return (
    <Box style={{ height: "100%", display: "flex", flexDirection: "column", gap: 12 }}>
      <Group gap="sm" align="center">
        <Tooltip label="Back to VMs">
          <ActionIcon
            component={Link}
            href="/ui/vms"
            variant="subtle"
            color="gray"
            size="sm"
          >
            <IconArrowLeft size={16} />
          </ActionIcon>
        </Tooltip>
        <Text size="sm" fw={500} style={{ color: "var(--lnr-text)" }}>
          VM Terminal
        </Text>
        <Text size="xs" style={{ color: "var(--lnr-text-muted)" }}>
          SSH session · VM {vmId}
        </Text>
      </Group>

      <Box
        ref={termRef}
        style={{
          flex: 1,
          backgroundColor: "#0d1117",
          borderRadius: 8,
          overflow: "hidden",
          minHeight: 400,
          border: "1px solid var(--lnr-border)",
          padding: 4,
        }}
      />
    </Box>
  );
}
