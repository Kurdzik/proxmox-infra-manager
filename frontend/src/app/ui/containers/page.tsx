"use client";

import { useEffect, useState, useRef } from "react";
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
  Modal,
  Select,
  Skeleton,
} from "@mantine/core";
import { IconPlus, IconTrash, IconBox } from "@tabler/icons-react";
import { get, post, del } from "@/lib/backendRequests";
import type { Container, CTTemplate, Node } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

export default function ContainersPage() {
  const [containers, setContainers] = useState<Container[]>([]);
  const [templates, setTemplates] = useState<CTTemplate[]>([]);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [provisioning, setProvisioning] = useState(false);
  const [notification, setNotification] = useState<{ message: string; statusCode: number } | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const load = async () => {
    const [ctRes, tplRes, nodesRes] = await Promise.allSettled([
      get("containers/list"),
      get("containers/templates"),
      get("nodes/list"),
    ]);
    if (ctRes.status === "fulfilled") setContainers(ctRes.value.data?.containers || []);
    if (tplRes.status === "fulfilled") setTemplates(tplRes.value.data?.templates || []);
    if (nodesRes.status === "fulfilled") setNodes(nodesRes.value.data?.nodes || []);
    setLoading(false);
  };

  useEffect(() => {
    load();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  useEffect(() => {
    const hasProvisioning = containers.some((c) => c.status === "provisioning");
    if (hasProvisioning && !pollRef.current) {
      pollRef.current = setInterval(() => load(), 5000);
    } else if (!hasProvisioning && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, [containers]);

  const handleProvision = async () => {
    if (!selectedTemplate || !selectedNode) return;
    setProvisioning(true);
    try {
      const res = await post("containers/provision", {
        template_id: parseInt(selectedTemplate),
        node_id: parseInt(selectedNode),
      });
      setNotification({ message: res.message || "Container provisioning started", statusCode: res.status });
      if (res.status === 200) { setModalOpen(false); load(); }
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    } finally {
      setProvisioning(false);
    }
  };

  const handleDelete = async (ctId: number) => {
    try {
      const res = await del(`containers/${ctId}`);
      setNotification({ message: res.message || "Container removal started", statusCode: res.status });
      if (res.status === 200) load();
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    }
  };

  const statusColor = (s: string) =>
    s === "running" ? "green" : s === "stopped" ? "gray" : s === "provisioning" ? "blue" : "red";

  return (
    <Stack gap="xl">
      <Group justify="space-between">
        <Box>
          <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Containers</Title>
          <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
            Manage Proxmox LXC containers
          </Text>
        </Box>
        <Button leftSection={<IconPlus size={14} />} size="sm" onClick={() => setModalOpen(true)}>
          Provision Container
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
                <Table.Th>VMID</Table.Th>
                <Table.Th>Node</Table.Th>
                <Table.Th>CPU</Table.Th>
                <Table.Th>Memory</Table.Th>
                <Table.Th>IP</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th></Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {containers.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={8}>
                    <Text size="sm" c="dimmed" ta="center" py="lg">
                      No containers. Provision one to get started.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : (
                containers.map((ct) => (
                  <Table.Tr key={ct.id}>
                    <Table.Td>
                      <Group gap="xs">
                        <IconBox size={14} color="var(--lnr-text-faint)" />
                        <Text size="sm" fw={500}>{ct.name}</Text>
                      </Group>
                    </Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{ct.vmid}</Text></Table.Td>
                    <Table.Td><Text size="sm">{ct.node_name}</Text></Table.Td>
                    <Table.Td><Text size="sm">{ct.cpu_cores}</Text></Table.Td>
                    <Table.Td><Text size="sm">{Math.round(ct.memory_mb / 1024)} GB</Text></Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{ct.ip_address || "—"}</Text></Table.Td>
                    <Table.Td>
                      <Badge color={statusColor(ct.status)} variant="light" size="xs">
                        {ct.status}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Button
                        size="xs"
                        variant="subtle"
                        color="red"
                        leftSection={<IconTrash size={12} />}
                        onClick={() => handleDelete(ct.id)}
                        disabled={ct.status === "provisioning"}
                      >
                        Remove
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                ))
              )}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title="Provision LXC Container">
        <Stack gap="md">
          <Select
            label="Template"
            placeholder="Select a container template"
            required
            data={templates.map((t) => ({ value: String(t.id), label: `${t.name} — ${t.cpu_cores} vCPU, ${Math.round(t.memory_mb / 1024)} GB` }))}
            value={selectedTemplate}
            onChange={setSelectedTemplate}
          />
          <Select
            label="Target Node"
            placeholder="Select a cluster node"
            required
            data={nodes.filter((n) => n.status === "online").map((n) => ({ value: String(n.id), label: n.name }))}
            value={selectedNode}
            onChange={setSelectedNode}
          />
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button
              onClick={handleProvision}
              loading={provisioning}
              disabled={!selectedTemplate || !selectedNode}
            >
              Provision
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
