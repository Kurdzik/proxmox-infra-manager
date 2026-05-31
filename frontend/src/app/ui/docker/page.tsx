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
  TextInput,
  NumberInput,
  Skeleton,
} from "@mantine/core";
import { IconPlus, IconTrash, IconBrandDocker } from "@tabler/icons-react";
import { get, post, del } from "@/lib/backendRequests";
import type { DockerService, VM, Container, AllowedImage } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

export default function DockerPage() {
  const [services, setServices] = useState<DockerService[]>([]);
  const [vms, setVMs] = useState<VM[]>([]);
  const [containers, setContainers] = useState<Container[]>([]);
  const [images, setImages] = useState<AllowedImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [notification, setNotification] = useState<{ message: string; statusCode: number } | null>(null);

  const [selectedTarget, setSelectedTarget] = useState<string | null>(null);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [imageTag, setImageTag] = useState("latest");
  const [serviceName, setServiceName] = useState("");
  const [internalPort, setInternalPort] = useState<number>(8080);
  const [proxyType, setProxyType] = useState<string | null>("http");

  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const load = async () => {
    const [svcRes, vmRes, ctRes, imgRes] = await Promise.allSettled([
      get("docker/list"),
      get("vms/list"),
      get("containers/list"),
      get("images/list"),
    ]);
    if (svcRes.status === "fulfilled") setServices(svcRes.value.data?.services || []);
    if (vmRes.status === "fulfilled") setVMs(vmRes.value.data?.vms || []);
    if (ctRes.status === "fulfilled") setContainers(ctRes.value.data?.containers || []);
    if (imgRes.status === "fulfilled") setImages(imgRes.value.data?.images || []);
    setLoading(false);
  };

  useEffect(() => {
    load();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  useEffect(() => {
    const hasDeploying = services.some((s) => s.status === "deploying");
    if (hasDeploying && !pollRef.current) {
      pollRef.current = setInterval(() => load(), 5000);
    } else if (!hasDeploying && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, [services]);

  const handleDeploy = async () => {
    if (!selectedTarget || !selectedImage || !serviceName) return;
    const [targetType, targetVmid] = selectedTarget.split(":");
    setDeploying(true);
    try {
      const res = await post("docker/deploy", {
        name: serviceName,
        image_name: selectedImage,
        image_tag: imageTag,
        target_vmid: parseInt(targetVmid),
        target_type: targetType,
        internal_port: internalPort,
        proxy_type: proxyType,
      });
      setNotification({ message: res.message || "Deployment started", statusCode: res.status });
      if (res.status === 200) { setModalOpen(false); load(); }
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    } finally {
      setDeploying(false);
    }
  };

  const handleDelete = async (svcId: number) => {
    try {
      const res = await del(`docker/${svcId}`);
      setNotification({ message: res.message || "Service removal started", statusCode: res.status });
      if (res.status === 200) load();
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    }
  };

  const statusColor = (s: string) =>
    s === "running" ? "green" : s === "stopped" ? "gray" : s === "deploying" ? "blue" : "red";

  const targetOptions = [
    ...vms.filter((v) => v.status === "running").map((v) => ({
      value: `vm:${v.vmid}`,
      label: `[VM] ${v.name} (${v.vmid}) — ${v.node_name}`,
      group: "Virtual Machines",
    })),
    ...containers.filter((c) => c.status === "running").map((c) => ({
      value: `ct:${c.vmid}`,
      label: `[CT] ${c.name} (${c.vmid}) — ${c.node_name}`,
      group: "LXC Containers",
    })),
  ];

  const imageOptions = images.map((img) => ({ value: img.name, label: img.name }));

  return (
    <Stack gap="xl">
      <Group justify="space-between">
        <Box>
          <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Docker Services</Title>
          <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
            Deploy and manage Docker containers on your infrastructure
          </Text>
        </Box>
        <Button leftSection={<IconPlus size={14} />} size="sm" onClick={() => setModalOpen(true)}>
          Deploy Service
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
                <Table.Th>Image</Table.Th>
                <Table.Th>Target</Table.Th>
                <Table.Th>Port</Table.Th>
                <Table.Th>Domain</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th></Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {services.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={7}>
                    <Text size="sm" c="dimmed" ta="center" py="lg">
                      No services deployed. Use Deploy Service to get started.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : (
                services.map((svc) => (
                  <Table.Tr key={svc.id}>
                    <Table.Td>
                      <Group gap="xs">
                        <IconBrandDocker size={14} color="var(--lnr-text-faint)" />
                        <Text size="sm" fw={500}>{svc.name}</Text>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{svc.image_name}:{svc.image_tag}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed">
                        [{svc.target_type.toUpperCase()}] {svc.target_vmid}
                      </Text>
                    </Table.Td>
                    <Table.Td><Text size="sm">{svc.internal_port}</Text></Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed">
                        {svc.dns?.hostname || "—"}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={statusColor(svc.status)} variant="light" size="xs">
                        {svc.status}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Button
                        size="xs"
                        variant="subtle"
                        color="red"
                        leftSection={<IconTrash size={12} />}
                        onClick={() => handleDelete(svc.id)}
                        disabled={svc.status === "deploying"}
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

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title="Deploy Docker Service" size="lg">
        <Stack gap="md">
          <TextInput
            label="Service Name"
            placeholder="my-app"
            required
            value={serviceName}
            onChange={(e) => setServiceName(e.currentTarget.value)}
          />
          <Select
            label="Target Host"
            placeholder="Select a VM or container"
            required
            data={targetOptions}
            value={selectedTarget}
            onChange={setSelectedTarget}
            searchable
          />
          <Group grow>
            <Select
              label="Image"
              placeholder="Select an image"
              required
              data={imageOptions}
              value={selectedImage}
              onChange={setSelectedImage}
              searchable
            />
            <TextInput
              label="Tag"
              placeholder="latest"
              value={imageTag}
              onChange={(e) => setImageTag(e.currentTarget.value)}
            />
          </Group>
          <Group grow>
            <NumberInput
              label="Internal Port"
              required
              value={internalPort}
              onChange={(v) => setInternalPort(Number(v))}
              min={1}
              max={65535}
            />
            <Select
              label="Proxy Type"
              data={[
                { value: "http", label: "HTTP (layer 7)" },
                { value: "tcp", label: "TCP Stream (layer 4)" },
              ]}
              value={proxyType}
              onChange={setProxyType}
            />
          </Group>
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button
              onClick={handleDeploy}
              loading={deploying}
              disabled={!selectedTarget || !selectedImage || !serviceName}
            >
              Deploy
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
