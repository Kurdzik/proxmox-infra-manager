"use client";

import { useEffect, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Group,
  Modal,
  Paper,
  Skeleton,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconPlus, IconTrash, IconNetwork } from "@tabler/icons-react";
import { del, get, post } from "@/lib/backendRequests";
import type { VNet } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

export default function NetworksPage() {
  const [networks, setNetworks] = useState<VNet[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [notification, setNotification] = useState<{ message: string; statusCode: number } | null>(null);

  const load = async () => {
    const res = await get("networks/list");
    if (res.status === 200) setNetworks(res.data?.networks || []);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const openModal = () => {
    setNewName("");
    setModalOpen(true);
  };

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    try {
      const res = await post("networks/create", { name });
      setNotification({ message: res.message || "Network created", statusCode: res.status });
      if (res.status === 200) { setModalOpen(false); load(); }
    } catch (err: any) {
      setNotification({ message: err.message || "Failed to create network", statusCode: 500 });
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete network "${name}"? This cannot be undone.`)) return;
    try {
      const res = await del(`networks/${id}`);
      setNotification({ message: res.message || "Network deleted", statusCode: res.status });
      if (res.status === 200) load();
    } catch (err: any) {
      setNotification({ message: err.message || "Failed to delete network", statusCode: 500 });
    }
  };

  return (
    <Stack gap="xl">
      <Group justify="space-between">
        <Box>
          <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Networks</Title>
          <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
            Isolated SDN virtual networks — each has its own subnet and DHCP range
          </Text>
        </Box>
        <Button leftSection={<IconPlus size={14} />} size="sm" onClick={openModal}>
          Create Network
        </Button>
      </Group>

      {notification && (
        <DisplayNotification message={notification.message} statusCode={notification.statusCode} />
      )}

      <Paper>
        {loading ? <Skeleton height={200} m="md" /> : (
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Bridge ID</Table.Th>
                <Table.Th>Subnet</Table.Th>
                <Table.Th>Gateway</Table.Th>
                <Table.Th>DHCP Range</Table.Th>
                <Table.Th>VMs</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {networks.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={7}>
                    <Text size="sm" c="dimmed" ta="center" py="lg">
                      No networks yet.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : networks.map((net) => (
                <Table.Tr key={net.id}>
                  <Table.Td>
                    <Group gap="xs">
                      <IconNetwork size={14} color="var(--lnr-text-faint)" />
                      <Text size="sm" fw={500}>{net.name}</Text>
                      {net.is_default && (
                        <Badge size="xs" color="blue" variant="light">Default</Badge>
                      )}
                    </Group>
                  </Table.Td>
                  <Table.Td><Text size="sm" c="dimmed" ff="monospace">{net.vnet_id}</Text></Table.Td>
                  <Table.Td><Text size="sm">{net.subnet || "—"}</Text></Table.Td>
                  <Table.Td><Text size="sm">{net.gateway || "—"}</Text></Table.Td>
                  <Table.Td>
                    <Text size="sm">
                      {net.dhcp_start && net.dhcp_end ? `${net.dhcp_start} – ${net.dhcp_end}` : "—"}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="xs" color={net.vm_count > 0 ? "teal" : "gray"} variant="light">
                      {net.vm_count}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Button
                      size="xs"
                      variant="subtle"
                      color="red"
                      leftSection={<IconTrash size={12} />}
                      disabled={net.is_default || net.vm_count > 0}
                      title={net.is_default ? "Cannot delete the default network" : net.vm_count > 0 ? "Remove VMs first" : "Delete network"}
                      onClick={() => handleDelete(net.id, net.name)}
                    >
                      Delete
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title="Create Network" size="sm">
        <Stack gap="md">
          <TextInput
            label="Network Name"
            placeholder="e.g. Production, Staging, Dev"
            value={newName}
            onChange={(e) => setNewName(e.currentTarget.value)}
            required
            onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); }}
          />
          <Text size="xs" c="dimmed">
            A new /24 subnet will be auto-allocated and DHCP configured via Proxmox SDN.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} loading={creating} disabled={!newName.trim()}>
              Create
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
