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
  Select,
  Switch,
  Alert,
  Skeleton,
} from "@mantine/core";
import {
  IconDeviceFloppy,
  IconServer,
  IconTerminal2,
  IconCheck,
  IconAlertCircle,
} from "@tabler/icons-react";
import { get, post } from "@/lib/backendRequests";
import { DisplayNotification } from "@/components/Notifications/component";

interface ConnectionTestResult {
  success: boolean;
  message: string;
  nodes?: string[];
}

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);

  // Proxmox connection
  const [proxmoxUrl, setProxmoxUrl] = useState("");
  const [proxmoxVersion, setProxmoxVersion] = useState("8");
  const [tokenId, setTokenId] = useState("");
  const [tokenSecret, setTokenSecret] = useState("");
  const [verifySsl, setVerifySsl] = useState(false);
  const [proxmoxLoading, setProxmoxLoading] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);
  const [proxmoxNotification, setProxmoxNotification] = useState<{ message: string; statusCode: number } | null>(null);

  // SSH Credentials for Terraform
  const [sshConfigured, setSshConfigured] = useState(false);
  const [sshUsername, setSshUsername] = useState("");
  const [newSshUsername, setNewSshUsername] = useState("");
  const [newSshPassword, setNewSshPassword] = useState("");
  const [sshSaving, setSshSaving] = useState(false);
  const [sshNotification, setSshNotification] = useState<{ message: string; statusCode: number } | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await get("init/config");
        if (res.status === 200) {
          setProxmoxUrl(res.data?.proxmox_url || "");
          setProxmoxVersion(res.data?.proxmox_version || "8");
          setTokenId(res.data?.token_id || "");
          setVerifySsl(res.data?.verify_ssl ?? false);
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

  const isProxmoxFormValid = () =>
    proxmoxUrl.startsWith("https://") && proxmoxVersion && tokenId && tokenSecret;

  const handleTestConnection = async () => {
    setProxmoxLoading(true);
    setTestResult(null);
    try {
      const res = await post("init/test-connection", {
        proxmox_url: proxmoxUrl,
        proxmox_version: proxmoxVersion,
        token_id: tokenId,
        token_secret: tokenSecret,
        verify_ssl: verifySsl,
      });
      if (res.status === 200) {
        setTestResult({ success: true, message: "Connection successful", nodes: res.data?.nodes });
      } else {
        setTestResult({ success: false, message: res.detail || "Connection failed" });
      }
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || "Connection failed" });
    } finally {
      setProxmoxLoading(false);
    }
  };

  const handleSaveProxmox = async () => {
    setProxmoxLoading(true);
    setProxmoxNotification(null);
    try {
      const res = await post("init/configure", {
        proxmox_url: proxmoxUrl,
        proxmox_version: proxmoxVersion,
        token_id: tokenId,
        token_secret: tokenSecret,
        verify_ssl: verifySsl,
      });
      setProxmoxNotification({ message: res.message || "Configuration saved", statusCode: res.status });
      if (res.status === 200) {
        setTokenSecret("");
        setTestResult(null);
      }
    } catch (err: any) {
      setProxmoxNotification({ message: err.message, statusCode: 500 });
    } finally {
      setProxmoxLoading(false);
    }
  };

  const handleSaveSsh = async () => {
    if (!newSshUsername || !newSshPassword) return;
    setSshSaving(true);
    try {
      const res = await post("init/configure-ssh", {
        ssh_username: newSshUsername,
        ssh_password: newSshPassword,
      });
      setSshNotification({ message: res.message || "SSH credentials saved", statusCode: res.status });
      if (res.status === 200) {
        setSshConfigured(true);
        setSshUsername(newSshUsername);
        setNewSshPassword("");
      }
    } catch (err: any) {
      setSshNotification({ message: err.message, statusCode: 500 });
    } finally {
      setSshSaving(false);
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

      {/* Proxmox Connection */}
      <Paper p="md">
        <Group mb="xs" gap="xs">
          <IconServer size={16} color="var(--lnr-text-muted)" />
          <Text size="sm" fw={600} style={{ color: "var(--lnr-text)" }}>Proxmox Connection</Text>
        </Group>
        <Text size="xs" c="dimmed" mb="md">
          Update the Proxmox VE cluster credentials. A new token secret is required to save changes.
        </Text>

        {proxmoxNotification && (
          <Box mb="md">
            <DisplayNotification message={proxmoxNotification.message} statusCode={proxmoxNotification.statusCode} />
          </Box>
        )}

        {loading ? (
          <Skeleton height={240} />
        ) : (
          <Stack gap="md">
            <TextInput
              label="Proxmox URL"
              placeholder="https://pve01.internal:8006"
              required
              value={proxmoxUrl}
              onChange={(e) => { setProxmoxUrl(e.currentTarget.value); setTestResult(null); }}
              description="HTTPS endpoint of your Proxmox cluster"
              disabled={proxmoxLoading}
            />
            <Select
              label="Proxmox VE Version"
              required
              value={proxmoxVersion}
              onChange={(v) => { setProxmoxVersion(v || "8"); setTestResult(null); }}
              data={[
                { value: "7", label: "Proxmox VE 7.x" },
                { value: "8", label: "Proxmox VE 8.x" },
              ]}
              disabled={proxmoxLoading}
            />
            <TextInput
              label="Token ID"
              placeholder="root@pam!infra-manager"
              required
              value={tokenId}
              onChange={(e) => { setTokenId(e.currentTarget.value); setTestResult(null); }}
              description="Format: user@realm!tokenname"
              disabled={proxmoxLoading}
            />
            <PasswordInput
              label="Token Secret"
              placeholder="Enter new token secret to apply changes"
              required
              value={tokenSecret}
              onChange={(e) => { setTokenSecret(e.currentTarget.value); setTestResult(null); }}
              disabled={proxmoxLoading}
            />
            <Switch
              label="Verify SSL certificate"
              checked={verifySsl}
              onChange={(e) => { setVerifySsl(e.currentTarget.checked); setTestResult(null); }}
              description="Disable for self-signed certificates"
              disabled={proxmoxLoading}
            />

            {testResult && (
              <Alert
                icon={testResult.success ? <IconCheck size={16} /> : <IconAlertCircle size={16} />}
                color={testResult.success ? "green" : "red"}
                variant="light"
              >
                <Text size="xs">{testResult.message}</Text>
                {testResult.nodes && testResult.nodes.length > 0 && (
                  <Text size="xs" mt={4}>Nodes: {testResult.nodes.join(", ")}</Text>
                )}
              </Alert>
            )}

            <Group>
              <Button
                variant="default"
                leftSection={<IconServer size={14} />}
                onClick={handleTestConnection}
                loading={proxmoxLoading}
                disabled={!isProxmoxFormValid()}
              >
                Test Connection
              </Button>
              <Button
                leftSection={<IconCheck size={14} />}
                onClick={handleSaveProxmox}
                loading={proxmoxLoading}
                disabled={!testResult?.success}
              >
                Save
              </Button>
            </Group>
          </Stack>
        )}
      </Paper>

      {/* SSH Credentials for Terraform */}
      <Paper p="md">
        <Group mb="xs" gap="xs" justify="space-between">
          <Group gap="xs">
            <IconTerminal2 size={16} color="var(--lnr-text-muted)" />
            <Text size="sm" fw={600} style={{ color: "var(--lnr-text)" }}>Terraform SSH Credentials</Text>
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

        {sshNotification && (
          <Box mb="md">
            <DisplayNotification message={sshNotification.message} statusCode={sshNotification.statusCode} />
          </Box>
        )}

        <Stack gap="sm">
          <TextInput
            label="SSH Username"
            placeholder="root"
            value={newSshUsername}
            onChange={(e) => setNewSshUsername(e.currentTarget.value)}
            disabled={sshSaving}
          />
          <PasswordInput
            label="SSH Password"
            placeholder={sshConfigured ? "Enter new password to update" : "Password"}
            value={newSshPassword}
            onChange={(e) => setNewSshPassword(e.currentTarget.value)}
            disabled={sshSaving}
          />
          <Group justify="flex-end">
            <Button
              size="sm"
              leftSection={<IconDeviceFloppy size={14} />}
              onClick={handleSaveSsh}
              loading={sshSaving}
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
