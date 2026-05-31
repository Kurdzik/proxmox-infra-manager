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
  TextInput,
  Select,
  Skeleton,
} from "@mantine/core";
import { IconPlus, IconTrash, IconRefresh } from "@tabler/icons-react";
import { get, post, del } from "@/lib/backendRequests";
import type { DNSEntry } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

export default function DNSPage() {
  const [entries, setEntries] = useState<DNSEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [notification, setNotification] = useState<{ message: string; statusCode: number } | null>(null);

  const [hostname, setHostname] = useState("");
  const [ipAddress, setIpAddress] = useState("");
  const [recordType, setRecordType] = useState<string | null>("A");

  const load = async () => {
    try {
      const res = await get("dns/list");
      if (res.status === 200) setEntries(res.data?.entries || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!hostname || !ipAddress || !recordType) return;
    setCreating(true);
    try {
      const res = await post("dns/create", { hostname, ip_address: ipAddress, record_type: recordType });
      setNotification({ message: res.message || "DNS entry created", statusCode: res.status });
      if (res.status === 200) { setModalOpen(false); setHostname(""); setIpAddress(""); load(); }
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (entryId: number) => {
    try {
      const res = await del(`dns/${entryId}`);
      setNotification({ message: res.message || "DNS entry deleted", statusCode: res.status });
      if (res.status === 200) load();
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await post("dns/sync");
      setNotification({ message: res.message || "DNS sync triggered", statusCode: res.status });
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
          <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>DNS</Title>
          <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
            Manage DNS records via Proxmox SDN
          </Text>
        </Box>
        <Group gap="xs">
          <Button
            leftSection={<IconRefresh size={14} />}
            variant="default"
            size="sm"
            loading={syncing}
            onClick={handleSync}
          >
            Sync
          </Button>
          <Button leftSection={<IconPlus size={14} />} size="sm" onClick={() => setModalOpen(true)}>
            Add Record
          </Button>
        </Group>
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
                <Table.Th>Hostname</Table.Th>
                <Table.Th>IP Address</Table.Th>
                <Table.Th>Type</Table.Th>
                <Table.Th>Zone</Table.Th>
                <Table.Th></Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {entries.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={5}>
                    <Text size="sm" c="dimmed" ta="center" py="lg">
                      No DNS records. Add one or let the platform manage them automatically.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : (
                entries.map((entry) => (
                  <Table.Tr key={entry.id}>
                    <Table.Td><Text size="sm" fw={500}>{entry.hostname}</Text></Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{entry.ip_address}</Text></Table.Td>
                    <Table.Td>
                      <Badge variant="outline" size="xs">{entry.record_type}</Badge>
                    </Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{entry.zone || "—"}</Text></Table.Td>
                    <Table.Td>
                      <Button
                        size="xs"
                        variant="subtle"
                        color="red"
                        leftSection={<IconTrash size={12} />}
                        onClick={() => handleDelete(entry.id)}
                      >
                        Delete
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                ))
              )}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title="Add DNS Record">
        <Stack gap="md">
          <TextInput
            label="Hostname"
            placeholder="myapp.internal"
            required
            value={hostname}
            onChange={(e) => setHostname(e.currentTarget.value)}
          />
          <TextInput
            label="IP Address"
            placeholder="10.100.1.50"
            required
            value={ipAddress}
            onChange={(e) => setIpAddress(e.currentTarget.value)}
          />
          <Select
            label="Record Type"
            required
            data={[{ value: "A", label: "A (IPv4)" }, { value: "AAAA", label: "AAAA (IPv6)" }]}
            value={recordType}
            onChange={setRecordType}
          />
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} loading={creating} disabled={!hostname || !ipAddress}>
              Create
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
