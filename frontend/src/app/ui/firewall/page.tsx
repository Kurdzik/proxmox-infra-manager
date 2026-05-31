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
  Modal,
  Select,
  TextInput,
  Skeleton,
} from "@mantine/core";
import { IconPlus, IconTrash, IconShield } from "@tabler/icons-react";
import { get, post, del } from "@/lib/backendRequests";
import type { FirewallRule } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

export default function FirewallPage() {
  const [rules, setRules] = useState<FirewallRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [notification, setNotification] = useState<{ message: string; statusCode: number } | null>(null);

  const [scope, setScope] = useState<string | null>("cluster");
  const [action, setAction] = useState<string | null>("ACCEPT");
  const [direction, setDirection] = useState<string | null>("in");
  const [protocol, setProtocol] = useState<string | null>(null);
  const [sourceIp, setSourceIp] = useState("");
  const [destPort, setDestPort] = useState("");
  const [comment, setComment] = useState("");

  const load = async () => {
    try {
      const res = await get("firewall/list");
      if (res.status === 200) setRules(res.data?.rules || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!scope || !action || !direction) return;
    setCreating(true);
    try {
      const res = await post("firewall/create", {
        scope, action, direction,
        protocol: protocol || undefined,
        source_ip: sourceIp || undefined,
        dest_port: destPort || undefined,
        comment: comment || undefined,
      });
      setNotification({ message: res.message || "Rule created", statusCode: res.status });
      if (res.status === 200) { setModalOpen(false); load(); }
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (ruleId: number) => {
    try {
      const res = await del(`firewall/${ruleId}`);
      setNotification({ message: res.message || "Rule deleted", statusCode: res.status });
      if (res.status === 200) load();
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    }
  };

  return (
    <Stack gap="xl">
      <Group justify="space-between">
        <Box>
          <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Firewall</Title>
          <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
            Manage Proxmox cluster firewall rules
          </Text>
        </Box>
        <Button leftSection={<IconPlus size={14} />} size="sm" onClick={() => setModalOpen(true)}>
          Add Rule
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
                <Table.Th>Scope</Table.Th>
                <Table.Th>Direction</Table.Th>
                <Table.Th>Action</Table.Th>
                <Table.Th>Protocol</Table.Th>
                <Table.Th>Source</Table.Th>
                <Table.Th>Dest Port</Table.Th>
                <Table.Th>Comment</Table.Th>
                <Table.Th>Managed</Table.Th>
                <Table.Th></Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rules.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={9}>
                    <Text size="sm" c="dimmed" ta="center" py="lg">
                      No firewall rules configured.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : (
                rules.map((rule) => (
                  <Table.Tr key={rule.id}>
                    <Table.Td><Text size="sm">{rule.scope}</Text></Table.Td>
                    <Table.Td>
                      <Badge variant="outline" size="xs">{rule.direction}</Badge>
                    </Table.Td>
                    <Table.Td>
                      <Badge
                        color={rule.action === "ACCEPT" ? "green" : rule.action === "DROP" ? "red" : "orange"}
                        variant="light"
                        size="xs"
                      >
                        {rule.action}
                      </Badge>
                    </Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{rule.protocol || "any"}</Text></Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{rule.source_ip || "any"}</Text></Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{rule.dest_port || "any"}</Text></Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{rule.comment || "—"}</Text></Table.Td>
                    <Table.Td>
                      {rule.platform_managed && (
                        <Badge variant="dot" color="accent" size="xs">platform</Badge>
                      )}
                    </Table.Td>
                    <Table.Td>
                      {rule.platform_managed && (
                        <Button
                          size="xs"
                          variant="subtle"
                          color="red"
                          leftSection={<IconTrash size={12} />}
                          onClick={() => handleDelete(rule.id)}
                        >
                          Delete
                        </Button>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))
              )}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title="Add Firewall Rule">
        <Stack gap="md">
          <Select
            label="Scope"
            required
            data={[
              { value: "cluster", label: "Cluster" },
              { value: "node", label: "Node" },
              { value: "vm", label: "VM" },
              { value: "ct", label: "Container" },
            ]}
            value={scope}
            onChange={setScope}
          />
          <Group grow>
            <Select
              label="Direction"
              required
              data={[{ value: "in", label: "Inbound" }, { value: "out", label: "Outbound" }]}
              value={direction}
              onChange={setDirection}
            />
            <Select
              label="Action"
              required
              data={[
                { value: "ACCEPT", label: "Accept" },
                { value: "DROP", label: "Drop" },
                { value: "REJECT", label: "Reject" },
              ]}
              value={action}
              onChange={setAction}
            />
          </Group>
          <Group grow>
            <Select
              label="Protocol"
              placeholder="Any"
              clearable
              data={[{ value: "tcp", label: "TCP" }, { value: "udp", label: "UDP" }, { value: "icmp", label: "ICMP" }]}
              value={protocol}
              onChange={setProtocol}
            />
            <TextInput
              label="Destination Port"
              placeholder="80, 443, 8000-9000"
              value={destPort}
              onChange={(e) => setDestPort(e.currentTarget.value)}
            />
          </Group>
          <TextInput
            label="Source IP / CIDR"
            placeholder="192.168.1.0/24"
            value={sourceIp}
            onChange={(e) => setSourceIp(e.currentTarget.value)}
          />
          <TextInput
            label="Comment"
            placeholder="Optional description"
            value={comment}
            onChange={(e) => setComment(e.currentTarget.value)}
          />
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} loading={creating} disabled={!scope || !action || !direction}>
              Create Rule
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
