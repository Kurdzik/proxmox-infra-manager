"use client";

import { useEffect, useRef, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Group,
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
  UnstyledButton,
  rem,
} from "@mantine/core";
import {
  IconCheck,
  IconCircleCheck,
  IconCloud,
  IconDeviceDesktop,
  IconDownload,
  IconKey,
  IconPlus,
  IconTerminal,
  IconTrash,
} from "@tabler/icons-react";
import Link from "next/link";
import { del, get, post } from "@/lib/backendRequests";
import type { Node, SSHKey, VM, VmImage } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

function OsIcon({ family, size = 32 }: { family: string; size?: number }) {
  if (family === "ubuntu") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="11" fill="#E95420" />
        <circle cx="12" cy="12" r="4" fill="white" />
        <circle cx="12" cy="4" r="2" fill="white" />
        <circle cx="19.5" cy="16" r="2" fill="white" />
        <circle cx="4.5" cy="16" r="2" fill="white" />
      </svg>
    );
  }
  if (family === "debian") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="11" fill="#A80030" />
        <text x="12" y="16" textAnchor="middle" fontSize="10" fill="white" fontWeight="bold">D</text>
      </svg>
    );
  }
  if (family === "rhel") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="11" fill="#EE0000" />
        <text x="12" y="16" textAnchor="middle" fontSize="8" fill="white" fontWeight="bold">RHL</text>
      </svg>
    );
  }
  if (family === "alpine") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="11" fill="#0D597F" />
        <text x="12" y="16" textAnchor="middle" fontSize="8" fill="white" fontWeight="bold">ALN</text>
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="11" fill="#666" />
    </svg>
  );
}

