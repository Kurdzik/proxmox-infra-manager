"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Box, Text, Group, ActionIcon, Tooltip, Badge, CopyButton } from "@mantine/core";
import { IconArrowLeft, IconCopy, IconCheck } from "@tabler/icons-react";
import Link from "next/link";
import { getAuthCookie } from "@/lib/cookies";
import { get } from "@/lib/backendRequests";

interface ConsoleCredentials {
  username: string;
  password: string;
}

export default function VMTerminalPage() {
  const params = useParams();
  const vmId = params.vm_id as string;
  const termRef = useRef<HTMLDivElement>(null);
  const [credentials, setCredentials] = useState<ConsoleCredentials | null>(null);

  useEffect(() => {
    get(`vms/${vmId}/console-credentials`).then((res) => {
      if (res.status === 200 && res.data) {
        setCredentials(res.data as ConsoleCredentials);
      }
    });
  }, [vmId]);

  useEffect(() => {
    if (!termRef.current || !vmId) return;

    let term: import("@xterm/xterm").Terminal | null = null;
    let ws: WebSocket | null = null;

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
        term?.write("\x1b[32mConnected to serial console.\x1b[0m\r\n");
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
      <Group gap="sm" align="center" justify="space-between">
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
            Serial console · VM {vmId}
          </Text>
        </Group>

        {credentials && (
          <Group gap="xs" align="center">
            <Text size="xs" style={{ color: "var(--lnr-text-muted)" }}>Login:</Text>
            <Badge variant="outline" color="blue" size="sm">{credentials.username}</Badge>
            <CopyButton value={credentials.password} timeout={2000}>
              {({ copied, copy }) => (
                <Tooltip label={copied ? "Copied!" : "Copy password"}>
                  <Badge
                    variant="outline"
                    color="gray"
                    size="sm"
                    style={{ cursor: "pointer", fontFamily: "monospace" }}
                    onClick={copy}
                    rightSection={copied ? <IconCheck size={10} /> : <IconCopy size={10} />}
                  >
                    {credentials.password}
                  </Badge>
                </Tooltip>
              )}
            </CopyButton>
          </Group>
        )}
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
