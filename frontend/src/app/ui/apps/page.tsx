"use client";

import { useEffect, useRef, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Group,
  Loader,
  Modal,
  NumberInput,
  Paper,
  Select,
  Skeleton,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
  rem,
} from "@mantine/core";
import { IconPackage, IconPlus, IconTrash } from "@tabler/icons-react";
import Link from "next/link";
import { del, get, post } from "@/lib/backendRequests";
import type { AppCatalogEntry, AppInstance, AppVersion, Node, VmImage, VNet } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

function generateAppName(slug: string) {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  const suffix = Array.from(crypto.getRandomValues(new Uint8Array(4)))
    .map((b) => chars[b % chars.length])
    .join("");
  return `${slug}-${suffix}`;
}

const statusColor = (s: string) => {
  switch (s) {
    case "running": return "green";
    case "stopped": return "gray";
    case "provisioning": return "blue";
    case "configuring": return "cyan";
    default: return "red";
  }
};

const statusLabel = (s: string) => {
  switch (s) {
    case "configuring": return "Installing…";
    default: return s;
  }
};

export default function AppsPage() {
  const [apps, setApps] = useState<AppInstance[]>([]);
  const [catalog, setCatalog] = useState<AppCatalogEntry[]>([]);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [images, setImages] = useState<VmImage[]>([]);
  const [networks, setNetworks] = useState<VNet[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [provisioning, setProvisioning] = useState(false);
  const [notification, setNotification] = useState<{ message: string; statusCode: number } | null>(null);
  const [destroyConfirm, setDestroyConfirm] = useState<AppInstance | null>(null);

  // Form state
  const [selectedCatalogId, setSelectedCatalogId] = useState<string | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [appName, setAppName] = useState("");
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);
  const [cpuCores, setCpuCores] = useState<number>(2);
  const [memoryMb, setMemoryMb] = useState<number>(2048);
  const [diskGb, setDiskGb] = useState<number>(20);
  const [selectedNetworkId, setSelectedNetworkId] = useState<string | null>(null);
  const [imagesLoading, setImagesLoading] = useState(false);

  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const load = async () => {
    const [appsRes, catalogRes, nodesRes] = await Promise.allSettled([
      get("apps/list"),
      get("apps/catalog"),
      get("nodes/list"),
    ]);
    if (appsRes.status === "fulfilled") setApps(appsRes.value.data?.apps || []);
    if (catalogRes.status === "fulfilled") setCatalog(catalogRes.value.data?.catalog || []);
    if (nodesRes.status === "fulfilled") setNodes(nodesRes.value.data?.nodes || []);
    setLoading(false);
  };

  useEffect(() => {
    load();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  useEffect(() => {
    const busy = apps.some((a) => a.status === "provisioning" || a.status === "configuring");
    if (busy && !pollRef.current) {
      pollRef.current = setInterval(() => load(), 5000);
    } else if (!busy && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, [apps]);

  const loadImages = async () => {
    setImagesLoading(true);
    try {
      const res = await get("vms/images");
      setImages(res.data?.images || []);
    } finally {
      setImagesLoading(false);
    }
  };

  const openModal = async () => {
    setSelectedCatalogId(null);
    setSelectedVersionId(null);
    setAppName("");
    setSelectedNode(null);
    setSelectedImageId(null);
    setCpuCores(2);
    setMemoryMb(2048);
    setDiskGb(20);
    setSelectedNetworkId(null);
    setModalOpen(true);
    loadImages();
    const netsRes = await get("networks/list");
    if (netsRes.status === 200) setNetworks(netsRes.data?.networks || []);
  };

  const handleCatalogChange = (val: string | null) => {
    setSelectedCatalogId(val);
    setSelectedVersionId(null);
    if (val) {
      const entry = catalog.find((c) => String(c.id) === val);
      if (entry) {
        const latestVersion = entry.versions.find((v) => v.is_latest) || entry.versions[0];
        if (latestVersion) setSelectedVersionId(String(latestVersion.id));
        setAppName(generateAppName(entry.slug));
      }
    }
  };

  const handleNodeChange = (node: string | null) => {
    setSelectedNode(node);
    setSelectedImageId(null);
  };

  const handleProvision = async () => {
    if (!selectedCatalogId || !selectedVersionId || !appName || !selectedNode || !selectedImageId) return;
    setProvisioning(true);
    try {
      const res = await post("apps/provision", {
        catalog_entry_id: Number(selectedCatalogId),
        version_id: Number(selectedVersionId),
        app_name: appName,
        node_name: selectedNode,
        image_id: selectedImageId,
        cpu_cores: cpuCores,
        memory_mb: memoryMb,
        disk_gb: diskGb,
        network_id: selectedNetworkId ? Number(selectedNetworkId) : undefined,
      });
      setNotification({ message: res.message || "App provisioning started", statusCode: res.status });
      if (res.status === 200) { setModalOpen(false); load(); }
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    } finally {
      setProvisioning(false);
    }
  };

  const handleDestroy = async (appId: number) => {
    setDestroyConfirm(null);
    try {
      const res = await del(`apps/${appId}`);
      setNotification({ message: res.message || "App destruction started", statusCode: res.status });
      if (res.status === 200) load();
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    }
  };

  const selectedCatalog = catalog.find((c) => String(c.id) === selectedCatalogId);
  const availableVersions: AppVersion[] = selectedCatalog?.versions || [];
  const onlineNodes = nodes.filter((n) => n.status === "online");
  const cloudImages = images.filter((i) => i.image_type === "cloud-image");

  const canProvision =
    !!selectedCatalogId &&
    !!selectedVersionId &&
    !!appName &&
    !!selectedNode &&
    !!selectedImageId;

  return (
    <Stack gap="xl">
      <Group justify="space-between">
        <Box>
          <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Apps</Title>
          <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
            Provision prebuilt services — VM provisioned via Terraform, software installed via Ansible
          </Text>
        </Box>
        <Button leftSection={<IconPlus size={14} />} size="sm" onClick={openModal}>
          Provision App
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
                <Table.Th>Type</Table.Th>
                <Table.Th>Version</Table.Th>
                <Table.Th>Node</Table.Th>
                <Table.Th>External Port</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {apps.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={7}>
                    <Text size="sm" c="dimmed" ta="center" py="lg">
                      No apps yet. Click Provision App to get started.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : apps.map((app) => (
                <Table.Tr key={app.id}>
                  <Table.Td>
                    <Group gap="xs">
                      <IconPackage size={14} color="var(--lnr-text-faint)" />
                      <Link href={`/ui/apps/${app.id}`} style={{ textDecoration: "none" }}>
                        <Text size="sm" fw={500} style={{ color: "var(--lnr-accent)" }}>{app.name}</Text>
                      </Link>
                    </Group>
                  </Table.Td>
                  <Table.Td><Text size="sm">{app.catalog_name || "—"}</Text></Table.Td>
                  <Table.Td><Text size="sm">{app.version}</Text></Table.Td>
                  <Table.Td><Text size="sm">{app.node_name}</Text></Table.Td>
                  <Table.Td>
                    <Text size="sm" c={app.external_port ? undefined : "dimmed"}>
                      {app.external_port ? `:${app.external_port}` : "—"}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    {(app.status === "provisioning" || app.status === "configuring") ? (
                      <Tooltip label={statusLabel(app.status)} withArrow>
                        <Group gap={6} wrap="nowrap">
                          <Loader size="xs" />
                          <Text size="xs" c="dimmed">{statusLabel(app.status)}</Text>
                        </Group>
                      </Tooltip>
                    ) : (
                      <Badge color={statusColor(app.status)} variant="light" size="xs">
                        {app.status}
                      </Badge>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Button
                      size="xs"
                      variant="subtle"
                      color="red"
                      leftSection={<IconTrash size={12} />}
                      onClick={() => setDestroyConfirm(app)}
                      disabled={app.status === "provisioning" || app.status === "configuring"}
                    >
                      Destroy
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      {/* Destroy confirmation */}
      <Modal
        opened={!!destroyConfirm}
        onClose={() => setDestroyConfirm(null)}
        title="Confirm destruction"
        size="sm"
      >
        <Stack gap="md">
          <Text size="sm">
            Are you sure you want to destroy <strong>{destroyConfirm?.name}</strong>?
            This will remove the VM, nginx config, and all associated data.
          </Text>
          <Group justify="flex-end">
            <Button variant="subtle" onClick={() => setDestroyConfirm(null)}>Cancel</Button>
            <Button color="red" onClick={() => destroyConfirm && handleDestroy(destroyConfirm.id)}>
              Destroy
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* Provision modal */}
      <Modal
        opened={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Provision App"
        size="lg"
      >
        <Stack gap="md">
          <Select
            label="App Type"
            placeholder="Select an app to provision"
            required
            data={catalog.map((c) => ({ value: String(c.id), label: c.name }))}
            value={selectedCatalogId}
            onChange={handleCatalogChange}
          />

          {selectedCatalog && (
            <Select
              label="Version"
              placeholder="Select version"
              required
              data={availableVersions.map((v) => ({
                value: String(v.id),
                label: v.is_latest ? `${v.version} (latest)` : v.version,
              }))}
              value={selectedVersionId}
              onChange={setSelectedVersionId}
            />
          )}

          {selectedCatalog && (
            <TextInput
              label="App Name"
              description="Auto-generated — edit if needed"
              value={appName}
              onChange={(e) => setAppName(e.currentTarget.value)}
              required
            />
          )}

          <Select
            label="Target Node"
            placeholder="Select a cluster node"
            required
            data={onlineNodes.map((n) => ({ value: n.name, label: n.name }))}
            value={selectedNode}
            onChange={handleNodeChange}
          />

          <Select
            label="Base Image"
            placeholder={imagesLoading ? "Loading images…" : "Select a cloud image"}
            disabled={imagesLoading}
            required
            data={cloudImages.map((img) => ({ value: img.id, label: img.name }))}
            value={selectedImageId}
            onChange={setSelectedImageId}
          />

          <Group grow>
            <NumberInput
              label="CPU Cores"
              min={1}
              max={64}
              value={cpuCores}
              onChange={(v) => setCpuCores(Number(v))}
            />
            <NumberInput
              label="Memory (MB)"
              min={512}
              step={512}
              value={memoryMb}
              onChange={(v) => setMemoryMb(Number(v))}
            />
            <NumberInput
              label="Disk (GB)"
              min={10}
              value={diskGb}
              onChange={(v) => setDiskGb(Number(v))}
            />
          </Group>

          <Select
            label="Network"
            description="Leave empty to auto-create an isolated VNet, or pick an existing one."
            placeholder="Auto-create new VNet (default)"
            data={networks.map((n) => ({
              value: String(n.id),
              label: n.is_default
                ? `${n.name} (default)${n.subnet ? ` — ${n.subnet}` : ""}`
                : `${n.name}${n.subnet ? ` — ${n.subnet}` : ""}`,
            }))}
            value={selectedNetworkId}
            onChange={setSelectedNetworkId}
            clearable
          />

          {canProvision && selectedCatalog && (
            <Box
              style={{
                padding: rem(10),
                borderRadius: 6,
                backgroundColor: "var(--lnr-elevated)",
                border: "1px solid var(--lnr-border)",
              }}
            >
              <Text size="xs" fw={500} mb={4}>Summary</Text>
              <Text size="xs" c="dimmed">
                {selectedCatalog.name} {availableVersions.find((v) => String(v.id) === selectedVersionId)?.version} · {appName}
              </Text>
              <Text size="xs" c="dimmed">
                Node: {selectedNode} · {cpuCores} vCPU · {memoryMb} MB RAM · {diskGb} GB disk
              </Text>
              <Text size="xs" c="dimmed">
                Network: {selectedNetworkId
                  ? networks.find((n) => String(n.id) === selectedNetworkId)?.name ?? selectedNetworkId
                  : "auto-create isolated VNet"}
              </Text>
              <Text size="xs" c="dimmed" mt={4}>
                Port {selectedCatalog.default_port} will be exposed on a port in the range {selectedCatalog.port_range_start}–{selectedCatalog.port_range_end}
              </Text>
            </Box>
          )}

          <Group justify="flex-end" mt="xs">
            <Button variant="default" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button
              onClick={handleProvision}
              loading={provisioning}
              disabled={!canProvision}
            >
              Provision
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
