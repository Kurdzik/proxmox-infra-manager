"use client";

import { useEffect, useState } from "react";
import {
  Title,
  Text,
  Box,
  Stack,
  Paper,
  Group,
  Badge,
  Button,
  Table,
  ActionIcon,
  Skeleton,
} from "@mantine/core";
import { IconRefresh, IconServer } from "@tabler/icons-react";
import { get, post } from "@/lib/backendRequests";
import type { Node } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

export default function NodesPage() {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [notification, setNotification] = useState<{ message: string; statusCode: number } | null>(null);

  const load = async () => {
    try {
      const res = await get("nodes/list");
      if (res.status === 200) setNodes(res.data?.nodes || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await post("nodes/sync");
      setNotification({ message: res.message || "Sync triggered", statusCode: res.status });
      if (res.status === 200) setTimeout(load, 2000);
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    } finally {
      setSyncing(false);
    }
  };

  return (
    <Stack gap="xl">
      <Group justify="space-between">
        <Box>
          <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Nodes</Title>
          <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
            Proxmox cluster nodes
          </Text>
        </Box>
        <Button
          leftSection={<IconRefresh size={14} />}
          variant="default"
          size="sm"
          loading={syncing}
          onClick={handleSync}
        >
          Sync Now
        </Button>
      </Group>

      {notification && (
        <DisplayNotification message={notification.message} statusCode={notification.statusCode} />
      )}

      <Paper>
        {loading ? (
          <Skeleton height={200} m="md" />
        ) : (
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Hostname</Table.Th>
                <Table.Th>CPU Cores</Table.Th>
                <Table.Th>Memory</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Last Seen</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {nodes.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={6}>
                    <Text size="sm" c="dimmed" ta="center" py="lg">
                      No nodes found. Click Sync Now to discover cluster nodes.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : (
                nodes.map((node) => (
                  <Table.Tr key={node.id}>
                    <Table.Td>
                      <Group gap="xs">
                        <IconServer size={14} color="var(--lnr-text-faint)" />
                        <Text size="sm" fw={500}>{node.name}</Text>
                      </Group>
                    </Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{node.hostname}</Text></Table.Td>
                    <Table.Td>
                      <Text size="sm">{node.cpu_count ?? "—"}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">
                        {node.memory_mb != null ? `${Math.round(node.memory_mb / 1024)} GB` : "—"}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge
                        color={node.status === "online" ? "green" : "red"}
                        variant="light"
                        size="xs"
                      >
                        {node.status}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed">
                        {node.last_seen_at ? new Date(node.last_seen_at).toLocaleString() : "—"}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                ))
              )}
            </Table.Tbody>
          </Table>
        )}
      </Paper>
    </Stack>
  );
}
