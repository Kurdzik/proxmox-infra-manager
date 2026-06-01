"use client";

import { useEffect, useState } from "react";
import {
  Title,
  Text,
  Box,
  Stack,
  Paper,
  Group,
  TextInput,
  PasswordInput,
  Button,
  Badge,
  Divider,
} from "@mantine/core";
import { IconDeviceFloppy, IconServer, IconTerminal2 } from "@tabler/icons-react";
import { get, post } from "@/lib/backendRequests";
import { DisplayNotification } from "@/components/Notifications/component";

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notification, setNotification] = useState<{ message: string; statusCode: number } | null>(null);

  // Platform config (read-only display)
  const [proxmoxUrl, setProxmoxUrl] = useState("");
  const [tokenId, setTokenId] = useState("");
  const [sshConfigured, setSshConfigured] = useState(false);
  const [sshUsername, setSshUsername] = useState("");

  // SSH form
  const [newSshUsername, setNewSshUsername] = useState("");
  const [newSshPassword, setNewSshPassword] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const res = await get("init/config");
        if (res.status === 200) {
          setProxmoxUrl(res.data?.proxmox_url || "");
          setTokenId(res.data?.token_id || "");
          setSshConfigured(res.data?.ssh_configured || false);
          setSshUsername(res.data?.ssh_username || "");
          setNewSshUsername(res.data?.ssh_username || "");
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleSaveSsh = async () => {
    if (!newSshUsername || !newSshPassword) return;
    setSaving(true);
    try {
      const res = await post("init/configure-ssh", {
        ssh_username: newSshUsername,
        ssh_password: newSshPassword,
      });
      setNotification({ message: res.message || "SSH credentials saved", statusCode: res.status });
      if (res.status === 200) {
        setSshConfigured(true);
        setSshUsername(newSshUsername);
        setNewSshPassword("");
      }
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Stack gap="xl">
      <Box>
        <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Settings</Title>
        <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
          Platform configuration and credentials
        </Text>
      </Box>

      {notification && (
        <DisplayNotification message={notification.message} statusCode={notification.statusCode} />
      )}

      {/* Proxmox connection (read-only) */}
      <Paper p="md">
        <Group mb="md" gap="xs">
          <IconServer size={16} color="var(--lnr-text-muted)" />
          <Text size="sm" fw={600} style={{ color: "var(--lnr-text)" }}>Proxmox Connection</Text>
        </Group>
        <Stack gap="sm">
          <Group justify="space-between">
            <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>API Endpoint</Text>
            <Text size="sm" ff="monospace">{loading ? "—" : proxmoxUrl}</Text>
          </Group>
          <Divider />
          <Group justify="space-between">
            <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>API Token</Text>
            <Text size="sm" ff="monospace">{loading ? "—" : tokenId}</Text>
          </Group>
        </Stack>
      </Paper>

      {/* SSH Credentials for Terraform */}
      <Paper p="md">
        <Group mb="xs" gap="xs" justify="space-between">
          <Group gap="xs">
            <IconTerminal2 size={16} color="var(--lnr-text-muted)" />
            <Text size="sm" fw={600} style={{ color: "var(--lnr-text)" }}>SSH Credentials</Text>
          </Group>
          <Badge
            color={sshConfigured ? "green" : "orange"}
            variant="light"
            size="xs"
          >
            {sshConfigured ? `configured (${sshUsername})` : "not configured"}
          </Badge>
        </Group>
        <Text size="xs" style={{ color: "var(--lnr-text-muted)" }} mb="md">
          Required by the Terraform Proxmox provider for disk operations. Use the root user or a user with SSH access to all cluster nodes.
        </Text>
        <Stack gap="sm">
          <TextInput
            label="SSH Username"
            placeholder="root"
            value={newSshUsername}
            onChange={(e) => setNewSshUsername(e.currentTarget.value)}
          />
          <PasswordInput
            label="SSH Password"
            placeholder={sshConfigured ? "Enter new password to update" : "Password"}
            value={newSshPassword}
            onChange={(e) => setNewSshPassword(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button
              size="sm"
              leftSection={<IconDeviceFloppy size={14} />}
              onClick={handleSaveSsh}
              loading={saving}
              disabled={!newSshUsername || !newSshPassword}
            >
              Save SSH Credentials
            </Button>
          </Group>
        </Stack>
      </Paper>
    </Stack>
  );
}
