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
  PasswordInput,
  Skeleton,
  Code,
} from "@mantine/core";
import { IconPlus, IconTrash, IconRefresh, IconPuzzle } from "@tabler/icons-react";
import { get, post, del } from "@/lib/backendRequests";
import type { Plugin } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

export default function PluginsPage() {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [notification, setNotification] = useState<{ message: string; statusCode: number } | null>(null);

  const [repoUrl, setRepoUrl] = useState("");
  const [authToken, setAuthToken] = useState("");

  const load = async () => {
    try {
      const res = await get("plugins/list");
      if (res.status === 200) setPlugins(res.data?.plugins || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleInstall = async () => {
    if (!repoUrl) return;
    setInstalling(true);
    try {
      const res = await post("plugins/install", { repo_url: repoUrl, auth_token: authToken });
      setNotification({ message: res.message || "Plugin installation started", statusCode: res.status });
      if (res.status === 200) {
        setModalOpen(false);
        setRepoUrl("");
        setAuthToken("");
        load();
      }
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    } finally {
      setInstalling(false);
    }
  };

  const handleUninstall = async (pluginId: number) => {
    try {
      const res = await del(`plugins/${pluginId}`);
      setNotification({ message: res.message || "Plugin uninstalled", statusCode: res.status });
      if (res.status === 200) load();
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    }
  };

  const handleUpdate = async (pluginId: number) => {
    try {
      const res = await post(`plugins/${pluginId}/update`);
      setNotification({ message: res.message || "Plugin update started", statusCode: res.status });
      if (res.status === 200) load();
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    }
  };

  const statusColor = (s: string) =>
    s === "running" ? "green" : s === "stopped" ? "gray" : s === "installing" ? "blue" : "red";

  const parseCapabilities = (caps: string): string[] => {
    try { return JSON.parse(caps); } catch { return []; }
  };

  return (
    <Stack gap="xl">
      <Group justify="space-between">
        <Box>
          <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Plugins</Title>
          <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
            Install and manage platform integrations
          </Text>
        </Box>
        <Button leftSection={<IconPlus size={14} />} size="sm" onClick={() => setModalOpen(true)}>
          Install Plugin
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
                <Table.Th>Version</Table.Th>
                <Table.Th>Capabilities</Table.Th>
                <Table.Th>Base URL</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Installed</Table.Th>
                <Table.Th></Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {plugins.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={7}>
                    <Text size="sm" c="dimmed" ta="center" py="lg">
                      No plugins installed. Install one by providing a repository URL.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : (
                plugins.map((plugin) => (
                  <Table.Tr key={plugin.id}>
                    <Table.Td>
                      <Group gap="xs">
                        <IconPuzzle size={14} color="var(--lnr-text-faint)" />
                        <Text size="sm" fw={500}>{plugin.name}</Text>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed">{plugin.version || "—"}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap={4}>
                        {parseCapabilities(plugin.capabilities).map((cap) => (
                          <Badge key={cap} variant="outline" size="xs" color="accent">
                            {cap}
                          </Badge>
                        ))}
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Code style={{ fontSize: 11 }}>{plugin.base_url}</Code>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={statusColor(plugin.status)} variant="light" size="xs">
                        {plugin.status}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed">
                        {new Date(plugin.installed_at).toLocaleDateString()}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <Button
                          size="xs"
                          variant="subtle"
                          leftSection={<IconRefresh size={12} />}
                          onClick={() => handleUpdate(plugin.id)}
                        >
                          Update
                        </Button>
                        <Button
                          size="xs"
                          variant="subtle"
                          color="red"
                          leftSection={<IconTrash size={12} />}
                          onClick={() => handleUninstall(plugin.id)}
                        >
                          Remove
                        </Button>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))
              )}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title="Install Plugin">
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Provide a Git repository URL containing an <Code>infra-plugin.yaml</Code> manifest.
            The plugin will be cloned and started as a Docker Compose stack.
          </Text>
          <TextInput
            label="Repository URL"
            placeholder="https://github.com/org/my-plugin"
            required
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.currentTarget.value)}
          />
          <PasswordInput
            label="Auth Token"
            placeholder="Personal access token or deploy token"
            description="Required for private repositories"
            value={authToken}
            onChange={(e) => setAuthToken(e.currentTarget.value)}
          />
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleInstall} loading={installing} disabled={!repoUrl}>
              Install
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
