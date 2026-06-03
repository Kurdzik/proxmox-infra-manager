"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Badge,
  Box,
  Button,
  CopyButton,
  Divider,
  Group,
  Loader,
  Modal,
  Paper,
  PasswordInput,
  Skeleton,
  Stack,
  Text,
  Title,
  rem,
} from "@mantine/core";
import {
  IconArrowLeft,
  IconCopy,
  IconCheck,
  IconPackage,
  IconPlayerPlay,
  IconPlayerStop,
  IconTrash,
} from "@tabler/icons-react";
import Link from "next/link";
import { del, get, post } from "@/lib/backendRequests";
import type { AppInstanceDetail } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

const statusColor = (s: string) => {
  switch (s) {
    case "running": return "green";
    case "stopped": return "gray";
    case "provisioning": return "blue";
    case "configuring": return "cyan";
    default: return "red";
  }
};

export default function AppDetailPage() {
  const params = useParams();
  const appId = params.app_id as string;

  const [app, setApp] = useState<AppInstanceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [destroyConfirm, setDestroyConfirm] = useState(false);
  const [notification, setNotification] = useState<{ message: string; statusCode: number } | null>(null);

  const load = async () => {
    const res = await get(`apps/${appId}`);
    if (res.status === 200) setApp(res.data?.app || null);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, [appId]);

  // Poll while provisioning/configuring
  useEffect(() => {
    if (!app) return;
    if (app.status !== "provisioning" && app.status !== "configuring") return;
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [app?.status]);

  const handleStart = async () => {
    setActionLoading("start");
    try {
      const res = await post(`apps/${appId}/start`);
      setNotification({ message: res.message || "Start command sent", statusCode: res.status });
      if (res.status === 200) load();
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    } finally {
      setActionLoading(null);
    }
  };

  const handleStop = async () => {
    setActionLoading("stop");
    try {
      const res = await post(`apps/${appId}/stop`);
      setNotification({ message: res.message || "Stop command sent", statusCode: res.status });
      if (res.status === 200) load();
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    } finally {
      setActionLoading(null);
    }
  };

  const handleDestroy = async () => {
    setDestroyConfirm(false);
    try {
      const res = await del(`apps/${appId}`);
      setNotification({ message: res.message || "Destruction started", statusCode: res.status });
      if (res.status === 200) {
        setTimeout(() => { window.location.href = "/ui/apps"; }, 1500);
      }
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    }
  };

  const connectionString = app?.connection_host && app?.connection_port && app?.connection_user
    ? `postgresql://${app.connection_user}:${app.connection_password}@${app.connection_host}:${app.connection_port}/postgres`
    : null;

  if (loading) {
    return (
      <Stack gap="xl">
        <Skeleton height={40} width={200} />
        <Skeleton height={160} />
        <Skeleton height={160} />
      </Stack>
    );
  }

  if (!app) {
    return (
      <Stack gap="md">
        <Link href="/ui/apps" style={{ textDecoration: "none" }}>
          <Button variant="subtle" leftSection={<IconArrowLeft size={14} />} size="sm">Back to Apps</Button>
        </Link>
        <Text c="dimmed">App not found.</Text>
      </Stack>
    );
  }

  const isBusy = app.status === "provisioning" || app.status === "configuring";
  const isRunning = app.status === "running";
  const isStopped = app.status === "stopped";

  return (
    <Stack gap="xl">
      <Group justify="space-between">
        <Box>
          <Group mb={4} gap="sm">
            <Link href="/ui/apps" style={{ textDecoration: "none" }}>
              <Button variant="subtle" leftSection={<IconArrowLeft size={14} />} size="xs" p={0} style={{ color: "var(--lnr-text-muted)" }}>
                Apps
              </Button>
            </Link>
          </Group>
          <Group gap="sm">
            <IconPackage size={20} color="var(--lnr-text-faint)" />
            <Title order={3} style={{ color: "var(--lnr-text)" }}>{app.name}</Title>
            {isBusy ? (
              <Group gap={6} wrap="nowrap">
                <Loader size="xs" />
                <Text size="xs" c="dimmed">{app.status === "configuring" ? "Installing software…" : "Provisioning VM…"}</Text>
              </Group>
            ) : (
              <Badge color={statusColor(app.status)} variant="light">{app.status}</Badge>
            )}
          </Group>
          <Text size="sm" style={{ color: "var(--lnr-text-muted)" }} mt={4}>
            {app.catalog_name} {app.version} · Node: {app.node_name}
          </Text>
        </Box>

        <Group gap="xs">
          {isRunning && (
            <Button
              size="sm"
              variant="light"
              color="orange"
              leftSection={<IconPlayerStop size={14} />}
              loading={actionLoading === "stop"}
              onClick={handleStop}
            >
              Stop
            </Button>
          )}
          {isStopped && (
            <Button
              size="sm"
              variant="light"
              color="green"
              leftSection={<IconPlayerPlay size={14} />}
              loading={actionLoading === "start"}
              onClick={handleStart}
            >
              Start
            </Button>
          )}
        </Group>
      </Group>

      {notification && (
        <DisplayNotification message={notification.message} statusCode={notification.statusCode} />
      )}

      {/* Connection info */}
      <Paper p="md">
        <Text size="sm" fw={600} mb="md" style={{ color: "var(--lnr-text)" }}>Connection</Text>
        {!app.connection_host ? (
          <Text size="sm" c="dimmed">
            {isBusy ? "Connection details will appear once the app is running." : "No connection info available."}
          </Text>
        ) : (
          <Stack gap="sm">
            <Group grow wrap="nowrap" gap="md">
              <Box>
                <Text size="xs" c="dimmed" mb={2}>Host</Text>
                <Text size="sm" fw={500}>{app.connection_host}</Text>
              </Box>
              <Box>
                <Text size="xs" c="dimmed" mb={2}>Port</Text>
                <Text size="sm" fw={500}>{app.connection_port}</Text>
              </Box>
              <Box>
                <Text size="xs" c="dimmed" mb={2}>Username</Text>
                <Text size="sm" fw={500}>{app.connection_user}</Text>
              </Box>
            </Group>

            <Box>
              <Text size="xs" c="dimmed" mb={2}>Password</Text>
              <PasswordInput
                value={app.connection_password || ""}
                readOnly
                styles={{ input: { fontFamily: "monospace", fontSize: "13px" } }}
              />
            </Box>

            {connectionString && (
              <Box>
                <Text size="xs" c="dimmed" mb={2}>Connection String</Text>
                <Group gap="xs" wrap="nowrap">
                  <Box
                    style={{
                      flex: 1,
                      padding: "6px 10px",
                      borderRadius: 6,
                      backgroundColor: "var(--lnr-elevated)",
                      border: "1px solid var(--lnr-border)",
                      fontFamily: "monospace",
                      fontSize: "12px",
                      color: "var(--lnr-text)",
                      overflowX: "auto",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {connectionString}
                  </Box>
                  <CopyButton value={connectionString} timeout={2000}>
                    {({ copied, copy }) => (
                      <Button
                        variant="light"
                        size="xs"
                        onClick={copy}
                        leftSection={copied ? <IconCheck size={12} /> : <IconCopy size={12} />}
                        color={copied ? "green" : "blue"}
                      >
                        {copied ? "Copied" : "Copy"}
                      </Button>
                    )}
                  </CopyButton>
                </Group>
              </Box>
            )}
          </Stack>
        )}
      </Paper>

      {/* VM details */}
      {app.vm_id && (
        <Paper p="md">
          <Text size="sm" fw={600} mb="sm" style={{ color: "var(--lnr-text)" }}>Underlying VM</Text>
          <Group gap="md">
            <Text size="sm" c="dimmed">VM ID: <span style={{ color: "var(--lnr-text)" }}>{app.vm_id}</span></Text>
            <Button
              size="xs"
              variant="subtle"
              component={Link}
              href={`/ui/vms`}
            >
              View in VMs
            </Button>
          </Group>
        </Paper>
      )}

      {/* Danger zone */}
      <Paper p="md" style={{ borderColor: "var(--mantine-color-red-3)", borderWidth: 1, borderStyle: "solid" }}>
        <Text size="sm" fw={600} mb={4} c="red">Danger Zone</Text>
        <Text size="xs" c="dimmed" mb="sm">
          Destroying this app will remove the VM, nginx stream proxy config, and all associated data. This cannot be undone.
        </Text>
        <Button
          size="sm"
          color="red"
          variant="light"
          leftSection={<IconTrash size={14} />}
          disabled={isBusy}
          onClick={() => setDestroyConfirm(true)}
        >
          Destroy App
        </Button>
      </Paper>

      <Modal
        opened={destroyConfirm}
        onClose={() => setDestroyConfirm(false)}
        title="Confirm destruction"
        size="sm"
      >
        <Stack gap="md">
          <Text size="sm">
            Are you sure you want to destroy <strong>{app.name}</strong>?
            This will remove the VM, nginx config, and all associated data. This cannot be undone.
          </Text>
          <Group justify="flex-end">
            <Button variant="subtle" onClick={() => setDestroyConfirm(false)}>Cancel</Button>
            <Button color="red" onClick={handleDestroy}>Destroy</Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