function generateVmName() {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `vm-${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
}

const statusColor = (s: string) =>
  s === "running" ? "green" : s === "stopped" ? "gray" : s === "provisioning" ? "blue" : "red";

export default function VMsPage() {
  const [vms, setVMs] = useState<VM[]>([]);
  const [images, setImages] = useState<VmImage[]>([]);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [provisioning, setProvisioning] = useState(false);
  const [notification, setNotification] = useState<{ message: string; statusCode: number } | null>(null);

  const [selectedImage, setSelectedImage] = useState<VmImage | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [vmName, setVmName] = useState("");
  const [cpuCores, setCpuCores] = useState<number>(2);
  const [memoryMb, setMemoryMb] = useState<number>(2048);
  const [diskGb, setDiskGb] = useState<number>(20);
  const [cloudInitUser, setCloudInitUser] = useState<string>("ubuntu");
  const [imagesLoading, setImagesLoading] = useState(false);

  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const load = async () => {
    const [vmsRes, nodesRes] = await Promise.allSettled([
      get("vms/list"),
      get("nodes/list"),
    ]);
    if (vmsRes.status === "fulfilled") setVMs(vmsRes.value.data?.vms || []);
    if (nodesRes.status === "fulfilled") setNodes(nodesRes.value.data?.nodes || []);
    setLoading(false);
  };

  useEffect(() => {
    load();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  useEffect(() => {
    const hasProvisioning = vms.some((v) => v.status === "provisioning");
    if (hasProvisioning && !pollRef.current) {
      pollRef.current = setInterval(() => load(), 5000);
    } else if (!hasProvisioning && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, [vms]);

  const loadImages = async (node?: string) => {
    setImagesLoading(true);
    try {
      const qs = node ? `?node=${encodeURIComponent(node)}&storage=local` : "";
      const res = await get(`vms/images${qs}`);
      setImages(res.data?.images || []);
    } finally {
      setImagesLoading(false);
    }
  };

  const openModal = () => {
    setSelectedImage(null);
    setSelectedNode(null);
    setVmName(generateVmName());
    setCpuCores(2);
    setMemoryMb(2048);
    setDiskGb(20);
    setCloudInitUser("ubuntu");
    setModalOpen(true);
    loadImages();
  };

  const handleNodeChange = (node: string | null) => {
    setSelectedNode(node);
    if (node) loadImages(node);
  };

  const handleProvision = async () => {
    if (!selectedImage || !selectedNode || !vmName) return;
    setProvisioning(true);
    try {
      const res = await post("vms/provision", {
        image_id: selectedImage.id,
        node_name: selectedNode,
        vm_name: vmName,
        cpu_cores: cpuCores,
        memory_mb: memoryMb,
        disk_gb: diskGb,
        cloud_init_user: cloudInitUser,
      });
      setNotification({ message: res.message || "VM provisioning started", statusCode: res.status });
      if (res.status === 200) { setModalOpen(false); load(); }
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    } finally {
      setProvisioning(false);
    }
  };

  const handleDelete = async (vmId: number) => {
    try {
      const res = await del(`vms/${vmId}`);
      setNotification({ message: res.message || "VM removal started", statusCode: res.status });
      if (res.status === 200) load();
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    }
  };

  const handleCopySSHKey = async (vmId: number) => {
    try {
      const res = await get(`vms/${vmId}/ssh-key`);
      const key: SSHKey = res.data;
      await navigator.clipboard.writeText(key.public_key);
      setNotification({ message: "Public key copied to clipboard", statusCode: 200 });
    } catch (err: any) {
      setNotification({ message: err.message || "Failed to copy SSH key", statusCode: 500 });
    }
  };

  const onlineNodes = nodes.filter((n) => n.status === "online");

  return (
    <Stack gap="xl">
      <Group justify="space-between">
        <Box>
          <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Virtual Machines</Title>
          <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
            Manage Proxmox QEMU virtual machines — provisioned via Terraform with cloud-init
          </Text>
        </Box>
        <Button leftSection={<IconPlus size={14} />} size="sm" onClick={openModal}>
          Provision VM
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
                <Table.Th>VMID</Table.Th>
                <Table.Th>Node</Table.Th>
                <Table.Th>CPU</Table.Th>
                <Table.Th>Memory</Table.Th>
                <Table.Th>IP</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {vms.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={8}>
                    <Text size="sm" c="dimmed" ta="center" py="lg">
                      No virtual machines yet. Click Provision VM to get started.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : vms.map((vm) => (
                <Table.Tr key={vm.id}>
                  <Table.Td>
                    <Group gap="xs">
                      <IconDeviceDesktop size={14} color="var(--lnr-text-faint)" />
                      <Text size="sm" fw={500}>{vm.name}</Text>
                    </Group>
                  </Table.Td>
                  <Table.Td><Text size="sm" c="dimmed">{vm.vmid}</Text></Table.Td>
                  <Table.Td><Text size="sm">{vm.node_name}</Text></Table.Td>
                  <Table.Td><Text size="sm">{vm.cpu_cores ?? "—"}</Text></Table.Td>
                  <Table.Td>
                    <Text size="sm">
                      {vm.memory_mb != null ? `${Math.round(vm.memory_mb / 1024)} GB` : "—"}
                    </Text>
                  </Table.Td>
                  <Table.Td><Text size="sm" c="dimmed">{vm.ip_address || "—"}</Text></Table.Td>
                  <Table.Td>
                    <Badge color={statusColor(vm.status)} variant="light" size="xs">{vm.status}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} wrap="nowrap">
                      {vm.status === "running" && (
                        <>
                          <Button
                            size="xs"
                            variant="subtle"
                            color="blue"
                            leftSection={<IconTerminal size={12} />}
                            component={Link}
                            href={`/ui/vms/${vm.id}/terminal`}
                          >
                            Terminal
                          </Button>
                          <Button
                            size="xs"
                            variant="subtle"
                            color="teal"
                            leftSection={<IconKey size={12} />}
                            onClick={() => handleCopySSHKey(vm.id)}
                          >
                            SSH Key
                          </Button>
                        </>
                      )}
                      <Button
                        size="xs"
                        variant="subtle"
                        color="red"
                        leftSection={<IconTrash size={12} />}
                        onClick={() => handleDelete(vm.id)}
                        disabled={vm.status === "provisioning"}
                      >
                        Remove
                      </Button>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      {/* Provision modal */}
      <Modal
        opened={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Provision Virtual Machine"
        size="lg"
      >
        <Stack gap="md">
          <Select
            label="Target Node"
            placeholder="Select a cluster node"
            required
            data={onlineNodes.map((n) => ({ value: n.name, label: n.name }))}
            value={selectedNode}
            onChange={handleNodeChange}
          />

          {/* Image picker — cloud-images only */}
          <Box>
            <Text size="sm" fw={500} mb="xs" style={{ color: "var(--lnr-text)" }}>
              Choose cloud image
            </Text>
            {imagesLoading ? (
              <Skeleton height={80} radius="sm" />
            ) : (
              <Stack gap="xs">
                {images.map((img) => {
                  const selected = selectedImage?.id === img.id;
                  return (
                    <UnstyledButton
                      key={img.id}
                      onClick={() => {
                        setSelectedImage(img);
                        // Set default cloud-init user based on OS family
                        const defaultUser =
                          img.os_family === "ubuntu" ? "ubuntu"
                          : img.os_family === "debian" ? "debian"
                          : img.os_family === "rhel" ? "cloud-user"
                          : img.os_family === "alpine" ? "alpine"
                          : "ubuntu";
                        setCloudInitUser(defaultUser);
                      }}
                      style={{
                        border: `1px solid ${selected ? "var(--mantine-color-blue-6)" : "var(--lnr-border)"}`,
                        borderRadius: 6,
                        padding: rem(12),
                        backgroundColor: selected ? "var(--mantine-color-blue-0)" : "var(--lnr-surface)",
                        transition: "border-color 120ms, background-color 120ms",
                      }}
                    >
                      <Group justify="space-between" wrap="nowrap">
                        <Group gap="md" wrap="nowrap">
                          <OsIcon family={img.os_family} size={36} />
                          <Box>
                            <Group gap="xs" align="center">
                              <Text size="sm" fw={600}>{img.name}</Text>
                              <Tooltip label="Cloud image — boots with DHCP, SSH key injected via cloud-init">
                                <Badge size="xs" color="blue" variant="light" leftSection={<IconCloud size={10} />}>
                                  Cloud
                                </Badge>
                              </Tooltip>
                              {selectedNode && (
                                img.available ? (
                                  <Tooltip label="Image already on host">
                                    <Badge
                                      size="xs"
                                      color="green"
                                      variant="light"
                                      leftSection={<IconCircleCheck size={10} />}
                                    >
                                      Ready
                                    </Badge>
                                  </Tooltip>
                                ) : (
                                  <Tooltip label={`~${img.size_gb} GB download required`}>
                                    <Badge
                                      size="xs"
                                      color="orange"
                                      variant="light"
                                      leftSection={<IconDownload size={10} />}
                                    >
                                      {img.size_gb} GB
                                    </Badge>
                                  </Tooltip>
                                )
                              )}
                            </Group>
                            <Text size="xs" c="dimmed">{img.description}</Text>
                          </Box>
                        </Group>
                        {selected && <IconCheck size={16} color="var(--mantine-color-blue-6)" />}
                      </Group>
                    </UnstyledButton>
                  );
                })}
                {images.length === 0 && (
                  <Text size="sm" c="dimmed">No cloud images available.</Text>
                )}
              </Stack>
            )}
          </Box>

          <TextInput
            label="VM Name"
            description="Auto-generated — edit if needed"
            value={vmName}
            onChange={(e) => setVmName(e.currentTarget.value)}
            required
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

          <TextInput
            label="Cloud-init user"
            description="Default login user injected via cloud-init"
            value={cloudInitUser}
            onChange={(e) => setCloudInitUser(e.currentTarget.value)}
          />

          {selectedImage && selectedNode && (
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
                {selectedImage.name} · {vmName} · {selectedNode}
              </Text>
              <Text size="xs" c="dimmed">
                {cpuCores} vCPU · {memoryMb} MB RAM · {diskGb} GB disk · user: {cloudInitUser}
              </Text>
              <Text size="xs" c="dimmed" mt={4}>
                {selectedImage.available
                  ? "Image already on host — Terraform will provision immediately"
                  : `Image will be downloaded first (~${selectedImage.size_gb} GB)`}
              </Text>
            </Box>
          )}

          <Group justify="flex-end" mt="xs">
            <Button variant="default" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button
              onClick={handleProvision}
              loading={provisioning}
              disabled={!selectedImage || !selectedNode || !vmName}
            >
              Provision
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
